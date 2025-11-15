#!/usr/bin/env python3
"""
ZhiYUAI 2.0 微服务启动脚本 - 中文版
一键启动所有微服务并进行健康检查
"""

import subprocess
import sys
import time
import os
import signal
import threading
from datetime import datetime
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 设置项目根目录
project_root = Path(__file__).parent
os.chdir(project_root)

# 设置环境变量
os.environ["DATABASE_URL"] = "postgresql://postgres:123456@localhost:5432/gummy_translator"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RABBITMQ_URL"] = "amqp://admin:admin123@localhost:5672/"

# 日志文件
LOG_FILE = project_root / "log.md"

TLS_TRUTHY = {"1", "true", "yes", "on"}
TLS_FALSY = {"0", "false", "no", "off"}

def _append_log(line: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")
    except Exception:
        pass

def _init_log():
    header = (
        f"# 启动日志\n\n"
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    try:
        LOG_FILE.write_text(header, encoding="utf-8")
    except Exception:
        # 若写入失败，不影响控制台输出
        pass

def print_header(title: str):
    """打印标题"""
    banner = f"\n{'=' * 60}\n*** {title} ***\n{'=' * 60}"
    print(banner)
    _append_log(banner)

def print_section(title: str):
    """打印子标题"""
    section = f"\n## {title}\n{'-' * 40}"
    print(section)
    _append_log(section)

def _stream_process_output(proc: subprocess.Popen, service_name: str):
    """将子进程输出写入 log.md 并回显到控制台"""
    if proc.stdout is None:
        return
    for line in proc.stdout:
        text = line.rstrip("\n")
        prefixed = f"[{service_name}] {text}"
        print(prefixed)
        _append_log(prefixed)

def start_service(service_name: str, service_path: Path, port: int) -> Optional[subprocess.Popen]:
    """启动单个服务"""
    msg = f"正在启动 {service_name} (端口 {port})..."
    print(msg)
    _append_log(msg)

    try:
        # 检查服务文件是否存在
        if not service_path.exists():
            err = f"错误: 服务文件不存在: {service_path}"
            print(err)
            _append_log(err)
            return None

        # 启动服务
        env = os.environ.copy()
        env["PORT"] = str(port)
        env["HOST"] = "0.0.0.0"
        process = subprocess.Popen(
            [sys.executable, str(service_path)],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        ok = f"{service_name} 启动成功 (PID: {process.pid})"
        print(ok)
        _append_log(ok)

        # 异步读取日志
        t = threading.Thread(target=_stream_process_output, args=(process, service_name), daemon=True)
        t.start()
        return process

    except Exception as e:
        err = f"{service_name} 启动失败: {e}"
        print(err)
        _append_log(err)
        return None


def _service_uses_tls(service: Dict[str, Any]) -> bool:
    """Return True if TLS should be enabled for the given service."""
    prefix = service.get("env_prefix")
    disable_flags = []
    enable_flags = []
    if prefix:
        disable_flags.append(f"{prefix}_SSL_DISABLE")
        enable_flags.append(f"{prefix}_SSL_ENABLED")
    disable_flags.append("SSL_DISABLE")
    enable_flags.append("SSL_ENABLED")

    for name in disable_flags:
        value = os.environ.get(name)
        if value and value.strip().lower() in TLS_TRUTHY:
            return False
    for name in enable_flags:
        value = os.environ.get(name)
        if value and value.strip().lower() in TLS_FALSY:
            return False

    cert_candidates = []
    if prefix:
        cert_candidates.append(f"{prefix}_SSL_CERTFILE")
    cert_candidates.append("SSL_CERTFILE")

    for key in cert_candidates:
        value = os.environ.get(key)
        if value and value.strip():
            return True
    return False


def check_service_health(service: Dict[str, Any], timeout: int = 5) -> bool:
    """检查服务健康状态"""
    import requests

    port = service["port"]
    service_name = service["name"]
    scheme = "https" if _service_uses_tls(service) else "http"
    verify_ssl = False if scheme == "https" else True

    try:
        response = requests.get(f"{scheme}://localhost:{port}/health", timeout=timeout, verify=verify_ssl)
        if response.status_code == 200:
            msg = f"{service_name} 健康检查通过"
            print(msg)
            _append_log(msg)
            return True
        else:
            msg = f"{service_name} 健康检查失败: HTTP {response.status_code}"
            print(msg)
            _append_log(msg)
            return False
    except Exception as e:
        err = f"{service_name} 连接失败: {e}"
        print(err)
        _append_log(err)
        return False

def stop_service(process: subprocess.Popen, service_name: str) -> bool:
    """停止单个服务"""
    try:
        if process.poll() is None:  # 进程还在运行
            print(f"正在停止 {service_name}...")

            # 先尝试正常终止
            process.terminate()

            # 等待进程结束
            try:
                process.wait(timeout=5)
                msg = f"{service_name} 已正常停止"
                print(msg)
                _append_log(msg)
                return True
            except subprocess.TimeoutExpired:
                msg = f"{service_name} 正在强制终止..."
                print(msg)
                _append_log(msg)
                process.kill()
                done = f"{service_name} 已强制停止"
                print(done)
                _append_log(done)
                return True

        return False

    except Exception as e:
        err = f"停止 {service_name} 时出错: {e}"
        print(err)
        _append_log(err)
        return False

def main():
    """主函数"""
    _init_log()
    print_header("ZhiYUAI 2.0 微服务启动器")

    # 服务配置
    services = [
        {
            "name": "AI路由服务",
            "path": project_root / "services" / "ai-router" / "main.py",
            "port": 8001,
            "description": "智能路由服务，管理多个AI引擎",
            "env_prefix": "AI_ROUTER",
        },
        {
            "name": "翻译服务",
            "path": project_root / "services" / "translation" / "main.py",
            "port": 8002,
            "description": "文本翻译服务，支持多语言翻译",
            "env_prefix": "TRANSLATION",
        },
        {
            "name": "场景识别服务",
            "path": project_root / "services" / "scene-recognition" / "main.py",
            "port": 8003,
            "description": "场景识别服务，智能识别使用场景",
            "env_prefix": "SCENE_RECOGNITION",
        },
        {
            "name": "语音交互服务",
            "path": project_root / "services" / "voice-interaction" / "main.py",
            "port": 8004,
            "description": "语音交互服务，支持语音识别和合成",
            "env_prefix": "VOICE_INTERACTION",
        }
    ]

    processes = []

    # 启动服务前检查
    print_section("启动前检查")
    print("正在检查服务配置...")
    _append_log("正在检查服务配置...")

    for service in services:
        lines = [
            f"   - {service['name']}: {service['description']}",
            f"   - 端口: {service['port']}",
            f"   - 文件: {service['path']}",
        ]
        for l in lines:
            print(l)
            _append_log(l)

        if not service['path'].exists():
            msg = "   文件不存在，跳过启动"
            print(msg)
            _append_log(msg)
        else:
            msg = "   文件存在，准备启动"
            print(msg)
            _append_log(msg)
        print()

    # 启动所有服务
    print_section("启动微服务")
    print("正在依次启动所有服务...")
    _append_log("正在依次启动所有服务...")

    def is_port_in_use(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", p)) == 0

    def find_free_port(start: int, limit: int = 100) -> Optional[int]:
        for p in range(start, start + limit):
            if not is_port_in_use(p):
                return p
        return None

    for i, service in enumerate(services, 1):
        step = f"\n启动第 {i}/{len(services)} 个服务"
        print(step)
        _append_log(step)

        if service['path'].exists():
            desired_port = service["port"]
            if is_port_in_use(desired_port):
                # 尝试在 1000 偏移后寻找空闲端口
                alt = find_free_port(desired_port + 1000)
                if alt is None:
                    msg = (
                        f"端口 {desired_port} 被占用，且未找到可用端口，跳过 {service['name']} 启动。"
                    )
                    print(msg)
                    _append_log(msg)
                    continue
                info = f"端口 {desired_port} 被占用，将改用 {alt} 启动 {service['name']}"
                print(info)
                _append_log(info)
                service["port"] = alt
            process = start_service(service["name"], service["path"], service["port"])
            if process:
                processes.append((process, service))
                time.sleep(2)  # 等待服务启动
        else:
            msg = f"跳过 {service['name']}，文件不存在"
            print(msg)
            _append_log(msg)

    if not processes:
        print("错误: 没有服务成功启动")
        _append_log("错误: 没有服务成功启动")
        return

    info = f"已启动 {len(processes)} 个服务"
    print(info)
    _append_log(info)

    # 等待服务完全启动
    print_section("等待服务完全启动")
    print("等待服务启动完成...")
    _append_log("等待服务启动完成...")
    time.sleep(10)

    # 检查服务健康状态
    print_section("服务健康检查")
    print("正在检查所有服务的健康状态...")
    _append_log("正在检查所有服务的健康状态...")

    try:
        import requests

        healthy_services = 0
        for process, service in processes:
            line = f"\n检查 {service['name']} (端口 {service['port']})..."
            print(line)
            _append_log(line)
            if check_service_health(service):
                healthy_services += 1

        print(f"\n服务健康状态总结:")
        _append_log("\n服务健康状态总结:")
        s1 = f"   健康服务: {healthy_services}/{len(processes)}"
        s2 = f"   异常服务: {len(processes) - healthy_services}/{len(processes)}"
        print(s1); _append_log(s1)
        print(s2); _append_log(s2)

        if healthy_services == len(processes):
            print("所有服务都健康运行！"); _append_log("所有服务都健康运行！")
        elif healthy_services > 0:
            print("部分服务运行正常"); _append_log("部分服务运行正常")
        else:
            print("所有服务都未正常启动"); _append_log("所有服务都未正常启动")

    except ImportError:
        print("警告: 未安装 requests 库，跳过健康检查")
        print("可以手动访问以下URL检查服务状态:")
        _append_log("警告: 未安装 requests 库，跳过健康检查")
        _append_log("可以手动访问以下URL检查服务状态:")
        for process, service in processes:
            scheme = "https" if _service_uses_tls(service) else "http"
            url = f"   {scheme}://localhost:{service['port']}/health"
            print(url)
            _append_log(url)

    # 显示服务信息和操作指南
    print_section("服务运行信息")
    print("当前运行中的服务:")
    _append_log("当前运行中的服务:")

    for process, service in processes:
        status = "运行中" if process.poll() is None else "已停止"
        scheme = "https" if _service_uses_tls(service) else "http"
        base_url = f"{scheme}://localhost:{service['port']}"
        lines = [
            f"   {service['name']}:",
            f"      - 访问地址: {base_url}",
            f"      - 健康检查: {base_url}/health",
            f"      - 状态: {status}",
            f"      - PID: {process.pid}",
        ]
        for l in lines:
            print(l)
            _append_log(l)
        print()

    # 显示API端点信息
    print_section("API端点信息")
    print("主要API接口:")
    _append_log("主要API接口:")
    def _print_api(label: str, method: str, env_prefix: str, path: str) -> None:
        service = next((svc for svc in services if svc.get("env_prefix") == env_prefix), None)
        if not service:
            return
        scheme = "https" if _service_uses_tls(service) else "http"
        url = f"{scheme}://localhost:{service['port']}{path}"
        line = f"   {label}:     {method} {url}"
        print(line)
        _append_log(line)

    _print_api("翻译接口", "POST", "TRANSLATION", "/translate")
    _print_api("质量评估", "POST", "TRANSLATION", "/quality/assess")
    _print_api("引擎选择", "POST", "TRANSLATION", "/engine/select")
    _print_api("批量翻译", "POST", "TRANSLATION", "/translate/batch")
    _print_api("场景识别", "POST", "SCENE_RECOGNITION", "/recognize")
    _print_api("AI路由", "POST", "AI_ROUTER", "/route")
    _print_api("语音识别", "POST", "VOICE_INTERACTION", "/voice/recognize")
    _print_api("语音翻译", "POST", "VOICE_INTERACTION", "/voice/translate")
    print(f"   TTS合成:       POST http://localhost:8004/tts")

    # 使用说明
    print_section("使用说明")
    print("测试和操作建议:")
    _append_log("测试和操作建议:")
    print("   1. 打开新终端，使用curl或Postman测试API接口")
    print("   2. 查看当前终端的服务日志输出")
    print("   3. 按 Ctrl+C 停止所有服务")
    print("   4. 访问 /docs 查看API文档")

    # 启动完成提示
    print_section("启动完成")
    print("ZhiYUAI 2.0 微服务启动器已启动")
    print(f"服务总数: {len(processes)} 个")
    print(f"项目根目录: {project_root}")
    print(f"会话ID: {int(time.time())}")
    _append_log("ZhiYUAI 2.0 微服务启动器已启动")
    _append_log(f"服务总数: {len(processes)} 个")
    _append_log(f"项目根目录: {project_root}")
    _append_log(f"会话ID: {int(time.time())}")

    print(f"\n按 Ctrl+C 停止所有服务...")
    print("-" * 60)
    _append_log("")
    _append_log("按 Ctrl+C 停止所有服务...")

    # 主循环，等待用户中断
    try:
        while True:
            time.sleep(1)
            # 检查进程是否还在运行
            running_count = sum(1 for process, _ in processes if process.poll() is None)

            if running_count == 0:
                print("所有服务都已停止")
                _append_log("所有服务都已停止")
                break

    except KeyboardInterrupt:
        print(f"\n用户中断，正在停止所有服务...")
        _append_log("用户中断，正在停止所有服务...")

        # 停止所有进程
        stopped_count = 0
        for process, service in processes:
            if stop_service(process, service["name"]):
                stopped_count += 1

        print(f"\n服务停止总结:")
        _append_log("\n服务停止总结:")
        s1 = f"   成功停止: {stopped_count}/{len(processes)} 个服务"
        s2 = f"   停止失败: {len(processes) - stopped_count}/{len(processes)} 个服务"
        print(s1); _append_log(s1)
        print(s2); _append_log(s2)

        if stopped_count == len(processes):
            print("所有服务已成功停止"); _append_log("所有服务已成功停止")
        else:
            print("部分服务可能仍在运行"); _append_log("部分服务可能仍在运行")

    print("ZhiYUAI 2.0 微服务启动器已退出")
    _append_log("ZhiYUAI 2.0 微服务启动器已退出")

if __name__ == "__main__":
    main()
