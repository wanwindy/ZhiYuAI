#!/usr/bin/env python3
"""Helpers for configuring TLS when running Starlette/Uvicorn services."""

from __future__ import annotations

import os
import re
from typing import Dict, Optional, Tuple

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _normalize_prefix(service_name: Optional[str]) -> Optional[str]:
    if not service_name:
        return None
    return re.sub(r"[^A-Z0-9]", "_", service_name.upper())


def _bool_from_env(name: str) -> Optional[bool]:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return None


def _tls_disabled(prefix: Optional[str]) -> bool:
    disable_candidates = []
    enable_candidates = []
    if prefix:
        disable_candidates.append(f"{prefix}_SSL_DISABLE")
        enable_candidates.append(f"{prefix}_SSL_ENABLED")
    disable_candidates.append("SSL_DISABLE")
    enable_candidates.append("SSL_ENABLED")

    for name in disable_candidates:
        result = _bool_from_env(name)
        if result is True:
            return True
    for name in enable_candidates:
        result = _bool_from_env(name)
        if result is False:
            return True
    return False


def _lookup_env(candidates: Tuple[str, ...]) -> Optional[str]:
    for name in candidates:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_ssl_paths(service_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Return the certificate/key paths for a service if configured."""
    prefix = _normalize_prefix(service_name)
    if _tls_disabled(prefix):
        return None, None
    cert_candidates = ()
    key_candidates = ()
    if prefix:
        cert_candidates += (f"{prefix}_SSL_CERTFILE",)
        key_candidates += (f"{prefix}_SSL_KEYFILE",)
    cert_candidates += ("SSL_CERTFILE",)
    key_candidates += ("SSL_KEYFILE",)

    cert_path = _lookup_env(cert_candidates)
    if not cert_path:
        return None, None
    key_path = _lookup_env(key_candidates)
    return cert_path, key_path


def uvicorn_ssl_kwargs(service_name: Optional[str] = None) -> Dict[str, str]:
    """Build keyword arguments for uvicorn.run to enable TLS when configured."""
    cert_path, key_path = resolve_ssl_paths(service_name)
    if not cert_path:
        return {}
    kwargs: Dict[str, str] = {"ssl_certfile": cert_path}
    if key_path:
        kwargs["ssl_keyfile"] = key_path
    return kwargs
