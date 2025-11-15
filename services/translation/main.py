#!/usr/bin/env python3
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.ai_clients import chat_completion, get_env_var  # noqa: E402
from shared.server import uvicorn_ssl_kwargs  # noqa: E402

SERVICE = "translation"
VERSION = "1.0.0"
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL") or os.getenv("LLM_MODEL") or "qwen3-max"
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
    return JSONResponse({"status": "ok", "service": SERVICE, "version": VERSION, "model": TRANSLATION_MODEL})


async def _translate_text(
    *,
    text: str,
    source_language: str | None,
    target_language: str | None,
    context: str | None,
) -> Dict[str, Any]:
    if not text.strip():
        raise ValueError("text is required for translation.")
    tgt = target_language or get_env_var("DEFAULT_TARGET_LANGUAGE", "en")
    src = source_language or "auto"
    context_hint = context or "General conversation."
    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional translation engine. "
                "Preserve meaning, tone, and formatting. Return only the translated text."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Source language: {src}\n"
                f"Target language: {tgt}\n"
                f"Context: {context_hint}\n"
                f"Text: {text}"
            ),
        },
    ]
    translated_text = await chat_completion(messages=messages, model=TRANSLATION_MODEL, temperature=0.1)
    return {
        "original_text": text,
        "translated_text": translated_text,
        "source_language": src,
        "target_language": tgt,
        "engine": TRANSLATION_MODEL,
        "confidence": 0.92,
    }


async def translate(request: Request) -> JSONResponse:
    data = await request.json()
    try:
        result = await _translate_text(
            text=data.get("text", ""),
            source_language=data.get("source_language"),
            target_language=data.get("target_language"),
            context=data.get("context"),
        )
    except ValueError as exc:
        return _error(str(exc))
    return JSONResponse({"success": True, "data": result})


async def translate_batch(request: Request) -> JSONResponse:
    data = await request.json()
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        return _error("items must be a non-empty list.")
    tasks: List[asyncio.Future] = []
    for item in items:
        tasks.append(
            asyncio.create_task(
                _translate_text(
                    text=item.get("text", ""),
                    source_language=item.get("source_language"),
                    target_language=item.get("target_language"),
                    context=item.get("context"),
                )
            )
        )
    results: List[Dict[str, Any]] = []
    for task in tasks:
        try:
            results.append(await task)
        except ValueError as exc:
            results.append({"error": str(exc)})
    return JSONResponse({"success": True, "data": results})


QUALITY_PATTERN = re.compile(r"score\s*[:=]\s*(0?\.\d+|1(\.0+)?)", re.IGNORECASE)


async def quality_assess(request: Request) -> JSONResponse:
    data = await request.json()
    source_text = data.get("source_text", "")
    translated_text = data.get("translated_text", "")
    if not source_text or not translated_text:
        return _error("source_text and translated_text are required.")
    messages = [
        {
            "role": "system",
            "content": (
                "You are a translation quality evaluator. "
                "Score fidelity/fluency between 0 and 1. Reply using the pattern "
                "'score:<float>;feedback:<short summary>'."
            ),
        },
        {
            "role": "user",
            "content": f"Source:\n{source_text}\n\nTranslation:\n{translated_text}",
        },
    ]
    evaluation = await chat_completion(messages=messages, model=TRANSLATION_MODEL, temperature=0.0)
    score_match = QUALITY_PATTERN.search(evaluation)
    score = float(score_match.group(1)) if score_match else 0.0
    feedback_match = re.search(r"feedback\s*:\s*(.*)", evaluation, re.IGNORECASE | re.DOTALL)
    feedback = feedback_match.group(1).strip() if feedback_match else evaluation.strip()
    return JSONResponse({"success": True, "data": {"quality_score": score, "notes": feedback.strip()}})


async def engine_select(request: Request) -> JSONResponse:
    data = await request.json()
    scenario = data.get("scenario", "general")
    priority = data.get("priority", "balanced")
    messages = [
        {
            "role": "system",
            "content": (
                "You decide which internal translation engine should be used. "
                "Available engines: "
                f"{TRANSLATION_MODEL} (balanced quality) and "
                f"{os.getenv('LLM_MODEL', TRANSLATION_MODEL)} (creative). "
                "Respond with the engine name and a short reason."
            ),
        },
        {
            "role": "user",
            "content": f"Scenario: {scenario}\nPriority: {priority}",
        },
    ]
    reason = await chat_completion(messages=messages, temperature=0.2)
    return JSONResponse(
        {
            "success": True,
            "data": {
                "engine": TRANSLATION_MODEL,
                "reason": reason,
            },
        }
    )


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/translate", translate, methods=["POST"]),
    Route("/translate/batch", translate_batch, methods=["POST"]),
    Route("/quality/assess", quality_assess, methods=["POST"]),
    Route("/engine/select", engine_select, methods=["POST"]),
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
    port = int(os.getenv("PORT", "8002"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, **uvicorn_ssl_kwargs(SERVICE))
