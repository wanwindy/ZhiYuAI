#!/usr/bin/env python3
"""
ZhiYUAI 终端演示脚本（中文版）

通过命令行串联各个微服务，演示文本翻译、场景识别、
语音翻译与语音合成功能，便于快速体验系统能力。
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print("⚠️ 未检测到 requests 库，请先执行: pip install requests", file=sys.stderr)
    sys.exit(1)


def configure_stdio() -> None:
    """Force UTF-8 console output; replace unsupported characters."""
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


IS_FROZEN = getattr(sys, "frozen", False)
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
OUTPUT_ROOT = Path.cwd()


class FinalTranslatorDemo:
    """负责组织所有演示流程的控制器。"""

    def __init__(self) -> None:
        # 微服务基础地址
        self.base_urls: Dict[str, str] = {
            "translation": "http://localhost:8002",
            "ai_router": "http://localhost:8001",
            "scene_recognition": "http://localhost:8003",
            "voice_interaction": "http://localhost:8004",
        }

        # 会话标识
        self.session_id = f"demo-session-{int(time.time())}"
        self.user_id = "demo-user"

        # 支持的语言映射
        self.supported_languages: Dict[str, str] = {
            "zh": "中文",
            "en": "英语",
            "ja": "日语",
            "ko": "韩语",
            "fr": "法语",
            "de": "德语",
            "es": "西班牙语",
            "ru": "俄语",
            "ar": "阿拉伯语",
            "pt": "葡萄牙语",
        }

        self.bundle_assets_dir = BUNDLE_ROOT / "demo_assets"
        self.assets_dir = OUTPUT_ROOT / "demo_assets"
        self.assets_dir.mkdir(exist_ok=True)
        self.sample_audio_name = "hello_world_female2.wav"
        self.sample_audio_path = self.assets_dir / self.sample_audio_name
        self.tts_output_path = self.assets_dir / "demo_tts_output.wav"

    def print_header(self, title: str) -> None:
        """打印演示大标题。"""
        print(f"\n{'=' * 60}")
        print(f"*** {title} ***")
        print(f"{'=' * 60}")

    def print_section(self, title: str) -> None:
        """打印章节标题，便于分段阅读。"""
        print(f"\n### {title}")
        print("-" * 40)

    def post_json(
        self,
        service: str,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """向指定服务发送 JSON 请求，并在出现错误时抛出异常。"""
        url = f"{self.base_urls[service]}{endpoint}"
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if not data.get("success", False):
            raise RuntimeError(f"服务返回错误: {data.get('error') or data}")
        return data["data"]

    def ensure_sample_audio(self) -> None:
        """确保示例音频已下载到本地。"""
        if self.sample_audio_path.exists():
            return
        bundled = self.bundle_assets_dir / self.sample_audio_name
        if bundled.exists():
            self.sample_audio_path.write_bytes(bundled.read_bytes())
            return
        audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/paraformer/hello_world_female2.wav"
        print(f"正在下载示例音频: {audio_url}")
        resp = requests.get(audio_url, timeout=30)
        resp.raise_for_status()
        self.sample_audio_path.write_bytes(resp.content)

    @staticmethod
    def load_audio_base64(path: Path) -> str:
        """读取音频文件并转换为 Base64 字符串。"""
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    @staticmethod
    def save_audio_base64(audio_base64: str, output_path: Path) -> Path:
        """保存 Base64 编码的音频到指定路径。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(audio_base64.encode("utf-8"))
        output_path.write_bytes(raw)
        return output_path

    def check_service_health(self) -> Dict[str, bool]:
        """检查各微服务的健康状态并输出结果。"""
        status: Dict[str, bool] = {}
        for service_name, url in self.base_urls.items():
            try:
                resp = requests.get(f"{url}/health", timeout=3)
                healthy = resp.status_code == 200
                status[service_name] = healthy
                print(f"[{'+' if healthy else '-'}] {service_name}: {'健康' if healthy else '异常'}")
            except Exception:
                status[service_name] = False
                print(f"[-] {service_name}: 无法连接")
        return status

    def text_translation_demo(self) -> None:
        """文本翻译服务演示。"""
        self.print_section("文本翻译功能演示")

        cases = [
            {
                "text": "Hello, how are you today?",
                "source_lang": "en",
                "target_lang": "zh",
                "description": "日常问候示例",
            },
            {
                "text": "The weather is really nice today",
                "source_lang": "en",
                "target_lang": "zh",
                "description": "天气表达示例",
            },
        ]

        for index, case in enumerate(cases, 1):
            print(f"\n--- 用例 {index} ---")
            print(f"原文: {case['text']}")
            print(
                f"语种: {self.supported_languages[case['source_lang']]} -> "
                f"{self.supported_languages[case['target_lang']]}"
            )
            print(f"场景: {case['description']}")

            translation_request = {
                "text": case["text"],
                "source_language": case["source_lang"],
                "target_language": case["target_lang"],
                "mode": "standard",
                "user_id": self.user_id,
                "session_id": self.session_id,
            }

            try:
                print("调用翻译服务 /translate ...")
                result = self.post_json("translation", "/translate", translation_request)
                print("翻译输出:")
                print(f"  -> {result['translated_text']}")
                print(f"  引擎: {result['engine']} | 置信度: {result.get('confidence', 0.0):.2%}")

                qa_payload = {
                    "source_text": case["text"],
                    "translated_text": result["translated_text"],
                }
                quality = self.post_json("translation", "/quality/assess", qa_payload)
                print(
                    f"  质量评估: {quality.get('quality_score', 0.0):.2f} | 反馈: {quality.get('notes')}"
                )
            except Exception as exc:
                print(f"翻译失败: {exc}")

    def scenario_dialogue_demo(self) -> None:
        """场景对话服务演示。"""
        self.print_section("场景对话功能演示")

        scenarios = [
            {
                "name": "商务会议",
                "keywords": ["meeting", "negotiation", "cooperation", "business"],
                "description": "正式、专业的商务沟通场景",
            },
            {
                "name": "旅行问路",
                "keywords": ["travel", "hotel", "attraction", "direction"],
                "description": "轻松友好的旅途问询场景",
            },
        ]

        image_samples = [
            "https://img.alicdn.com/imgextra/i3/O1CN01K3SgGo1eqmlUgeE9b_!!6000000003923-0-tps-3840-2160.jpg",
            "https://img.alicdn.com/imgextra/i4/O1CN01BjZvwg1Y23CF5qIRB_!!6000000003000-0-tps-3840-2160.jpg",
        ]

        print("\n场景识别演示:")
        for index, scenario in enumerate(scenarios, 1):
            print(f"\n场景 {index}: {scenario['name']}")
            print(f"关键词: {', '.join(scenario['keywords'])}")
            print(f"说明: {scenario['description']}")

            recognition_request = {
                "image_urls": image_samples,
                "prompt": f"根据这些画面判断是否属于{scenario['name']}场景，并给出翻译策略建议。",
            }

            try:
                print("调用场景识别服务 /recognize ...")
                result = self.post_json("scene_recognition", "/recognize", recognition_request)
                print(
                    f"  场景识别: {result.get('scenario_name')} | 置信度: {result.get('confidence')}"
                )
                print(f"  推荐策略: {result.get('recommended_settings')}")

                analysis_payload = {"context_text": scenario["description"]}
                analysis = self.post_json("scene_recognition", "/analyze", analysis_payload)
                print(f"  文本情感分析: {analysis}")
            except Exception as exc:
                print(f"场景识别失败: {exc}")

    def show_system_overview(self) -> None:
        """打印系统核心能力概览。"""
        self.print_section("ZhiYUAI 2.0 系统概览")
        print("\n核心特性:")
        print("1. 智能语音交互 —— 实时语音识别、翻译与合成能力")
        print("2. 自适应场景 —— 自动识别沟通场景并调整策略")
        print("3. 多引擎融合 —— 支持阿里云、硅基流动等多家模型服务")
        print("4. 多模态输入 —— 同时处理文本、语音、图像等内容")
        print("5. 企业级部署 —— 微服务架构，高并发与可扩展性保障")

    def voice_interaction_demo(self) -> None:
        """语音交互服务演示（ASR + 翻译 + TTS）。"""
        self.print_section("语音交互功能演示")

        try:
            self.ensure_sample_audio()
        except Exception as exc:
            print(f"下载示例音频失败: {exc}")
            return

        audio_b64 = self.load_audio_base64(self.sample_audio_path)
        translate_payload = {
            "audio_base64": audio_b64,
            "target_language": "en",
        }

        try:
            print("调用语音翻译服务 /voice/translate ...")
            translation = self.post_json(
                "voice_interaction",
                "/voice/translate",
                translate_payload,
                timeout=90.0,
            )
            print(f"  请求 ID: {translation['request_id']}")
            print(f"  转写结果: {translation['transcripts']}")
            print(f"  翻译结果: {translation.get('translations')}")
        except Exception as exc:
            print(f"语音翻译失败: {exc}")
            return

        tts_text = "ZhiYUAI 实时翻译演示完成，感谢观看！"
        tts_payload = {"text": tts_text}

        try:
            print("调用语音合成服务 /tts ...")
            tts_result = self.post_json("voice_interaction", "/tts", tts_payload)
            audio_path = self.save_audio_base64(tts_result["audio_base64"], self.tts_output_path)
            print(f"  合成完成，文件已保存至: {audio_path.resolve()}")
        except Exception as exc:
            print(f"TTS 合成失败: {exc}")

    def show_api_endpoints(self) -> None:
        """展示可用的 REST 接口列表。"""
        self.print_section("可用 API 列表")

        endpoints = [
            {
                "service": "翻译服务",
                "url": "http://localhost:8002",
                "endpoints": [
                    "POST /translate —— 文本翻译",
                    "POST /translate/batch —— 批量翻译",
                    "POST /quality/assess —— 翻译质量评估",
                    "GET  /engines —— 引擎列表",
                ],
            },
            {
                "service": "场景识别服务",
                "url": "http://localhost:8003",
                "endpoints": [
                    "POST /recognize —— 场景识别",
                    "GET  /scenarios —— 场景枚举",
                    "POST /analyze —— 文本语境分析",
                ],
            },
            {
                "service": "AI 路由服务",
                "url": "http://localhost:8001",
                "endpoints": [
                    "POST /route —— 智能引擎路由",
                    "GET  /engines —— 引擎状态",
                    "POST /benchmark —— 性能总结",
                ],
            },
            {
                "service": "语音交互服务",
                "url": "http://localhost:8004",
                "endpoints": [
                    "POST /voice/recognize —— 语音识别",
                    "POST /voice/translate —— 语音翻译",
                    "POST /tts —— 文本转语音",
                ],
            },
        ]

        for endpoint in endpoints:
            print(f"\n{endpoint['service']} ({endpoint['url']})")
            for api in endpoint["endpoints"]:
                print(f"   {api}")

    def run_complete_demo(self) -> None:
        """串联执行完整演示流程。"""
        self.print_header("ZhiYUAI 2.0 终端演示")

        self.show_system_overview()

        self.print_section("服务健康检查")
        health_status = self.check_service_health()

        self.text_translation_demo()
        self.scenario_dialogue_demo()
        self.voice_interaction_demo()

        self.show_api_endpoints()

        self.print_section("演示总结")
        healthy_count = sum(1 for ok in health_status.values() if ok)
        total_count = len(health_status)

        print("演示已完成。")
        print(f"服务状态: {healthy_count}/{total_count} 项服务健康")
        print(f"Session ID: {self.session_id}")
        print(f"User ID: {self.user_id}")

        if healthy_count < total_count:
            print("\n提示: 部分服务未成功启动，可以尝试以下方式:")
            print("   - 使用 Docker Compose: docker-compose up -d")
            print("   - 使用 Python 脚本: python start_services.py")
            print("   - 或者手动逐个启动微服务主程序")

        print("\n更多信息请查看 README.md")


def main() -> None:
    """脚本入口。"""
    configure_stdio()
    demo = FinalTranslatorDemo()
    demo.run_complete_demo()


if __name__ == "__main__":
    main()
