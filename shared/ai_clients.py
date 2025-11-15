#!/usr/bin/env python3
"""Shared helpers for integrating with DashScope/Qwen models."""

from __future__ import annotations

import io
import json
import os
import re
import time
import wave
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

import openai
import dashscope

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_TIMEOUT = float(os.getenv("AI_CLIENT_TIMEOUT", "60"))


def _coerce_bool(value: Optional[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _determine_mock_mode() -> bool:
    explicit = os.getenv("USE_MOCK_AI")
    if explicit is not None:
        return _coerce_bool(explicit)
    # If no credentials are provided we default to mock mode for local demos/tests.
    return not bool(os.getenv("DASHSCOPE_API_KEY"))


_MOCK_MODE = _determine_mock_mode()


def is_mock_mode() -> bool:
    """Return whether the services should operate in mock/local mode."""
    return _MOCK_MODE


def get_env_var(name: str, default: Optional[str] = None, *, required: bool = False) -> str:
    """Fetch environment variables with optional default/required semantics."""
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Environment variable '{name}' is required for AI integration.")
    return value or ""


def ensure_dashscope_api_key() -> str:
    """Ensure DashScope global API key is configured on the SDK."""
    if is_mock_mode():
        if not dashscope.api_key:
            dashscope.api_key = "mock-api-key"
        return dashscope.api_key
    api_key = get_env_var("DASHSCOPE_API_KEY", required=True)
    if dashscope.api_key != api_key:
        dashscope.api_key = api_key
    return api_key


def configure_openai_client() -> None:
    """Configure OpenAI global settings for DashScope compatibility (0.28.1 style)."""
    if is_mock_mode():
        openai.api_key = "mock-api-key"
        openai.api_base = DEFAULT_BASE_URL
        return
    api_key = ensure_dashscope_api_key()
    base_url = get_env_var("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL)
    timeout = float(get_env_var("AI_CLIENT_TIMEOUT", str(DEFAULT_TIMEOUT)))
    openai.api_key = api_key
    openai.api_base = base_url
    openai.request_timeout = timeout


async def chat_completion(
    *,
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """Call the DashScope-compatible chat completion API and return the text content."""
    if is_mock_mode():
        return _mock_chat_completion(
            messages=messages,
            model=model or get_env_var("LLM_MODEL", "qwen3-max"),
            temperature=temperature,
            response_format=response_format,
        )
    configure_openai_client()
    model_name = model or get_env_var("LLM_MODEL", "qwen3-max")
    # Build request kwargs
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    # Note: response_format might not be supported in 0.28.1, only add if provided
    if response_format:
        kwargs["response_format"] = response_format
    
    response = await openai.ChatCompletion.acreate(**kwargs)
    # In 0.28.1, response is a dict
    content = response["choices"][0]["message"]["content"]
    return (content or "").strip()


def coerce_language_list(lang: Optional[str]) -> List[str]:
    """Return a normalized translation target language list."""
    if not lang:
        default_lang = get_env_var("DEFAULT_TARGET_LANGUAGE", "en")
        return [default_lang]
    return [lang]


def dashscope_realtime_translator_kwargs(
    *,
    target_languages: Iterable[str],
    translation_enabled: bool,
    callback: Any | None = None,
) -> Dict[str, Any]:
    """Standard kwargs for TranslationRecognizerRealtime."""
    if not is_mock_mode():
        ensure_dashscope_api_key()
    sample_rate = int(get_env_var("ASR_SAMPLE_RATE", "16000"))
    return {
        "model": get_env_var("ASR_TRANSLATION_MODEL", "gummy-realtime-v1"),
        "format": "wav",
        "sample_rate": sample_rate,
        "translation_target_languages": list(target_languages),
        "translation_enabled": translation_enabled,
        "callback": callback,
    }


def mock_voice_interaction_result(
    *,
    target_language: Optional[str],
    enable_translation: bool,
) -> Dict[str, Any]:
    """Produce a deterministic mock result for voice recognize/translate endpoints."""
    transcript = "hello from gummy translator"
    transcripts = [transcript]
    translations: List[Dict[str, Any]] = []
    if enable_translation:
        lang = (target_language or "en").lower()
        translations.append(
            {
                "language": lang,
                "text": pseudo_translate(transcript, lang),
            }
        )
    return {
        "request_id": f"mock-{int(time.time() * 1000)}",
        "transcription": transcripts,
        "translation": translations,
    }


def mock_tts_audio_bytes(_: Optional[str] = None) -> bytes:
    """Generate a short audible WAV (beep) for local/mock mode.

    Using a 440Hz sine wave for ~500ms so users can hear playback
    without requiring external TTS credentials.
    """
    sample_rate = 16000
    duration_sec = 0.5
    freq_hz = 440.0
    amplitude = 0.25  # 25% of full scale to avoid clipping

    total_samples = int(sample_rate * duration_sec)
    frames = bytearray()
    for n in range(total_samples):
        # 2*pi*f*t with t = n / sample_rate
        t = n / sample_rate
        sample = int(32767 * amplitude * __import__("math").sin(2.0 * __import__("math").pi * freq_hz * t))
        # little-endian 16-bit
        frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))
    return buffer.getvalue()


def pseudo_translate(text: str, target_language: Optional[str]) -> str:
    """Return a simple heuristic translation for demo/testing scenarios."""
    if not target_language:
        return text
    lang = target_language.lower()
    if lang in {"zh", "zh-cn", "chinese"}:
        return _translate_en_to_zh(text)
    if lang in {"en", "english"}:
        return text
    return f"[{lang} translation] {text}"


def _translate_en_to_zh(text: str) -> str:
    """Very small deterministic English-to-Chinese pseudo translator."""
    dictionary = {
        "hello": "\u4f60\u597d",
        "hi": "\u55e8",
        "how": "\u5982\u4f55",
        "are": "",
        "you": "\u4f60",
        "today": "\u4eca\u5929",
        "the": "",
        "weather": "\u5929\u6c14",
        "is": "\u662f",
        "really": "\u975e\u5e38",
        "nice": "\u597d",
        "good": "\u597d",
        "thanks": "\u8c22\u8c22",
        "thank": "\u611f\u8c22",
        "meeting": "\u4f1a\u8bae",
        "business": "\u5546\u52a1",
        "travel": "\u51fa\u884c",
        "directions": "\u65b9\u5411",
        "from": "\u6765\u81ea",
        "gummy": "Gummy",
        "translator": "\u7ffb\u8bd1\u5668",
    }
    parts = re.findall(r"[A-Za-z']+|[^A-Za-z']+", text)
    translated = []
    for part in parts:
        lower = part.lower()
        if lower in dictionary:
            translated_text = dictionary[lower]
            if translated_text:
                translated.append(translated_text)
            continue
        if part == ",":
            translated.append("，")
            continue
        if part == "?":
            translated.append("？")
            continue
        if part == "!":
            translated.append("！")
            continue
        if part == ".":
            translated.append("。")
            continue
        translated.append(part)
    joined = "".join(translated)
    joined = re.sub(r"\s+", "", joined)
    if not joined:
        return "译文不可用"
    return joined


class _MockChatCompletions:
    async def create(
        self,
        *,
        model: Optional[str],
        messages: List[Dict[str, Any]],
        temperature: float,
        response_format: Optional[Dict[str, Any]],
        stream: bool,
    ) -> SimpleNamespace:
        content = _mock_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            response_format=response_format,
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _MockAsyncOpenAI:
    """Minimal stub mimicking AsyncOpenAI for local/mock mode."""

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_MockChatCompletions())


def _mock_chat_completion(
    *,
    messages: List[Dict[str, Any]],
    model: Optional[str],
    temperature: float,
    response_format: Optional[Dict[str, Any]],
) -> str:
    """Generate deterministic mock responses tailored to service prompts."""
    system_prompt = ""
    if messages:
        system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
        if system_msg:
            system_content = system_msg.get("content", "")
            if isinstance(system_content, str):
                system_prompt = system_content.lower()
    user_msg = messages[-1] if messages else {}
    user_content = user_msg.get("content") if isinstance(user_msg, dict) else ""

    if isinstance(user_content, list):
        return json.dumps(
            {
                "scenario_name": "mock_scene",
                "confidence": 0.72,
                "summary": "Detected a generic collaborative scenario.",
                "recommended_settings": {
                    "response_style": "neutral",
                    "formality_level": "balanced",
                    "cultural_adaptation": True,
                },
            },
            ensure_ascii=False,
        )

    user_text = str(user_content or "")
    if "translation engine" in system_prompt:
        fields: Dict[str, str] = {}
        for line in user_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().lower()] = value.strip()
        target = fields.get("target language", "en")
        text = fields.get("text", user_text).strip()
        key = (text.lower(), target.lower())
        memorized = {
            ("hello, how are you today?", "zh"): "\u4f60\u597d\uff0c\u4f60\u4eca\u5929\u600e\u4e48\u6837\uff1f",
            ("the weather is really nice today", "zh"): "\u4eca\u5929\u5929\u6c14\u771f\u597d",
        }
        if key in memorized:
            return memorized[key]
        return pseudo_translate(text, target)

    if "translation quality evaluator" in system_prompt:
        return "score:0.88;feedback:Translation reads naturally with minor room for polish."

    if "translation quality evaluator" in user_text.lower():
        return "score:0.85;feedback:Mock evaluation indicates acceptable quality."

    if "decide which internal translation engine" in system_prompt:
        scenario_match = re.search(r"Scenario:\s*(.+)", user_text, re.IGNORECASE)
        scenario = scenario_match.group(1).strip() if scenario_match else "general"
        return f"For scenario '{scenario}' use the balanced translation engine to keep tone consistent."

    if "ai routing brain" in system_prompt:
        task_match = re.search(r"task_type=(\w+)", user_text)
        task_type = task_match.group(1) if task_match else "general"
        engine = "translation" if task_type in {"translation", "voice"} else "llm-core"
        return json.dumps(
            {
                "engine": engine,
                "reason": f"Selected {engine} engine for {task_type} task.",
            }
        )

    if "summarize routing metrics" in system_prompt:
        return "Throughput steady; latency within acceptable bounds."

    if "extract sentiment" in system_prompt:
        sentiment = "positive" if "great" in user_text.lower() else "neutral"
        return json.dumps({"sentiment": sentiment, "topics": ["mock"]})

    if "analyze visual scenes" in system_prompt:
        return json.dumps(
            {
                "scenario_name": "collaboration_session",
                "confidence": 0.78,
                "summary": "Participants engaged in a collaborative discussion.",
                "recommended_settings": {
                    "response_style": "supportive",
                    "formality_level": "balanced",
                    "cultural_adaptation": True,
                },
            },
            ensure_ascii=False,
        )

    if "multilingual scenario coach" in system_prompt:
        if isinstance(messages, list) and messages:
            recent_user = next((msg.get("content") for msg in reversed(messages) if msg.get("role") == "user"), "")
        else:
            recent_user = ""
        return (
            "建议保持语气亲和且表达清晰，先复述要点再给出简洁回应。"
            if "商务" in recent_user
            else "保持自然聊天语气，适度加入礼貌用语，有助于顺畅交流。"
        )

    # Generic fallback response.
    return "Mock response generated locally."
