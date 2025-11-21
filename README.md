# AI Demo Service

轻量级的 FastAPI 服务，用于演示和测试 `ringconntestplatform` 中的 AI 需求理解与测试用例生成引擎。该模块可以独立部署，为访客提供一个在线入口体验功能点提取、原文匹配以及测试用例生成能力。

## 特性

- 🌐 HTTP API：基于 FastAPI，提供 `healthz`、模型列表、功能模块提取、测试用例生成与模块重匹配等接口。
- 🧠 `ai_demo_core`：完整拷贝并模块化封装原有 AI 引擎逻辑，可单独安装或复用。
- ⚙️ 可配置：通过环境变量或请求体参数自定义 LLM 地址、模型、温度等参数，默认兼容本地 Ollama。
- 🗂️ 调试数据落盘：保留 `data/debug` 目录用于记录 LLM 原始响应与 AI 运行轨迹，方便排查问题。

## 项目架构

本项目采用**前后端分离**架构：

- **后端（Backend）**：基于 FastAPI 的 RESTful API 服务，运行在 `http://localhost:8113`
  - 位置：`src/ai_demo_service/`
  - 提供 AI 功能模块提取、测试用例生成等 API 接口
  - 支持 CORS 跨域请求

- **前端（Frontend）**：基于 Vue3 + Vite 的单页应用，运行在 `http://localhost:3000`
  - 位置：`frontend/`
  - 通过 Vite 代理将 `/api` 请求转发到后端服务
  - 开发环境使用相对路径，生产环境可通过环境变量配置

## 快速开始

### 1. 安装依赖

**后端依赖：**
```bash
# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 Python 依赖
pip install -e .
```

**前端依赖：**
```bash
cd frontend
npm install
```

### 2. 启动服务

**启动后端（像 Flask 那样直接运行）：**

```bash
# 方式1：直接运行（推荐，类似 Flask 的 python app.py）
python -m ai_demo_service.main

# 方式2：使用 uvicorn 命令
uvicorn ai_demo_service.main:app --reload --port 8113
```

后端服务启动后可以访问：
- `GET http://localhost:8113/healthz` - 服务健康检查
- `GET http://localhost:8113/api/v1/models` - 查看可用模型列表
- `POST http://localhost:8113/api/v1/function-modules/extract` - 提取功能模块
- `POST http://localhost:8113/api/v1/test-cases/generate` - 生成测试用例
- `POST http://localhost:8113/api/v1/modules/rematch` - 重新匹配模块原文
- `GET http://localhost:8113/docs` - Swagger API 文档

**启动前端：**

```bash
cd frontend
npm run dev
```

前端服务将在 `http://localhost:3000` 启动，自动通过 Vite 代理将 `/api` 请求转发到后端服务。

### 3. 一键启动（可选）

如果需要同时启动前后端，可以使用启动脚本：

```bash
# 使用 Shell 脚本（Linux/macOS）
./start.sh

# 或使用 Python 脚本（跨平台）
python3 start.py
```


## 环境变量配置

### 后端环境变量

在项目根目录创建 `.env` 文件（参考 `.env.example`），或直接设置系统环境变量：

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `AI_DEMO_BACKEND_HOST` | 后端服务监听地址 | `0.0.0.0` |
| `AI_DEMO_BACKEND_PORT` | 后端服务端口 | `8113` |
| `AI_DEMO_BACKEND_RELOAD` | 是否启用热重载 | `true`（开发环境） |
| `AI_DEMO_CORS_ORIGINS` | CORS 允许的来源（逗号分隔） | `*`（开发环境）<br>生产环境建议设置为前端域名 |
| `AI_DEMO_APP_NAME` | 应用名称 | `AI Demo Service` |
| `AI_DEMO_APP_VERSION` | 应用版本 | `0.1.0` |
| `AI_DEMO_LOG_LEVEL` | 服务日志级别 | `INFO` |
| `AI_DEMO_DEFAULT_MODEL` | 默认模型 | `qwen2.5:7b` |
| `AI_DEMO_LLM_BASE_URL` | LLM 服务地址（Ollama） | `http://localhost:11434` |
| `AI_DEMO_MAX_TOKENS` | 默认最大 token 数 | `8000` |

### 前端环境变量

在 `frontend/` 目录创建 `.env.local` 文件（可选）：

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | API 基础 URL（用于前端 API 调用） | 开发环境：空字符串（使用代理）<br>生产环境：需配置完整URL |
| `VITE_BACKEND_URL` | Vite 代理目标地址（开发环境） | `http://localhost:8113` |
| `VITE_PORT` | 前端开发服务器端口 | `3000` |

> **重要提示**：
> - 复制 `.env.example` 为 `.env` 并根据实际情况修改配置
> - 后端也可以通过 API 请求体里的 `base_url`、`model_name`、`temperature`、`max_tokens` 参数进行临时覆盖
> - **开发环境**：前端通常不需要设置环境变量，会自动使用 Vite 代理（`/api` → `http://localhost:8113`）
> - **生产环境**：
>   - 必须设置 `VITE_API_BASE_URL` 为后端服务的完整 URL（如 `https://api.example.com`）
>   - 必须设置 `AI_DEMO_CORS_ORIGINS` 为前端域名（如 `https://example.com`），提高安全性
>   - 建议设置 `AI_DEMO_BACKEND_RELOAD=false` 禁用热重载

## 项目结构

```
ai_demo_service/
├── src/                         # Python 源代码目录
│   ├── ai_demo_core/            # 核心AI引擎（可独立复用）
│   │   └── engine/              # AI引擎核心模块
│   │       ├── llm_service.py   # LLM服务封装
│   │       ├── extractors.py    # 功能模块提取器
│   │       ├── test_case_generator.py  # 测试用例生成器
│   │       └── ...
│   └── ai_demo_service/         # FastAPI后端服务
│       ├── api/                 # API路由定义
│       │   └── routes.py       # 路由处理器
│       ├── services/            # 业务逻辑层
│       │   └── test_case_service.py
│       ├── config.py            # 配置管理
│       ├── schemas.py           # 数据模型定义
│       └── main.py              # FastAPI应用入口
│
├── frontend/                     # Vue3前端应用
│   ├── src/
│   │   ├── apis/               # API调用封装
│   │   │   └── ai.js           # AI相关API
│   │   ├── components/         # Vue组件
│   │   │   └── ai/             # AI功能相关组件
│   │   ├── views/              # 页面视图
│   │   │   └── ai/             # AI功能页面
│   │   ├── router/             # 路由配置
│   │   ├── App.vue             # 根组件
│   │   └── main.js             # 应用入口
│   ├── index.html              # HTML模板
│   ├── vite.config.js          # Vite配置（包含API代理）
│   └── package.json            # 前端依赖配置
│
├── scripts/                     # 工具脚本
├── data/                        # 数据目录（调试信息等）
├── start.sh                     # 一键启动脚本（Shell，同时启动前后端，可选）
├── start.py                     # 一键启动脚本（Python，同时启动前后端，可选）
├── pyproject.toml              # Python项目配置
└── README.md                    # 项目说明文档
```

### 前后端通信说明

- **开发环境**：
  - 前端运行在 `http://localhost:3000`
  - 后端运行在 `http://localhost:8113`
  - 前端通过 Vite 代理（`/api` → `http://localhost:8113`）访问后端
  - 前端代码使用相对路径 `/api`，由 Vite 自动代理

- **生产环境**：
  - 前端构建后部署到静态服务器
  - 后端部署到应用服务器
  - 前端通过环境变量 `VITE_API_BASE_URL` 配置后端地址
  - 或使用 Nginx 等反向代理统一域名

## 部署建议

1. **独立部署**：将本目录作为独立仓库推送至 GitHub。
2. **后端部署**：使用 Render/Fly.io/Railway/Zeabur 等平台部署后端服务，设置环境变量。
3. **前端部署**：
   - 构建前端：`cd frontend && npm run build`
   - 将 `dist/` 目录部署到 Vercel/Netlify/GitHub Pages 等静态托管平台
   - 或使用同一平台部署前后端（前端代理到后端API）
4. **Hexo集成**：在 Hexo 博客中添加一个体验入口页面，链接到部署的前端地址。

## 开发说明

- 代码位于 `src/` 目录，`ai_demo_core` 为引擎模块，`ai_demo_service` 为 HTTP 层。
- `data/debug` 目录会在运行时自动创建，可通过 `.gitignore` 忽略本地调试文件。
- 推荐使用 `ruff` 和 `pytest` 做基础静态检查与测试。

如需进一步扩展功能（例如鉴权、任务队列、前端页面），可以在此项目基础上继续演进。欢迎反馈。
