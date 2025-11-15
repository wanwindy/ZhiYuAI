#!/usr/bin/env python3
"""简易 HTTP 服务器，用于托管 ZhiYUAI Web 客户端。"""

from __future__ import annotations

import argparse
import os
import socketserver
import ssl
import sys
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.server import resolve_ssl_paths  # noqa: E402


class CORSRequestHandler(SimpleHTTPRequestHandler):
    """支持跨域的静态文件服务处理器。"""

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()


class ThreadingCORSHTTPServer(socketserver.ThreadingTCPServer):
    """允许地址复用的线程安全 HTTP 服务器。"""

    allow_reuse_address = True
    daemon_threads = True


def run_server(port: int, host: str, certfile: Optional[str] = None, keyfile: Optional[str] = None) -> None:
    """在指定端口启动静态文件服务器，可选启用 HTTPS。"""
    web_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(web_root)

    server_address = (host, port)
    with ThreadingCORSHTTPServer(server_address, CORSRequestHandler) as httpd:
        env_cert, env_key = (None, None)
        if not certfile:
            env_cert, env_key = resolve_ssl_paths("web")
            if env_cert:
                certfile = env_cert
            if env_key and not keyfile:
                keyfile = env_key

        scheme = "http"
        if certfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile, keyfile or certfile)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            scheme = "https"

        listen_host = host or "0.0.0.0"
        display_host = listen_host if listen_host not in {"0.0.0.0", ""} else "localhost"

        print("ZhiYUAI Web 控制台已启动")
        print(f"监听地址: {listen_host}:{port}")
        print(f"访问地址: {scheme}://{display_host}:{port}")
        if listen_host in {"0.0.0.0", ""}:
            print("局域网访问请使用服务器内网 IP 或主机名。")
        if certfile:
            print(f"已启用 HTTPS，证书: {certfile}")

        print("功能概览:")
        print("  • 文本翻译与语音播报")
        print("  • 麦克风录音翻译")
        print("  • 摄像头场景识别")
        print("按下 Ctrl+C 可停止服务")
        print("-" * 60)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已退出")
            sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 ZhiYUAI Web 客户端")
    parser.add_argument("--port", type=int, default=3000, help="监听端口（默认: 3000）")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址（默认: 0.0.0.0）")
    parser.add_argument("--certfile", help="启用 HTTPS 时的证书文件路径")
    parser.add_argument("--keyfile", help="启用 HTTPS 时的私钥文件路径（默认同证书文件）")
    args = parser.parse_args()
    run_server(args.port, args.host, args.certfile, args.keyfile)


if __name__ == "__main__":
    main()
