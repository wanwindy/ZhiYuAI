#!/usr/bin/env python3
"""AI router service that delegates to DashScope models."""

import json
import os
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

SERVICE = "ai-router"
VERSION = "1.0.0"

AVAILABLE_ENGINES = [
    {
        "name": "llm-core",
        "model": get_env_var("LLM_MODEL", "qwen3-max"),
        "capabilities": ["chat", "reasoning", "routing"],
    },
    {
        "name": "translation",
        "model": get_env_var("TRANSLATION_MODEL", "qwen3-max"),
        "capabilities": ["translation", "contextual"],
    },
    {
        "name": "vision",
        "model": get_env_var("VISION_MODEL", "qwen-vl-max-latest"),
        "capabilities": ["vision", "scene"],
    },
    {
        "name": "asr-translate",
        "model": get_env_var("ASR_TRANSLATION_MODEL", "gummy-realtime-v1"),
        "capabilities": ["asr", "realtime", "translation"],
    },
    {
        "name": "tts",
        "model": get_env_var("TTS_MODEL", "qwen3-tts-flash"),
        "capabilities": ["tts"],
    },
]
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://localhost:3060"


def _cors_config() -> Dict[str, Any]:
    raw = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).strip()
    if raw == "*":
        return {"allow_origin_regex": ".*", "allow_credentials": False}
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return {"allow_origins": origins, "allow_credentials": True}


def _error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "error": message}, status_code=status_code)


def _fallback_engine(task_type: str) -> Dict[str, Any]:
    mapping = {
        "translation": "translation",
        "vision": "vision",
        "voice": "asr-translate",
        "tts": "tts",
    }
    name = mapping.get(task_type, "llm-core")
    return next((engine for engine in AVAILABLE_ENGINES if engine["name"] == name), AVAILABLE_ENGINES[0])


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": SERVICE, "version": VERSION, "engines": AVAILABLE_ENGINES})


async def route(request: Request) -> JSONResponse:
    payload = await request.json()
    task_type = payload.get("task_type", "general")
    priority = payload.get("priority", "balanced")
    metrics = payload.get("metrics", {})
    hints = payload.get("hints", "")

    system_prompt = (
        "You are the AI routing brain for ZhiYUAI. "
        "Pick the best engine (by name) from the provided list based on task_type, priority and metrics. "
        "Reply as JSON with fields engine (string) and reason (string)."
    )
    engine_summary = json.dumps(AVAILABLE_ENGINES, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Available engines: {engine_summary}\n"
            f"task_type={task_type}\npriority={priority}\nmetrics={metrics}\nhints={hints}",
        },
    ]
    response_text = await chat_completion(messages=messages, temperature=0.2)
    try:
        selection = json.loads(response_text)
        engine_name = selection.get("engine")
        reason = selection.get("reason", "No reason provided.")
    except json.JSONDecodeError:
        fallback = _fallback_engine(task_type)
        engine_name = fallback["name"]
        reason = f"Fallback selection due to parsing error: {response_text}"

    engine = next((eng for eng in AVAILABLE_ENGINES if eng["name"] == engine_name), _fallback_engine(task_type))
    return JSONResponse({"success": True, "data": {"engine": engine, "reason": reason}})


async def engines(_: Request) -> JSONResponse:
    return JSONResponse({"success": True, "data": AVAILABLE_ENGINES})


async def benchmark(request: Request) -> JSONResponse:
    """Summarize provided latency metrics."""
    payload = await request.json()
    metrics = payload.get("metrics", {})
    if not metrics:
        return JSONResponse({"success": True, "data": {"message": "No metrics provided."}})
    messages = [
        {"role": "system", "content": "Summarize routing metrics into a short sentence."},
        {"role": "user", "content": json.dumps(metrics, ensure_ascii=False)},
    ]
    summary = await chat_completion(messages=messages, temperature=0.3)
    return JSONResponse({"success": True, "data": {"summary": summary}})


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/route", route, methods=["POST"]),
    Route("/engines", engines, methods=["GET"]),
    Route("/benchmark", benchmark, methods=["POST"]),
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
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, **uvicorn_ssl_kwargs(SERVICE))
