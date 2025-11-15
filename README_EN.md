# 🌍 ZhiYUAI 2.0

[中文版本](README.md) · [MIT License](LICENSE)

ZhiYUAI 2.0 upgrades the original single-tenant translator into a multimodal platform that understands speech, text, and images. It is built with Starlette/Uvicorn, DashScope, and a pluggable AI Router so you can switch between real providers and mock responses with a single `.env` flag. This repository ships Python scripts, Docker Compose manifests, and standalone executables, making it easy to demo to HR or evaluate locally.

---

## ✨ Highlights

- **Realtime voice interaction**: combines DashScope ASR, translation, and TTS with REST/SSE/WebSocket endpoints (`services/voice-interaction`).
- **AI routing layer**: automatically selects the best model combo based on scenario & priority, with a built-in mock mode for offline demos (`services/ai-router`).
- **Scene-aware assistants**: merges camera frames with dialogue context and generates translation strategies along with tone suggestions (`services/scene-recognition`).
- **Text translation API**: single requests, batch jobs, quality scoring, and engine recommendations under a unified REST interface (`services/translation`).
- **One-click scripts & demos**: `start_services.py` kicks off all core microservices, `final_demo.py` runs an end-to-end terminal showcase, and `test_database_integration.py` validates the shared database layer.
- **In-memory database**: `shared/database` mimics the PostgreSQL API entirely in memory, so the project works even without a DB. Swap it with a real driver at deployment time.

---

## 🗂️ Repository Layout

```
services/               # translation / ai-router / scene-recognition / voice-interaction
shared/                 # DashScope & OpenAI clients, TLS helpers, in-memory DB
web/                    # lightweight web console (static assets + dev server)
docs/                   # architecture and product documents
infrastructure/         # database scripts, monitoring configs
demo_assets/            # sample audio/image files for demos
dist/                   # PyInstaller build artifacts (one-click launcher)
```

---

## ⚙️ Prerequisites

| Component         | Version  | Notes                                                     |
|-------------------|----------|-----------------------------------------------------------|
| Python            | 3.9+     | Use venv/conda if possible                                |
| Node.js           | 16+      | Only required when hacking on the `web/` UI               |
| Docker Compose    | 2.x      | Optional, but convenient for spinning up infra services   |
| PostgreSQL 13+    | Optional | Run `install_and_setup.py` if you need a real database    |
| Redis / RabbitMQ  | Optional | Definitions available in `docker-compose.yml`             |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate      # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
copy .env.example .env      # Linux/Mac: cp .env.example .env
```

`.env.example` only contains placeholders. Fill in your DashScope / API keys inside `.env`. The file is ignored by git, so sensitive values will not be committed. Leaving the keys empty automatically enables mock mode for offline demos.

### 3. Initialize the database (optional)

```bash
python install_and_setup.py
```

This script creates PostgreSQL tables and seeds default configs. Skip it if you rely on the in-memory database.

### 4. Launch services / demo

```bash
python start_services.py        # sequentially start all core microservices
python final_demo.py            # run the terminal-based end-to-end demo

# With Docker
make dev-up                     # requires docker-compose
```

---

## 🧪 Testing & Demo

```bash
pytest                                  # run all Python tests
python test_database_integration.py     # verify the in-memory DB layer
python final_demo.py                    # showcase every service end-to-end
```

---

## 🔍 Debugging & Ops

- Logs: `make logs SERVICE=translation`
- Local web console: `python web/server.py --port 3000`
- Monitoring stack lives in `infrastructure/monitoring/` (Prometheus + Grafana)

---

## 🤝 Customization Tips

- Replace the in-memory DB by following the schema in `docs/database-integration-guide.md` and swapping `shared/database/*` with ORM-powered implementations.
- Services auto-detect mock mode: when `DASHSCOPE_API_KEY` is empty they fall back to deterministic responses, ideal for firewalled or credential-free environments.
- Feel free to trim Docker Compose targets, Make commands, or PyInstaller bundles to craft a smaller HR demo package.

---

> Need help or have suggestions? Open an issue or drop feedback in the docs.
