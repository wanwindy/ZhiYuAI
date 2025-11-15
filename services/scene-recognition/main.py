#!/usr/bin/env python3
"""Scene recognition and dialogue service using DashScope Qwen-VL.

Provides:
- Image-based scene recognition endpoints
- Text analysis helpers
- Realtime scene-dialogue WebSocket: camera frames inform context, mic audio
  is recognized and answered with synthesized speech for speaker output.
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.ai_clients import (  # noqa: E402
    chat_completion,
    get_env_var,
    ensure_dashscope_api_key,
    is_mock_mode,
    mock_tts_audio_bytes,
    dashscope_realtime_translator_kwargs,
)
from shared.server import uvicorn_ssl_kwargs  # noqa: E402

import dashscope  # noqa: E402
from dashscope.audio.asr import TranslationRecognizerCallback, TranslationRecognizerRealtime  # noqa: E402

SERVICE = "scene-recognition"
VERSION = "1.0.0"
VISION_MODEL = get_env_var("VISION_MODEL", "qwen-vl-max-latest")
ASR_MODEL = get_env_var("ASR_TRANSLATION_MODEL", "gummy-realtime-v1")
ASR_SAMPLE_RATE = int(get_env_var("ASR_SAMPLE_RATE", "16000"))
MAX_AUDIO_BYTES = int(get_env_var("MAX_AUDIO_BYTES", str(5 * 1024 * 1024)))

TTS_MODEL = get_env_var("TTS_MODEL", "qwen3-tts-flash")
TTS_VOICE = get_env_var("TTS_VOICE", "Cherry")
TTS_LANGUAGE = get_env_var("TTS_LANGUAGE_TYPE", "Chinese")
TTS_AUDIO_FORMAT = get_env_var("TTS_AUDIO_FORMAT", "wav")
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://localhost:3060"


def _cors_config() -> Dict[str, Any]:
    raw = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).strip()
    if raw == "*":
        return {"allow_origin_regex": ".*", "allow_credentials": False}
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return {"allow_origins": origins, "allow_credentials": True}


def _error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "error": message}, status_code=status_code)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": SERVICE, "version": VERSION, "model": VISION_MODEL})


def _build_image_content(images: List[str], query: str) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = []
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({"type": "text", "text": query})
    return content


async def recognize(request: Request) -> JSONResponse:
    payload = await request.json()
    images = payload.get("image_urls") or payload.get("images") or []
    if not isinstance(images, list) or not images:
        return _error("image_urls must be a non-empty list of URLs.")
    query = payload.get("prompt") or "分析这些画面，识别场景、人物关系和沟通风格，并输出推荐的翻译策略。"
    system_prompt = (
        "You analyze visual scenes for a multilingual assistant. "
        "Respond with JSON containing: scenario_name (string), confidence (0-1), "
        "summary (string), recommended_settings (object with response_style, formality_level, cultural_adaptation boolean)."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_image_content(images, query)},
    ]
    response_text = await chat_completion(messages=messages, model=VISION_MODEL, temperature=0.0)
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = {
            "scenario_name": "unknown",
            "confidence": 0.5,
            "summary": response_text,
            "recommended_settings": {"response_style": "neutral", "formality_level": "balanced", "cultural_adaptation": True},
        }
    return JSONResponse({"success": True, "data": parsed})


async def scenarios(_: Request) -> JSONResponse:
    data = [
        {"name": "business_meeting", "recommended_style": "formal"},
        {"name": "casual_conversation", "recommended_style": "friendly"},
        {"name": "technical_presentation", "recommended_style": "precise"},
    ]
    return JSONResponse({"success": True, "data": data})


async def analyze(request: Request) -> JSONResponse:
    payload = await request.json()
    text = payload.get("context_text", "")
    if not text.strip():
        return _error("context_text is required.")
    messages = [
        {
            "role": "system",
            "content": "Extract sentiment (positive/neutral/negative) and key topics as a JSON object.",
        },
        {
            "role": "user",
            "content": text,
        },
    ]
    response_text = await chat_completion(messages=messages, model=os.getenv("LLM_MODEL", "qwen3-max"))
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = {"sentiment": "neutral", "notes": response_text}
    return JSONResponse({"success": True, "data": parsed})


async def dialogue(request: Request) -> JSONResponse:
    payload = await request.json()
    history = payload.get("history")
    if not isinstance(history, list) or not history:
        return _error("history must be a non-empty list of messages.")
    scenario = payload.get("scenario") or "general"
    language = payload.get("language") or "zh"

    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a multilingual scenario coach. Provide concise, context-aware replies "
                "that help refine translation tone and strategy."
            ),
        }
    ]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            return _error("Each history entry must include role ('user'/'assistant') and text content.")
        messages.append({"role": role, "content": content})

    prompt = (
        f"场景类型: {scenario}\n"
        f"目标语言: {language}\n"
        "请围绕用户需求给出可操作建议，控制在 80 字以内。"
    )
    messages.append({"role": "user", "content": prompt})

    response_text = await chat_completion(messages=messages, model=os.getenv("LLM_MODEL", "qwen3-max"), temperature=0.6)
    return JSONResponse({"success": True, "data": {"reply": response_text.strip()}})


# ======================== Realtime Scene Dialogue ========================

class _StreamingASRCallback(TranslationRecognizerCallback):
    """Collect streaming ASR events and send them to an async queue."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[Dict[str, Any] | None]):
        self._loop = loop
        self._queue = queue
        self._segments: List[str] = []
        self._ended = False

    def _emit(self, payload: Dict[str, Any] | None) -> None:
        asyncio.run_coroutine_threadsafe(self._queue.put(payload), self._loop)

    def _finish(self) -> None:
        if not self._ended:
            self._ended = True
            self._emit(None)

    def on_open(self) -> None:  # noqa: D401
        self._emit({"type": "ready"})

    def on_event(self, request_id, transcription_result, translation_result, usage) -> None:  # noqa: ANN001
        if transcription_result and getattr(transcription_result, "text", ""):
            text = (transcription_result.text or "").strip()
            if text:
                self._segments.append(text)
                aggregated = " ".join(self._segments).strip()
                self._emit({"type": "transcript", "text": aggregated})

    def on_error(self, message) -> None:  # noqa: ANN001
        self._emit({"type": "error", "message": str(message or "asr error")})
        self._finish()

    def on_complete(self) -> None:
        data = {"transcripts": list(self._segments)}
        self._emit({"type": "done", "data": data})
        self._finish()

    def on_close(self) -> None:
        self._finish()


async def _synthesize_speech(text: str, *, voice: Optional[str] = None, language_type: Optional[str] = None) -> bytes:
    if not text.strip():
        raise ValueError("text is required for TTS")
    # Fast-path for local/mock environments
    if is_mock_mode():
        return mock_tts_audio_bytes(text)
    # Attempt online synthesis; if it fails (network/credential), fall back to mock audio
    try:
        ensure_dashscope_api_key()
        voice_name = voice or TTS_VOICE
        lang = language_type or TTS_LANGUAGE

        def _call() -> str:
            response = dashscope.MultiModalConversation.call(
                model=TTS_MODEL,
                api_key=ensure_dashscope_api_key(),
                text=text,
                voice=voice_name,
                language_type=lang,
                audio_format=TTS_AUDIO_FORMAT,
                stream=False,
            )
            return response.output.audio.url

        import httpx  # local import

        audio_url = await asyncio.to_thread(_call)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(audio_url)
            resp.raise_for_status()
            return resp.content
    except Exception:
        # Ensure UX continuity: provide audible mock audio when online TTS is unavailable
        return mock_tts_audio_bytes(text)


async def _analyze_scene_from_url(image_url: str) -> Dict[str, Any]:
    user_content = _build_image_content([image_url], "分析画面，给出场景、摘要与沟通策略")
    system_prompt = (
        "You analyze visual scenes for a multilingual assistant. "
        "Respond with JSON: scenario_name, confidence (0-1), summary, recommended_settings (response_style, formality_level, cultural_adaptation)."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    response_text = await chat_completion(messages=messages, model=VISION_MODEL, temperature=0.0)
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "scenario_name": "unknown",
            "confidence": 0.5,
            "summary": response_text,
            "recommended_settings": {"response_style": "neutral", "formality_level": "balanced", "cultural_adaptation": True},
        }


async def dialogue_live(websocket: WebSocket) -> None:
    """Realtime scene-dialogue over WebSocket.

    Client -> server:
      - Binary: audio frames (WAV/PCM 16k)
      - Text JSON: {"type":"frame","image_url":"https://..."} | {"type":"stop"}

    Server -> client:
      - ready | transcript | scene | assistant_text | assistant_audio | error | done
    """
    await websocket.accept()

    async def _safe_send(payload: Dict[str, Any]) -> bool:
        try:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:  # Connection closed or transport error
            return False

    reply_language = websocket.query_params.get("reply_language") or TTS_LANGUAGE

    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()
    callback = _StreamingASRCallback(loop, event_queue)

    kwargs = dashscope_realtime_translator_kwargs(
        target_languages=[],
        translation_enabled=False,
        callback=callback,
    )

    try:
        recognizer = TranslationRecognizerRealtime(**kwargs)
    except Exception as exc:  # noqa: BLE001
        await _safe_send({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    try:
        await asyncio.to_thread(recognizer.start)
    except Exception as exc:  # noqa: BLE001
        await _safe_send({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    current_scene: Optional[Dict[str, Any]] = None
    last_image_url: Optional[str] = None
    total_bytes = 0
    stopped = False

    async def sender() -> None:
        nonlocal current_scene
        try:
            while True:
                payload = await event_queue.get()
                if payload is None:
                    break
                ptype = payload.get("type")
                if ptype in {"ready", "transcript", "error"}:
                    ok = await _safe_send(payload)
                    if not ok:
                        break
                elif ptype == "done":
                    transcripts = payload.get("data", {}).get("transcripts", [])
                    user_text = " ".join(transcripts).strip()
                    if not user_text:
                        ok = await _safe_send({"type": "done"})
                        if not ok:
                            break
                        continue
                    scene_summary = (current_scene or {}).get("summary") or ""
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful multilingual assistant engaged in a live video conversation. "
                                "Use the provided scene summary to keep responses context-aware and concise."
                            ),
                        },
                        {"role": "user", "content": f"[场景摘要]\n{scene_summary}\n\n[用户]\n{user_text}"},
                    ]
                    try:
                        reply_text = await chat_completion(messages=messages, model=os.getenv("LLM_MODEL", "qwen3-max"), temperature=0.6)
                    except Exception as exc:  # noqa: BLE001
                        if not await _safe_send({"type": "error", "message": str(exc)}):
                            break
                        if not await _safe_send({"type": "done"}):
                            break
                        continue
                    if not await _safe_send({"type": "assistant_text", "text": reply_text.strip()}):
                        break
                    try:
                        audio_bytes = await _synthesize_speech(reply_text, voice=TTS_VOICE, language_type=reply_language)
                        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                        if not await _safe_send({"type": "assistant_audio", "audio_base64": audio_b64, "audio_format": TTS_AUDIO_FORMAT}):
                            break
                    except Exception as exc:  # noqa: BLE001
                        if not await _safe_send({"type": "error", "message": f"TTS失败: {exc}"}):
                            break
                    if not await _safe_send({"type": "done"}):
                        break
        except Exception:
            pass

    sender_task = asyncio.create_task(sender())

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.receive":
                if message.get("bytes"):
                    chunk = message["bytes"] or b""
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > MAX_AUDIO_BYTES:
                            await _safe_send({"type": "error", "message": "音频流超过大小限制"})
                            break
                        await asyncio.to_thread(recognizer.send_audio_frame, chunk)
                elif message.get("text"):
                    try:
                        payload = json.loads(message["text"]) if message.get("text") else {}
                    except json.JSONDecodeError:
                        continue
                    mtype = payload.get("type")
                    if mtype == "frame":
                        image_url = payload.get("image_url")
                        image_b64 = payload.get("image_base64")
                        if not image_url and image_b64:
                            # Try using data URL for compatibility-mode vision API
                            image_url = f"data:image/jpeg;base64,{image_b64}"
                        if image_url and image_url != last_image_url:
                            try:
                                scene = await _analyze_scene_from_url(image_url)
                                current_scene = scene
                                last_image_url = image_url
                                await _safe_send({"type": "scene", **scene})
                            except Exception as exc:  # noqa: BLE001
                                await _safe_send({"type": "error", "message": f"场景识别失败: {exc}"})
                    elif mtype == "stop":
                        await asyncio.to_thread(recognizer.stop)
                        stopped = True
            elif message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        if not stopped:
            try:
                await asyncio.to_thread(recognizer.stop)
            except Exception:  # noqa: BLE001
                pass
        await sender_task
        try:
            await websocket.close()
        except Exception:
            pass


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/recognize", recognize, methods=["POST"]),
    Route("/scenarios", scenarios, methods=["GET"]),
    Route("/analyze", analyze, methods=["POST"]),
    Route("/dialogue", dialogue, methods=["POST"]),
    WebSocketRoute("/dialogue/live", dialogue_live),
]

app = Starlette(debug=False, routes=routes)
cors_kwargs = _cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_kwargs,
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, **uvicorn_ssl_kwargs(SERVICE))
