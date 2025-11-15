"""In-memory stand-ins for the database integration layer.

The original project blueprint referenced a fairly involved PostgreSQL schema.
For HR demos and automated scripts (like ``test_database_integration.py``) we
only need deterministic, dependency-free behaviour.  This module offers simple
async APIs that mimic the original signatures and keep data in process memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from .session import InMemorySession


def _now() -> datetime:
    return datetime.utcnow()


@dataclass
class _TableCounter:
    getter: Any

    async def count(self) -> int:
        items = self.getter()
        return len(items)


@dataclass
class DatabaseService:
    """Expose table-like counters for the in-memory store."""

    session: InMemorySession

    def __post_init__(self) -> None:
        self.users = _TableCounter(lambda: list(_DB["users"].values()))
        self.user_sessions = _TableCounter(lambda: list(_DB["user_sessions"].values()))
        self.translation_history = _TableCounter(lambda: list(_DB["translation_history"].values()))
        self.translation_cache = _TableCounter(lambda: list(_DB["translation_cache"].values()))
        self.system_configurations = _TableCounter(lambda: list(_DB["system_config"].values()))


_DB: Dict[str, Any] = {
    "users": {},
    "user_sessions": {},
    "translation_history": {},
    "translation_cache": {},
    "scene_analysis": {},
    "scene_configurations": {
        "business_meeting": {"translation_style": "formal", "response_speed": "normal"},
        "casual_conversation": {"translation_style": "friendly", "response_speed": "fast"},
    },
    "system_config": {},
    "metrics": [],
    "audit_logs": [],
}


def _ensure_user(user_id: UUID) -> SimpleNamespace:
    user = _DB["users"].get(user_id)
    if user:
        return user
    user = SimpleNamespace(
        id=user_id,
        username=f"user-{str(user_id)[:8]}",
        created_at=_now(),
    )
    _DB["users"][user_id] = user
    return user


class VoiceServiceIntegration:
    @staticmethod
    async def create_or_get_session(*, user_id: UUID, session_id: str) -> SimpleNamespace:
        session = _DB["user_sessions"].get(session_id)
        if session:
            return session
        _ensure_user(user_id)
        session = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            session_id=session_id,
            start_time=_now(),
            total_translations=0,
        )
        _DB["user_sessions"][session_id] = session
        return session


class TranslationServiceIntegration:
    @staticmethod
    async def log_translation(
        *,
        user_id: UUID,
        session_id: UUID,
        source_text: str,
        target_text: str,
        source_language: str,
        target_language: str,
        api_provider: str,
        confidence_score: float,
        quality_score: float,
        processing_time: int,
        scene_context: str,
    ) -> SimpleNamespace:
        _ensure_user(user_id)
        entry = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            session_id=session_id,
            source_text=source_text,
            target_text=target_text,
            source_language=source_language,
            target_language=target_language,
            api_provider=api_provider,
            confidence_score=confidence_score,
            quality_score=quality_score,
            processing_time=processing_time,
            scene_context=scene_context,
            created_at=_now(),
        )
        _DB["translation_history"][entry.id] = entry
        session = _DB["user_sessions"].get(session_id)
        if session:
            session.total_translations += 1
        return entry

    @staticmethod
    async def get_or_create_translation_cache(
        *,
        source_text: str,
        source_language: str,
        target_language: str,
        target_text: str,
        api_provider: str,
        confidence_score: float,
    ) -> SimpleNamespace:
        cache_key = (source_text, source_language, target_language)
        cached = _DB["translation_cache"].get(cache_key)
        if cached:
            return cached
        cached = SimpleNamespace(
            id=uuid4(),
            source_text=source_text,
            source_language=source_language,
            target_language=target_language,
            target_text=target_text,
            api_provider=api_provider,
            confidence_score=confidence_score,
            created_at=_now(),
        )
        _DB["translation_cache"][cache_key] = cached
        return cached


class SceneServiceIntegration:
    @staticmethod
    async def log_scene_analysis(
        *,
        session_id: UUID,
        scene_type: str,
        confidence_score: float,
        audio_features: Dict[str, Any],
        content_features: Dict[str, Any],
    ) -> SimpleNamespace:
        entry = SimpleNamespace(
            id=uuid4(),
            session_id=session_id,
            scene_type=scene_type,
            confidence_score=confidence_score,
            audio_features=audio_features,
            content_features=content_features,
            created_at=_now(),
        )
        _DB["scene_analysis"][entry.id] = entry
        return entry

    @staticmethod
    async def get_scene_configuration(name: str) -> Optional[SimpleNamespace]:
        config = _DB["scene_configurations"].get(name)
        if not config:
            return None
        return SimpleNamespace(name=name, configuration=config)


class SystemIntegration:
    @staticmethod
    async def set_system_config(key: str, value: Any, description: Optional[str] = None) -> None:
        _DB["system_config"][key] = {"value": value, "description": description, "updated_at": _now()}

    @staticmethod
    async def get_system_config(key: str, default: Any | None = None) -> Any:
        config = _DB["system_config"].get(key)
        if config is None:
            return default
        return config["value"]

    @staticmethod
    async def record_metric(*, name: str, value: float, unit: str, labels: Dict[str, Any]) -> None:
        _DB["metrics"].append(
            SimpleNamespace(
                id=uuid4(),
                name=name,
                value=value,
                unit=unit,
                labels=labels,
                created_at=_now(),
            )
        )

    @staticmethod
    async def log_user_action(
        *,
        action: str,
        user_id: UUID,
        resource_type: str,
        resource_id: str,
        new_values: Dict[str, Any],
    ) -> None:
        _DB["audit_logs"].append(
            SimpleNamespace(
                id=uuid4(),
                action=action,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                new_values=new_values,
                created_at=_now(),
            )
        )
