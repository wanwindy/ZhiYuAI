# 🌍 ZhiYUAI 2.0

[English Version](README_EN.md) · [MIT License](LICENSE)

ZhiYUAI 2.0 将原有的单体翻译系统升级为语音 + 文本 + 图像协同的智能翻译平台，底层基于 Starlette/Uvicorn、DashScope 以及可插拔的 AI Router。仓库同时提供 Python 脚本、Docker Compose 与独立可执行文件，方便在 HR 演示或本地评估时快速复现全套体验。

---

## ✨ 核心亮点

- **实时语音交互**：集成 DashScope 实时 ASR、翻译与 TTS，支持 REST/SSE/WebSocket 三种模式（`services/voice-interaction`）。
- **多引擎路由**：AI Router 根据任务类型与优先级自动挑选最优模型组合，同时内置 Mock 模式便于离线演示（`services/ai-router`）。
- **视觉/对话协同**：场景识别服务将摄像头画面与对话上下文融合，动态生成翻译策略与推荐语气（`services/scene-recognition`）。
- **文本翻译 API**：单次翻译、批量翻译、质量评估、引擎推荐统一在 REST 接口中（`services/translation`）。
- **一键脚本 + Demo**：`start_services.py`/`final_demo.py` 负责快速启动与端到端演示，`test_database_integration.py` 提供可运行的数据库示例。
- **内存数据库实现**：`shared/database` 默认以内存结构模拟 PostgreSQL API，在没有数据库权限时也能运行；需要真实库时可按文档替换。

---

## 🗂️ 仓库结构

```
services/               # translation / ai-router / scene-recognition / voice-interaction
shared/                 # DashScope & OpenAI 封装、TLS 辅助、内存数据库等共享模块
web/                    # 简易 Web 控制台（静态资源 + 调试服务器）
docs/                   # 架构、数据库、产品规划等文档
infrastructure/         # 数据库脚本、监控配置
demo_assets/            # 演示音频、图片素材
dist/                   # PyInstaller 生成的一键启动程序
```

---

## ⚙️ 环境准备

| 组件             | 版本建议 | 说明                                         |
|------------------|----------|----------------------------------------------|
| Python           | 3.9+     | 推荐使用 venv/conda 虚拟环境                 |
| Node.js          | 16+      | 仅在调试 `web/` 前端页面时需要               |
| Docker Compose   | 2.x      | 可选，一键启动依赖数据库/服务                |
| PostgreSQL 13+   | 可选     | 如需真实数据库，运行 `install_and_setup.py`  |
| Redis / RabbitMQ | 可选     | `docker-compose.yml` 中提供默认服务定义      |

---

## 🚀 快速上手

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate      # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
copy .env.example .env      # Linux/Mac: cp .env.example .env
```

`.env.example` 仅包含示例键值，请在 `.env` 中填入 DashScope 等真实凭据；`.env` 已加入 `.gitignore`，不会被提交。若留空，服务会自动启用 Mock 模式，适合离线演示。

### 3. 初始化数据库（可选）

```bash
python install_and_setup.py
```

脚本将创建 PostgreSQL 表并写入默认配置；只使用内存数据库时可跳过。

### 4. 启动核心服务

```bash
python start_services.py        # 顺序启动四个微服务
python final_demo.py            # 终端内演示完整流程

# 或使用 Docker
make dev-up                     # 依赖 docker-compose
```

---

## 🧪 测试与演示

```bash
pytest                                  # 运行全部 Python 测试
python test_database_integration.py     # 校验内存/数据库集成示例
python final_demo.py                    # 端到端演示脚本
```

---

## 🔍 调试 & 运维

- 查看服务日志：`make logs SERVICE=translation`
- 启动本地 Web 控制台：`python web/server.py --port 3000`
- 监控栈（Prometheus/Grafana）配置位于 `infrastructure/monitoring/`

---

## 🤝 定制与扩展

- 需要接入真实数据库时，可按照 `docs/database-integration-guide.md` 的结构替换 `shared/database` 内的内存实现。
- 所有服务默认兼容 Mock 模式：未配置 DashScope Key 时自动返回内置示例，方便在无网络或无凭据的环境快速演示。
- 可根据 HR 场景裁剪 Docker Compose、Make 命令或 PyInstaller 打包脚本，打造更轻量的演示版本。

---

> Looking for English docs? Please read [README_EN.md](README_EN.md).
