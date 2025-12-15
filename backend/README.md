# Backend 安装和启动指南

## 安装依赖

在 `backend/` 目录下安装项目依赖：

```bash
cd backend
pip install -e .
```

或者如果使用虚拟环境：

```bash
cd backend
source ../.venv/bin/activate  # 激活虚拟环境
pip install -e .
```

## 启动服务

### 方式一：直接运行（推荐）

```bash
cd backend
python -m app.main
```

### 方式二：使用 uvicorn

```bash
cd backend
uvicorn app.main:app --reload --port 8113
```

## 环境变量配置

在项目根目录创建 `.env` 文件（可选）：

### 使用 Ollama（本地模型）

```bash
AI_DEMO_BACKEND_HOST=0.0.0.0
AI_DEMO_BACKEND_PORT=8113
AI_DEMO_CORS_ORIGINS=http://localhost:3000
AI_DEMO_LLM_PROVIDER=ollama
AI_DEMO_LLM_BASE_URL=http://localhost:11434
AI_DEMO_DEFAULT_MODEL=qwen2.5:7b
AI_DEMO_MAX_TOKENS=8000
```

### 使用 GPT-5.2 API（OpenAI 兼容）

```bash
AI_DEMO_BACKEND_HOST=0.0.0.0
AI_DEMO_BACKEND_PORT=8113
AI_DEMO_CORS_ORIGINS=http://localhost:3000
AI_DEMO_LLM_PROVIDER=openai
AI_DEMO_LLM_BASE_URL=https://api.example.com  # 替换为实际的 GPT-5.2 API 地址
AI_DEMO_LLM_API_KEY=BSkz0o399ltr4Ivmb86k3xQeGrfs3juy6ptqFN4KNY9C00hz9EvvJQQJ99BLACYeBjFXJ3w3AAAACOGQfCc
AI_DEMO_DEFAULT_MODEL=gpt-5.2
AI_DEMO_MAX_TOKENS=8000
```

> **注意**：使用 OpenAI 兼容 API 时，需要设置 `AI_DEMO_LLM_PROVIDER=openai` 并提供正确的 `AI_DEMO_LLM_BASE_URL` 和 `AI_DEMO_LLM_API_KEY`。

## 常见问题

### ModuleNotFoundError: No module named 'uvicorn'

**解决方法**：在 `backend/` 目录下运行 `pip install -e .`

### 导入错误：No module named 'app'

**解决方法**：确保在 `backend/` 目录下运行，或者设置 `PYTHONPATH=backend`

