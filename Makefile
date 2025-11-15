PY_SOURCES = services shared final_demo.py start_services.py install_and_setup.py test_database_integration.py

.PHONY: help dev-up dev-down dev-logs build build-service test format lint clean docs install logs

help:
	@echo "Available commands:"
	@echo "  dev-up        - 启动 docker-compose 环境"
	@echo "  dev-down      - 停止 docker-compose 环境"
	@echo "  build         - 构建全部服务镜像"
	@echo "  build-service - 构建指定服务镜像，例如 make build-service SERVICE=translation"
	@echo "  test          - 运行 pytest"
	@echo "  format        - 使用 black 格式化主要 Python 文件"
	@echo "  lint          - 运行 flake8/mypy/bandit"
	@echo "  clean         - 清理 __pycache__ 与 pyc"
	@echo "  docs          - 查看文档指引"
	@echo "  install       - 安装项目依赖"
	@echo "  logs          - 查看 docker-compose 日志"

dev-up:
	docker-compose up -d

dev-down:
	docker-compose down

dev-logs:
	docker-compose logs -f

build:
	docker-compose build

build-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make build-service SERVICE=translation"; \
		exit 1; \
	fi
	docker-compose build $(SERVICE)

test:
	python -m pytest -v

format:
	black $(PY_SOURCES)

lint:
	flake8 services shared
	mypy services shared
	bandit -r services shared

clean:
	python - <<'PY'
import pathlib, shutil
for path in pathlib.Path(".").rglob("__pycache__"):
    shutil.rmtree(path, ignore_errors=True)
for path in pathlib.Path(".").rglob("*.pyc"):
    path.unlink(missing_ok=True)
print("清理完成")
PY

docs:
	@echo "文档位于 docs/ 目录，请直接阅读对应 Markdown 文件。"

install:
	pip install -r requirements.txt

logs:
	@if [ -z "$(SERVICE)" ]; then \
		docker-compose logs -f; \
	else \
		docker-compose logs -f $(SERVICE); \
	fi
