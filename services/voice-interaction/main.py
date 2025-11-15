#!/usr/bin/env python3
"""Voice interaction service backed by DashScope ASR/TTS models."""

import asyncio
import contextlib
import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import dashscope
import httpx
import uvicorn
from dashscope.audio.asr import TranslationRecognizerCallback, TranslationRecognizerRealtime
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.ai_clients import (  # noqa: E402
    coerce_language_list,
   dashscope_realtime_translator_kwargs,
   ensure_dashscope_api_key,
   get_env_var,
   is_mock_mode,
   mock_tts_audio_bytes,
   mock_voice_interaction_result,
)
from shared.server import uvicorn_ssl_kwargs  # noqa: E402

SERVICE = "voice-interaction"
VERSION = "1.0.0"
MAX_AUDIO_BYTES = int(get_env_var("MAX_AUDIO_BYTES", str(5 * 1024 * 1024)))
TTS_MODEL = get_env_var("TTS_MODEL", "qwen3-tts-flash")
TTS_VOICE = get_env_var("TTS_VOICE", "Cherry")
TTS_LANGUAGE = get_env_var("TTS_LANGUAGE_TYPE", "Chinese")
TTS_AUDIO_FORMAT = get_env_var("TTS_AUDIO_FORMAT", "wav")
TTS_FETCH_TIMEOUT = float(get_env_var("TTS_FETCH_TIMEOUT", "30"))
DEFAULT_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS_DEFAULT", "http://localhost:3000,http://localhost:3060")


def _cors_config() -> Dict[str, Any]:
    raw = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).strip()
    if raw == "*":
        return {"allow_origin_regex": ".*", "allow_credentials": False}
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return {"allow_origins": origins, "allow_credentials": True}


def _error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "error": message}, status_code=status_code)


async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": SERVICE,
            "version": VERSION,
            "models": {"asr": get_env_var("ASR_TRANSLATION_MODEL", "gummy-realtime-v1"), "tts": TTS_MODEL},
        }
    )


async def _load_audio_bytes(payload: Dict[str, Any]) -> bytes:
    if "audio_base64" in payload:
        raw = base64.b64decode(payload["audio_base64"])
        if len(raw) > MAX_AUDIO_BYTES:
            raise ValueError("audio payload exceeds MAX_AUDIO_BYTES limit.")
        return raw
    if "audio_url" in payload:
        url = payload["audio_url"]
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            if len(content) > MAX_AUDIO_BYTES:
                raise ValueError("audio download exceeds MAX_AUDIO_BYTES limit.")
            return content
    raise ValueError("Provide 'audio_base64' or 'audio_url'.")


async def _run_translator(
    audio_bytes: bytes,
    *,
    target_language: str | None,
    enable_translation: bool,
) -> Dict[str, Any]:
    if is_mock_mode():
        return mock_voice_interaction_result(target_language=target_language, enable_translation=enable_translation)
    kwargs = dashscope_realtime_translator_kwargs(
        target_languages=coerce_language_list(target_language) if enable_translation else [],
        translation_enabled=enable_translation,
    )

    def _call() -> Dict[str, Any]:
        recognizer = TranslationRecognizerRealtime(**kwargs)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp_path = tmp.name
        try:
            result = recognizer.call(tmp_path)
        finally:
            os.unlink(tmp_path)
        if result.error_message:
            raise RuntimeError(result.error_message)
        return {
            "request_id": result.request_id,
            "transcription": [item.text for item in result.transcription_result_list],
            "translation": (
                [
                    {
                        "language": lang,
                        "text": translation.get_translation(lang).text,
                    }
                    for translation in result.translation_result_list
                    for lang in coerce_language_list(target_language)
                ]
                if enable_translation
                else []
            ),
        }

    return await asyncio.to_thread(_call)


class StreamingRecognizerCallback(TranslationRecognizerCallback):
    """Collect streaming translation events and forward them to the async loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[Dict[str, Any] | None]):
        self._loop = loop
        self._queue = queue
        self._transcripts: List[str] = []
        self._translation_map: Dict[str, str] = {}
        self._request_id: str | None = None
        self._ended = False

    def _schedule(self, payload: Dict[str, Any] | None) -> None:
        asyncio.run_coroutine_threadsafe(self._queue.put(payload), self._loop)

    def _finish(self, payload: Dict[str, Any] | None = None) -> None:
        if payload is not None:
            self._schedule(payload)
        if not self._ended:
            self._ended = True
            self._schedule(None)

    def ensure_finished(self) -> None:
        """Guarantee the queue consumer is released."""
        if not self._ended:
            self._finish()

    def finish_with_error(self, message: str) -> None:
        self._finish({"type": "error", "message": message})

    # Callback interface -------------------------------------------------
    def on_open(self) -> None:  # noqa: D401
        self._schedule({"type": "ready"})

    def on_event(self, request_id, transcription_result, translation_result, usage) -> None:  # noqa: ANN001
        if request_id:
            self._request_id = request_id

        if transcription_result and getattr(transcription_result, "text", ""):
            text = (transcription_result.text or "").strip()
            if text:
                self._transcripts.append(text)
                aggregated = " ".join(self._transcripts).strip()
                self._schedule({"type": "transcript", "text": aggregated})

        if translation_result:
            languages = translation_result.get_language_list() or []
            for language in languages:
                translation = translation_result.get_translation(language)
                if translation and getattr(translation, "text", ""):
                    self._translation_map[language] = translation.text
                    self._schedule(
                        {
                            "type": "translation",
                            "language": language,
                            "text": translation.text,
                        }
                    )

    def on_error(self, message) -> None:  # noqa: ANN001
        self.finish_with_error(str(message or "translation recognizer error"))

    def on_complete(self) -> None:
        data = {
            "request_id": self._request_id,
            "transcripts": list(self._transcripts),
            "translations": [
                {"language": language, "text": text}
                for language, text in self._translation_map.items()
            ],
        }
        self._finish({"type": "done", "data": data})

    def on_close(self) -> None:
        self.ensure_finished()


async def voice_recognize(request: Request) -> JSONResponse:
    payload = await request.json()
    try:
        audio_bytes = await _load_audio_bytes(payload)
        transcription = await _run_translator(audio_bytes, target_language=None, enable_translation=False)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        return _error(str(exc))
    return JSONResponse(
        {
            "success": True,
            "data": {
                "request_id": transcription["request_id"],
                "transcripts": transcription["transcription"],
            },
        }
    )


async def voice_translate(request: Request) -> JSONResponse:
    payload = await request.json()
    target_language = payload.get("target_language")
    try:
        audio_bytes = await _load_audio_bytes(payload)
        translation = await _run_translator(audio_bytes, target_language=target_language, enable_translation=True)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        return _error(str(exc))
    return JSONResponse(
        {
            "success": True,
            "data": {
                "request_id": translation["request_id"],
                "transcripts": translation["transcription"],
                "translations": translation["translation"],
            },
        }
    )


def _sse_format(payload: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def voice_translate_stream(request: Request) -> StreamingResponse:
    """Stream realtime ASR/translation events over SSE for a single audio clip.

    - In mock mode, we emulate streaming from a precomputed result to keep
      local demos/tests stable without external dependencies.
    - In live mode, we feed the audio bytes to DashScope's realtime recognizer
      and forward callback events as SSE frames immediately when they arrive.
    """
    payload = await request.json()
    target_language = payload.get("target_language")

    try:
        audio_bytes = await _load_audio_bytes(payload)
    except (ValueError, httpx.HTTPError) as exc:
        error_payload = _sse_format({"type": "error", "message": str(exc)})
        return StreamingResponse(content=iter([error_payload]), media_type="text/event-stream")

    # Fast path: mock mode preserves previous behavior but streams incrementally.
    if is_mock_mode():
        try:
            translation = await _run_translator(audio_bytes, target_language=target_language, enable_translation=True)
        except (RuntimeError, ValueError) as exc:  # pragma: no cover - defensive
            error_payload = _sse_format({"type": "error", "message": str(exc)})
            return StreamingResponse(content=iter([error_payload]), media_type="text/event-stream")

        async def mock_event_stream() -> AsyncIterator[bytes]:
            yield _sse_format({"type": "ready"})
            transcripts = translation.get("transcription") or []
            aggregated = ""
            for segment in transcripts:
                aggregated = (aggregated + " " + segment).strip()
                yield _sse_format({"type": "transcript", "text": aggregated})
                await asyncio.sleep(0)
            translations = translation.get("translation") or []
            for item in translations:
                yield _sse_format(
                    {
                        "type": "translation",
                        "language": item.get("language"),
                        "text": item.get("text"),
                    }
                )
                await asyncio.sleep(0)
            yield _sse_format({"type": "done", "data": translation})

        return StreamingResponse(mock_event_stream(), media_type="text/event-stream")

    # Live mode: wire the realtime recognizer with a callback and queue.
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()
    callback = StreamingRecognizerCallback(loop, event_queue)

    kwargs = dashscope_realtime_translator_kwargs(
        target_languages=coerce_language_list(target_language),
        translation_enabled=True,
        callback=callback,
    )

    try:
        recognizer = TranslationRecognizerRealtime(**kwargs)
    except Exception as exc:  # noqa: BLE001
        error_payload = _sse_format({"type": "error", "message": str(exc)})
        return StreamingResponse(content=iter([error_payload]), media_type="text/event-stream")

    async def drive_recognizer() -> None:
        try:
            # Start the recognizer session.
            await asyncio.to_thread(recognizer.start)
            # Feed audio frames in chunks to enable progressive results.
            max_bytes = MAX_AUDIO_BYTES
            if len(audio_bytes) > max_bytes:
                callback.finish_with_error("音频流超过大小限制")
                return
            chunk_size = 8192
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i : i + chunk_size]
                await asyncio.to_thread(recognizer.send_audio_frame, chunk)
                await asyncio.sleep(0)  # yield control to flush SSE events
            # Signal end of stream.
            await asyncio.to_thread(recognizer.stop)
        except Exception as exc:  # noqa: BLE001
            callback.finish_with_error(str(exc))
        finally:
            callback.ensure_finished()

    async def live_event_stream() -> AsyncIterator[bytes]:
        driver = asyncio.create_task(drive_recognizer())
        try:
            while True:
                payload = await event_queue.get()
                if payload is None:
                    break
                yield _sse_format(payload)
        finally:
            if not driver.done():
                driver.cancel()
                with contextlib.suppress(Exception):
                    await driver

    return StreamingResponse(live_event_stream(), media_type="text/event-stream")


async def voice_translate_live(websocket: WebSocket) -> None:
    """Handle realtime voice translation over WebSocket."""
    await websocket.accept()
    target_language = websocket.query_params.get("target_language")
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()
    callback = StreamingRecognizerCallback(loop, event_queue)

    kwargs = dashscope_realtime_translator_kwargs(
        target_languages=coerce_language_list(target_language),
        translation_enabled=True,
        callback=callback,
    )

    try:
        recognizer = TranslationRecognizerRealtime(**kwargs)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False))
        await websocket.close()
        return

    try:
        await asyncio.to_thread(recognizer.start)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False))
        await websocket.close()
        return

    async def sender() -> None:
        try:
            while True:
                payload = await event_queue.get()
                if payload is None:
                    break
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except (WebSocketDisconnect, RuntimeError):
            # Connection closed or response no longer possible.
            callback.ensure_finished()

    sender_task = asyncio.create_task(sender())
    total_bytes = 0
    stopped = False

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.receive":
                if message.get("bytes"):
                    chunk = message["bytes"]
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > MAX_AUDIO_BYTES:
                            callback.finish_with_error("音频流超过大小限制")
                            break
                        await asyncio.to_thread(recognizer.send_audio_frame, chunk)
                elif message.get("text"):
                    try:
                        payload = json.loads(message["text"])
                    except json.JSONDecodeError:
                        continue
                    if payload.get("type") == "stop":
                        await asyncio.to_thread(recognizer.stop)
                        stopped = True
                        break
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
        callback.ensure_finished()
        await sender_task
        try:
            await websocket.close()
        except RuntimeError:
            pass


async def _download_tts_audio(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=TTS_FETCH_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _synthesize_speech(text: str, voice: str | None, language: str | None) -> bytes:
    if not text.strip():
        raise ValueError("text is required for TTS.")
    if is_mock_mode():
        return mock_tts_audio_bytes(text)
    ensure_dashscope_api_key()
    voice_name = voice or TTS_VOICE
    language_type = language or TTS_LANGUAGE

    def _call() -> str:
        response = dashscope.MultiModalConversation.call(
            model=TTS_MODEL,
            api_key=ensure_dashscope_api_key(),
            text=text,
            voice=voice_name,
            language_type=language_type,
            audio_format=TTS_AUDIO_FORMAT,
            stream=False,
        )
        return response.output.audio.url

    audio_url = await asyncio.to_thread(_call)
    return await _download_tts_audio(audio_url)


async def tts(request: Request) -> JSONResponse:
    payload = await request.json()
    text = payload.get("text", "")
    try:
        audio_bytes = await _synthesize_speech(text, payload.get("voice"), payload.get("language_type"))
        encoded = base64.b64encode(audio_bytes).decode("utf-8")
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        return _error(str(exc))
    return JSONResponse(
        {
            "success": True,
            "data": {
                "audio_base64": encoded,
                "audio_format": TTS_AUDIO_FORMAT,
                "voice": payload.get("voice") or TTS_VOICE,
            },
        }
    )


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/voice/recognize", voice_recognize, methods=["POST"]),
    Route("/voice/translate", voice_translate, methods=["POST"]),
    Route("/voice/translate/stream", voice_translate_stream, methods=["POST"]),
    Route("/tts", tts, methods=["POST"]),
    WebSocketRoute("/voice/translate/live", voice_translate_live),
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
    port = int(os.getenv("PORT", "8004"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, **uvicorn_ssl_kwargs(SERVICE))
