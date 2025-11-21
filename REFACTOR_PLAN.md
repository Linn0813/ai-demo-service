# 项目重构方案

## 当前问题分析

### 1. 目录结构混乱
- ❌ 根目录文件过多：`start.py`, `start.sh` 等启动脚本混在根目录
- ❌ `src/` 目录包含所有 Python 代码，但命名不够清晰
- ❌ `ai_demo_service.egg-info/` 不应该在 `src/` 目录下
- ❌ `scripts/` 和根目录脚本分散，没有统一管理
- ❌ `data/` 目录在根目录，运行时数据应该统一管理

### 2. 前后端分离不够清晰
- ❌ `frontend/` 在根目录，但后端代码在 `src/ai_demo_service/`
- ❌ 没有明确的 `backend/` 目录，前后端结构不对等
- ❌ 配置分散，没有统一的配置管理

### 3. 包结构问题
- ⚠️ `ai_demo_core` 和 `ai_demo_service` 都在 `src/` 下，但层级关系不清晰
- ⚠️ 包名和目录名不一致，容易混淆

## 重构目标

1. **清晰的目录结构**：前后端分离，各司其职
2. **统一的配置管理**：配置文件集中管理
3. **规范的脚本管理**：所有脚本统一管理
4. **清晰的依赖关系**：核心库和服务分离明确
5. **便于部署**：前后端可以独立部署
6. **可扩展性**：支持多模块扩展（测试用例生成 + 知识库问答）

## 重构后的目录结构

```
ai_demo_service/
├── backend/                          # 后端服务（FastAPI）
│   ├── app/                         # 应用代码
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 应用入口（可直接运行）
│   │   ├── config.py                # 配置管理
│   │   ├── schemas/                  # 数据模型（按模块组织）
│   │   │   ├── __init__.py
│   │   │   ├── common.py            # 通用模型（HealthResponse等）
│   │   │   ├── test_case.py         # 测试用例生成相关模型
│   │   │   └── knowledge_base.py    # 知识库相关模型
│   │   ├── api/                     # API 路由（按模块组织）
│   │   │   ├── __init__.py
│   │   │   ├── v1/                  # API v1 版本
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_case.py     # 测试用例生成路由
│   │   │   │   └── knowledge_base.py # 知识库路由
│   │   │   └── common.py            # 通用路由（health等）
│   │   └── services/                # 业务逻辑层（按模块组织）
│   │       ├── __init__.py
│   │       ├── test_case_service.py # 测试用例生成服务
│   │       └── knowledge_base_service.py # 知识库服务
│   ├── core/                        # 核心 AI 引擎（可独立复用）
│   │   ├── __init__.py
│   │   ├── logger.py                # 日志服务（共享）
│   │   ├── engine/                  # AI 引擎核心模块
│   │   │   ├── __init__.py
│   │   │   ├── base/                # 基础共享服务（两个功能共用）
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.py        # 通用配置（LLM、Embedding等）
│   │   │   │   ├── llm_service.py   # LLM 服务（共享，两个功能都用）
│   │   │   │   ├── embedding_service.py  # Embedding 服务（共享，知识库需要）
│   │   │   │   └── debug_recorder.py     # 调试记录（共享）
│   │   │   ├── test_case/           # 测试用例生成引擎（业务特定）
│   │   │   │   ├── __init__.py
│   │   │   │   ├── extractors.py    # 功能模块提取器
│   │   │   │   ├── test_case_generator.py  # 测试用例生成器
│   │   │   │   ├── prompts.py       # 测试用例生成 Prompt
│   │   │   │   ├── validators.py   # 测试用例验证器
│   │   │   │   └── ...              # 其他测试用例特定模块
│   │   │   └── knowledge_base/      # 知识库引擎（业务特定）
│   │   │       ├── __init__.py
│   │   │       ├── document_loader.py    # 文档加载器（PDF/Markdown/TXT等）
│   │   │       ├── text_splitter.py      # 文本分割器（chunking）
│   │   │       ├── vector_store.py       # 向量存储（ChromaDB/Qdrant等）
│   │   │       ├── retriever.py          # 检索器（RAG）
│   │   │       ├── qa_generator.py       # 问答生成器（使用共享的 LLM 服务）
│   │   │       └── prompts.py           # 知识库问答 Prompt
│   ├── storage/                     # 数据存储
│   │   ├── knowledge_base/          # 知识库存储
│   │   │   ├── documents/           # 原始文档
│   │   │   └── vectors/             # 向量数据库
│   │   └── uploads/                 # 上传文件临时存储
│   ├── tests/                       # 后端测试
│   │   ├── __init__.py
│   │   ├── test_api/
│   │   ├── test_services/
│   │   └── test_core/
│   ├── pyproject.toml               # 后端 Python 配置
│   └── requirements.txt             # 后端依赖（可选，pyproject.toml 已包含）

├── frontend/                        # 前端应用（Vue3）
│   ├── src/
│   │   ├── apis/                   # API 调用封装（按模块组织）
│   │   │   ├── index.js            # API 统一导出
│   │   │   ├── testCase.js         # 测试用例生成 API
│   │   │   └── knowledgeBase.js    # 知识库 API
│   │   ├── components/             # Vue 组件（按模块组织）
│   │   │   ├── common/             # 通用组件
│   │   │   ├── testCase/           # 测试用例生成组件
│   │   │   │   ├── AiPageLayout.vue
│   │   │   │   └── FunctionPointsConfirm.vue
│   │   │   └── knowledgeBase/      # 知识库组件
│   │   │       ├── DocumentUpload.vue
│   │   │       ├── DocumentList.vue
│   │   │       └── QAChat.vue
│   │   ├── views/                  # 页面视图（按模块组织）
│   │   │   ├── TestCase/           # 测试用例生成页面
│   │   │   │   ├── AiModule.vue
│   │   │   │   └── AITestCaseGenerate.vue
│   │   │   └── KnowledgeBase/      # 知识库页面
│   │   │       ├── KnowledgeBaseManage.vue
│   │   │       └── QA.vue
│   │   ├── router/                 # 路由配置
│   │   │   └── index.js
│   │   ├── stores/                 # 状态管理（Pinia，可选）
│   │   │   └── ...
│   │   ├── utils/                 # 工具函数
│   │   │   └── ...
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── .env.example                # 前端环境变量示例

├── scripts/                        # 统一脚本目录
│   ├── start_dev.py                # 开发环境启动脚本（同时启动前后端）
│   ├── start_dev.sh                # 开发环境启动脚本（Shell 版本）
│   └── tools/                      # 工具脚本
│       ├── test_case/              # 测试用例生成工具
│       │   ├── debug_extract_modules.py
│       │   └── generate_test_cases.py
│       └── knowledge_base/         # 知识库工具
│           └── import_documents.py

├── data/                           # 运行时数据（gitignore）
│   ├── debug/
│   │   └── ai_runs/
│   └── knowledge_base/            # 知识库数据
│       └── ...

├── docs/                           # 文档目录
│   ├── api/                        # API 文档
│   ├── development/                # 开发文档
│   └── deployment/                 # 部署文档

├── .env.example                    # 环境变量示例（根目录）
├── .gitignore
├── README.md                       # 项目说明
├── LICENSE                         # 许可证（可选）
└── docker-compose.yml              # Docker 编排（可选）
```

## 重构步骤

### 阶段一：创建新目录结构（不破坏现有代码）

1. **创建新目录**
   ```bash
   mkdir -p backend/app/api
   mkdir -p backend/app/services
   mkdir -p backend/core/engine
   mkdir -p backend/tests
   mkdir -p scripts/tools
   mkdir -p docs
   ```

2. **移动后端代码**
   ```bash
   # 移动应用代码
   mv src/ai_demo_service/* backend/app/
   mv src/ai_demo_service/api/* backend/app/api/
   mv src/ai_demo_service/services/* backend/app/services/
   
   # 移动核心代码
   mv src/ai_demo_core/* backend/core/
   mv src/ai_demo_core/engine/* backend/core/engine/
   ```

3. **移动前端代码**
   ```bash
   # 前端代码已经在 frontend/ 目录，无需移动
   # 但需要更新配置中的路径引用
   ```

4. **移动脚本**
   ```bash
   mv start.py scripts/start_dev.py
   mv start.sh scripts/start_dev.sh
   mv scripts/*.py scripts/tools/  # 保留示例文件等
   ```

### 阶段二：更新导入路径

1. **更新后端导入**
   - `ai_demo_service.*` → `app.*`
   - `ai_demo_core.*` → `core.*`
   - 更新 `pyproject.toml` 中的包配置

2. **更新前端配置**
   - 更新 `vite.config.js` 中的路径引用（如果有）
   - 更新 API 调用中的基础 URL 配置

3. **更新脚本导入**
   - 更新 `scripts/` 目录下的脚本导入路径

### 阶段三：更新配置文件

1. **更新 `backend/pyproject.toml`**
   ```toml
   [tool.setuptools]
   package-dir = {"" = "."}
   
   [tool.setuptools.packages.find]
   where = ["."]
   include = ["app*", "core*"]
   ```

2. **更新环境变量**
   - 创建 `.env.example` 文件
   - 更新配置读取逻辑

3. **更新启动脚本**
   - 更新 `scripts/start_dev.py` 中的路径引用

### 阶段四：清理和验证

1. **删除旧目录**
   ```bash
   rm -rf src/
   rm -rf ai_demo_service.egg-info/
   ```

2. **更新文档**
   - 更新 `README.md` 中的目录结构说明
   - 更新导入示例

3. **测试验证**
   - 测试后端启动：`python -m app.main`
   - 测试前端启动：`cd frontend && npm run dev`
   - 测试脚本运行

## 重构后的优势

### 1. 清晰的目录结构
- ✅ 前后端完全分离，结构对等
- ✅ 核心库和服务分离明确
- ✅ 脚本统一管理

### 2. 便于维护
- ✅ 每个模块职责单一
- ✅ 导入路径清晰
- ✅ 配置集中管理

### 3. 便于部署
- ✅ 前后端可以独立部署
- ✅ 核心库可以作为独立包发布
- ✅ Docker 部署更简单

### 4. 符合最佳实践
- ✅ 遵循 Python 项目标准结构
- ✅ 遵循前后端分离架构
- ✅ 符合现代 Web 开发规范

## 知识库问答功能设计

### 功能模块划分

#### 1. 后端 API 设计

**知识库管理 API (`/api/v1/knowledge-base`)**
- `POST /documents` - 上传文档（支持 PDF、Markdown、TXT 等）
- `GET /documents` - 获取文档列表
- `GET /documents/{doc_id}` - 获取文档详情
- `DELETE /documents/{doc_id}` - 删除文档
- `POST /documents/{doc_id}/reindex` - 重新索引文档

**问答 API (`/api/v1/qa`)**
- `POST /ask` - 提交问题，返回答案
- `POST /chat` - 流式对话（SSE/WebSocket）
- `GET /history` - 获取问答历史

#### 2. 核心引擎设计

**文档处理流程**
```
文档上传 → 文档加载器 → 文本分割 → 向量化 → 存储到向量数据库
```

**问答流程（RAG）**
```
用户问题 → 向量化 → 向量检索（相似度搜索）→ 上下文构建 → LLM 生成答案
```

#### 3. 技术选型建议

**向量数据库**
- 开发环境：ChromaDB（轻量级，本地存储）
- 生产环境：Qdrant / Pinecone / Weaviate（可选）

**Embedding 模型**
- 本地：sentence-transformers（中文模型）
- 云端：OpenAI Embeddings / 百度文心 / 阿里通义（可选）

**文档加载器**
- PDF: PyPDF2 / pdfplumber
- Markdown: markdown
- TXT: 直接读取
- Word: python-docx
- Excel: openpyxl / pandas

#### 4. 数据模型设计

```python
# schemas/knowledge_base.py

class DocumentUploadRequest(BaseModel):
    file: UploadFile
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None

class DocumentInfo(BaseModel):
    id: str
    title: str
    file_name: str
    file_type: str
    file_size: int
    upload_time: datetime
    chunk_count: int
    status: str  # processing, ready, error

class QARequest(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None  # 指定文档范围
    top_k: int = 5  # 检索 top K 个相关片段
    temperature: float = 0.7

class QAResponse(BaseModel):
    answer: str
    sources: List[DocumentChunk]  # 引用的文档片段
    confidence: float
```

## 迁移注意事项

1. **导入路径变更**
   - 所有 `from ai_demo_service.*` 改为 `from app.*`
   - 所有 `from ai_demo_core.*` 改为 `from core.*`
   - **基础服务（共享）**：
     - `from core.engine.base.llm_service import LLMService`
     - `from core.engine.base.embedding_service import EmbeddingService`
     - `from core.engine.base.config import DEFAULT_CONFIG`
   - **测试用例生成（业务特定）**：
     - `from core.engine.test_case.test_case_generator import TestCaseGenerator`
     - `from core.engine.test_case.extractors import FunctionModuleExtractor`
   - **知识库（业务特定）**：
     - `from core.engine.knowledge_base.qa_generator import QAGenerator`
     - `from core.engine.knowledge_base.retriever import Retriever`

2. **配置文件路径**
   - `pyproject.toml` 需要移动到 `backend/` 目录
   - 环境变量路径可能需要调整
   - 新增知识库相关配置（向量数据库地址、embedding 模型等）

3. **测试路径**
   - 测试文件需要更新导入路径
   - 测试运行命令需要更新
   - 新增知识库功能测试

4. **CI/CD 配置**
   - 如果有 CI/CD 配置，需要更新路径
   - 可能需要添加向量数据库服务

5. **依赖管理**
   - 新增知识库相关依赖（chromadb、sentence-transformers 等）
   - 更新 `pyproject.toml` 和 `requirements.txt`

## 回滚方案

如果重构过程中出现问题，可以：
1. 保留 `src/` 目录作为备份
2. 使用 Git 分支进行重构
3. 逐步迁移，确保每个阶段都可以独立运行

## 实施建议

1. **创建重构分支**
   ```bash
   git checkout -b refactor/project-structure
   ```

2. **分阶段实施**
   - 先创建新目录结构
   - 然后逐步迁移代码
   - 最后更新配置和文档

3. **充分测试**
   - 每个阶段完成后进行测试
   - 确保前后端都能正常运行

4. **更新文档**
   - 及时更新 README
   - 更新开发文档
   - 添加知识库功能使用文档

## 知识库功能实施计划

### 阶段一：基础架构（重构完成后）

1. **创建知识库模块目录结构**
   ```bash
   mkdir -p backend/core/engine/knowledge_base
   mkdir -p backend/app/api/v1
   mkdir -p backend/app/schemas
   mkdir -p backend/storage/knowledge_base/{documents,vectors}
   ```

2. **实现核心组件**
   - 文档加载器（支持多种格式）
   - 文本分割器（chunking）
   - 向量化服务（embedding）
   - 向量存储接口（抽象层，支持多种后端）

3. **实现基础 API**
   - 文档上传接口
   - 文档列表接口
   - 文档删除接口

### 阶段二：RAG 功能

1. **实现检索器**
   - 向量检索（相似度搜索）
   - 混合检索（向量 + 关键词）
   - 重排序（reranking）

2. **实现问答生成器**
   - 上下文构建
   - Prompt 工程
   - 答案生成

3. **实现问答 API**
   - 单次问答接口
   - 流式对话接口（可选）

### 阶段三：前端界面

1. **知识库管理界面**
   - 文档上传组件
   - 文档列表组件
   - 文档删除功能

2. **问答界面**
   - 聊天式问答界面
   - 答案展示（包含引用来源）
   - 问答历史记录

### 阶段四：优化和扩展

1. **性能优化**
   - 批量处理优化
   - 缓存机制
   - 异步处理

2. **功能扩展**
   - 多轮对话支持
   - 文档预览功能
   - 文档搜索功能
   - 知识图谱可视化（可选）

## 新增依赖项

### 后端依赖（添加到 pyproject.toml）

```toml
dependencies = [
    # 现有依赖...
    "chromadb>=0.4.0",              # 向量数据库（开发环境）
    "sentence-transformers>=2.2.0",  # Embedding 模型
    "PyPDF2>=3.0.0",                 # PDF 处理
    "python-docx>=1.1.0",            # Word 文档处理
    "openpyxl>=3.1.0",               # Excel 处理
    "langchain>=0.1.0",             # RAG 框架（可选，简化开发）
]
```

### 前端依赖（添加到 package.json）

```json
{
  "dependencies": {
    // 现有依赖...
    "vue-markdown": "^0.1.0",      // Markdown 渲染（文档预览）
    "file-saver": "^2.0.5"          // 文件下载
  }
}
```

