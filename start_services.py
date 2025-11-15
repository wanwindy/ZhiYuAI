#!/usr/bin/env python3
"""
一键启动 ZhiYUAI 全部微服务（中文输出版）。
"""

from __future__ import annotations

import io
import os
import runpy
import signal
import sys
import time
import importlib
from dataclasses import dataclass
from pathlib import Path
from subprocess import Popen
from typing import Dict, List

try:
    import requests
except ImportError:
    print("⚠️ 未检测到 requests 库，请先执行: pip install requests", file=sys.stderr)
    sys.exit(1)


IS_FROZEN = getattr(sys, "frozen", False)
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PROJECT_ROOT = Path.cwd() if IS_FROZEN else BUNDLE_ROOT
if str(BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_ROOT))

if IS_FROZEN:
    _FROZEN_IMPORTS = [
        "uvicorn",
        "starlette.applications",
        "starlette.middleware.cors",
        "starlette.requests",
        "starlette.responses",
        "starlette.routing",
        "starlette.websockets",
        "dashscope",
        "dashscope.audio.asr",
        "httpx",
        "openai",
        "sqlalchemy",
        "sqlalchemy.ext.asyncio",
        "sqlalchemy.orm",
        "asyncpg",
        "psycopg2",
        "dotenv",
        "structlog",
        "pydantic",
    ]
    for module_name in _FROZEN_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception:
            pass
DEFAULT_HEALTH_PATH = "/health"


def configure_stdio() -> None:
    """Force UTF-8 console output; fall back to replacing unmappable chars."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if not stream:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
                continue
        except Exception:
            pass
        buffer = getattr(stream, "buffer", None)
        if buffer:
            try:
                wrapper = io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
            except Exception:
                continue
            setattr(sys, name, wrapper)


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    script: Path
    port: int
    health_path: str = DEFAULT_HEALTH_PATH


SERVICES: List[ServiceConfig] = [
    ServiceConfig("\u7ffb\u8bd1\u670d\u52a1", BUNDLE_ROOT / "services" / "translation" / "main.py", 8002),
    ServiceConfig("AI \u8def\u7531\u670d\u52a1", BUNDLE_ROOT / "services" / "ai-router" / "main.py", 8001),
    ServiceConfig("\u573a\u666f\u8bc6\u522b\u670d\u52a1", BUNDLE_ROOT / "services" / "scene-recognition" / "main.py", 8003),
    ServiceConfig("\u8bed\u97f3\u4ea4\u4e92\u670d\u52a1", BUNDLE_ROOT / "services" / "voice-interaction" / "main.py", 8004),
]


_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _tls_disabled(env: Dict[str, str], prefix: str | None) -> bool:
    disable_candidates = []
    enable_candidates = []
    if prefix:
        disable_candidates.append(f"{prefix}_SSL_DISABLE")
        enable_candidates.append(f"{prefix}_SSL_ENABLED")
    disable_candidates.append("SSL_DISABLE")
    enable_candidates.append("SSL_ENABLED")

    for name in disable_candidates:
        value = env.get(name)
        if value and value.strip().lower() in _TRUTHY:
            return True
    for name in enable_candidates:
        value = env.get(name)
        if value and value.strip().lower() in _FALSY:
            return True
    return False


def load_env_file(path: Path) -> Dict[str, str]:
    """读取 .env 文件中的键值配置。"""
    if not path.exists():
        return {}
    env: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def _service_command(config: ServiceConfig) -> List[str]:
    if IS_FROZEN:
        try:
            rel_path = config.script.relative_to(BUNDLE_ROOT).as_posix()
        except ValueError:
            rel_path = os.path.relpath(config.script, BUNDLE_ROOT).replace("\\", "/")
        return [sys.executable, "--run-service", rel_path]
    return [sys.executable, str(config.script)]


def start_service(config: ServiceConfig, extra_env: Dict[str, str]) -> Popen:
    """启动单个微服务并返回子进程对象。"""
    command = _service_command(config)
    env = os.environ.copy()
    env.update(extra_env)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=None,
        stderr=None,
        text=True,
    )


def wait_for_health(
    config: ServiceConfig,
    process: Popen,
    timeout_seconds: int = 30,
    *,
    scheme: str = "http",
    verify_ssl: bool = True,
) -> bool:
    """在超时时间内轮询服务健康状态。"""
    deadline = time.time() + timeout_seconds
    url = f"{scheme}://127.0.0.1:{config.port}{config.health_path}"
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            response = requests.get(url, timeout=2, verify=verify_ssl)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def stop_all(processes: List[Popen]) -> None:
    """终止所有仍在运行的子进程。"""
    for proc in processes:
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                continue
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass


def run_service_child(script_rel: str, args: List[str]) -> None:
    configure_stdio()
    script_path = BUNDLE_ROOT / Path(script_rel)
    if not script_path.exists():
        print(f"\u274c \u65e0\u6cd5\u627e\u5230\u670d\u52a1\u811a\u672c: {script_path}")
        sys.exit(1)
    sys.argv = [str(script_path), *args]
    runpy.run_path(str(script_path), run_name="__main__")


def print_banner() -> None:
    print("\n" + "=" * 60)
    print("\U0001F680  ZhiYUAI \u5fae\u670d\u52a1\u4e00\u952e\u542f\u52a8\u5668")
    print("=" * 60)


def main() -> None:
    configure_stdio()
    print_banner()

    env_path = PROJECT_ROOT / ".env"
    env_vars = load_env_file(env_path)
    if env_vars:
        print(f"\U0001F4E6 \u5df2\u52a0\u8f7d\u73af\u5883\u914d\u7f6e: {env_path}")
    else:
        print("\u2139\ufe0f \u672a\u627e\u5230 .env\uff0c\u4f7f\u7528\u5f53\u524d\u7ec8\u7aef\u73af\u5883\u3002")

    if "DASHSCOPE_API_KEY" not in env_vars and "USE_MOCK_AI" not in os.environ:
        print("\U0001F4A1 \u672a\u68c0\u6d4b\u5230 DashScope API Key\uff0c\u5df2\u9ed8\u8ba4\u542f\u7528 Mock \u6a21\u5f0f\u3002")
        env_vars.setdefault("USE_MOCK_AI", "1")

    processes: List[Popen] = []

    try:
        for config in SERVICES:
            if not config.script.exists():
                print(f"\u274c \u627e\u4e0d\u5230 {config.name} \u811a\u672c: {config.script}")
                continue

            print(f"\n\u25b6\ufe0f \u6b63\u5728\u542f\u52a8 {config.name} ({config.port}) ...", flush=True)
            service_env = env_vars.copy()
            service_env["PORT"] = str(config.port)
            service_env.setdefault("HOST", "0.0.0.0")

            process = start_service(config, service_env)
            processes.append(process)

            env_prefix = config.script.parent.name.upper().replace("-", "_")
            cert_env = None
            if not _tls_disabled(service_env, env_prefix):
                cert_env = service_env.get(f"{env_prefix}_SSL_CERTFILE") or service_env.get("SSL_CERTFILE")
            scheme = "https" if cert_env else "http"
            verify_ssl = False if scheme == "https" else True

            if wait_for_health(config, process, scheme=scheme, verify_ssl=verify_ssl):
                print(
                    f"\u2705 {config.name} \u5df2\u5c31\u7eea: "
                    f"{scheme}://127.0.0.1:{config.port}{config.health_path}"
                )
            else:
                print(
                    f"\u26a0\ufe0f {config.name} \u672a\u5728\u9884\u671f\u65f6\u95f4\u5185\u901a\u8fc7\u5065\u5eb7\u68c0\u67e5\uff0c"
                    f"\u8bf7\u9605\u89c6\u7ec8\u7aef\u65e5\u5fd7\u3002"
                )

        running = [proc for proc in processes if proc.poll() is None]
        if running:
            print("\n\U0001F3AF \u6240\u6709\u670d\u52a1\u5df2\u5c1d\u8bd5\u542f\u52a8\uff0c\u53ef\u6267\u884c `python final_demo.py` \u7ec8\u7aef\u6f14\u793a\u3002")
            print("\U0001F6D1 \u82e5\u9700\u9000\u51fa\uff0c\u8bf7\u5728\u672c\u7ec8\u7aef\u6309 Ctrl+C\u3002")
        else:
            print("\n\u26a0\ufe0f \u672a\u68c0\u6d4b\u5230\u6b63\u5728\u8fd0\u884c\u7684\u670d\u52a1\uff0c\u8bf7\u6839\u636e\u4e0a\u6587\u63d0\u793a\u6392\u67e5\u3002")

        while running:
            time.sleep(1)
            running = [proc for proc in processes if proc.poll() is None]

    except KeyboardInterrupt:
        print("\n\U0001F9F9 \u6b63\u5728\u505c\u6b62\u6240\u6709\u670d\u52a1 ...")
    finally:
        stop_all(processes)
        print("\U0001F44B \u5df2\u9000\u51fa\u3002")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-service":
        if len(sys.argv) < 3:
            print("⚠️ --run-service 需要提供脚本路径", file=sys.stderr)
            sys.exit(2)
        run_service_child(sys.argv[2], sys.argv[3:])
        sys.exit(0)
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
