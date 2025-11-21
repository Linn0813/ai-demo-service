# 知识库问答功能架构设计

## 功能概述

知识库问答功能是一个基于 RAG（Retrieval-Augmented Generation）的智能问答系统，允许用户上传文档到知识库，然后通过自然语言提问，系统会从知识库中检索相关信息并生成答案。

## 核心功能

1. **文档管理**
   - 上传文档（PDF、Markdown、TXT、Word、Excel 等）
   - 文档列表查看
   - 文档删除
   - 文档重新索引

2. **智能问答**
   - 单次问答
   - 多轮对话（可选）
   - 流式响应（可选）
   - 答案来源标注

## 技术架构

### 1. 整体流程

```
用户上传文档
    ↓
文档加载器（Document Loader）
    ↓
文本分割器（Text Splitter）
    ↓
向量化（Embedding）
    ↓
存储到向量数据库（Vector Store）
    ↓
[用户提问]
    ↓
问题向量化
    ↓
向量检索（相似度搜索）
    ↓
检索 Top-K 相关文档片段
    ↓
构建上下文（Context）
    ↓
LLM 生成答案
    ↓
返回答案 + 引用来源
```

### 2. 模块设计

#### 2.1 基础服务模块 (`core/engine/base/`) - 共享服务

**llm_service.py** - LLM 服务（共享）
```python
class LLMService:
    """LLM 服务，测试用例生成和知识库问答共用"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    )
    
    def generate(self, prompt: str, max_retries: int = 2) -> str
    def generate_stream(self, prompt: str) -> Iterator[str]  # 流式生成
```

**embedding_service.py** - 向量化服务（共享）
```python
class EmbeddingService:
    """文本向量化服务，知识库使用"""
    
    def __init__(self, model_name: Optional[str] = None)
    def embed_text(self, text: str) -> List[float]
    def embed_batch(self, texts: List[str]) -> List[List[float]]
    def get_model_name(self) -> str
```

**config.py** - 通用配置（共享）
```python
# LLM 配置
DEFAULT_CONFIG = {
    "llm_base_url": "http://localhost:11434",
    "default_model": "qwen2.5:7b",
    "temperature": 0.7,
    "max_tokens": 8000,
    ...
}

# Embedding 配置
EMBEDDING_CONFIG = {
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "device": "cpu",
    ...
}
```

#### 2.2 文档处理模块 (`core/engine/knowledge_base/`)

**document_loader.py** - 文档加载器
```python
class DocumentLoader:
    """支持多种格式的文档加载器"""
    
    def load_pdf(self, file_path: str) -> str
    def load_markdown(self, file_path: str) -> str
    def load_txt(self, file_path: str) -> str
    def load_word(self, file_path: str) -> str
    def load_excel(self, file_path: str) -> str
    def load(self, file_path: str) -> Document
```

**text_splitter.py** - 文本分割器
```python
class TextSplitter:
    """将长文本分割成适合向量化的片段"""
    
    def split_text(
        self, 
        text: str, 
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[TextChunk]
```


**vector_store.py** - 向量存储
```python
class VectorStore:
    """向量数据库抽象接口"""
    
    def add_documents(
        self, 
        documents: List[DocumentChunk],
        embeddings: List[List[float]]
    ) -> List[str]
    
    def search(
        self, 
        query_embedding: List[float],
        top_k: int = 5,
        filter: Optional[Dict] = None
    ) -> List[SearchResult]
    
    def delete_documents(self, document_ids: List[str])
    def get_collection_info(self) -> Dict
```

#### 2.2 RAG 模块

**retriever.py** - 检索器
```python
class Retriever:
    """RAG 检索器"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService  # 使用共享的 EmbeddingService
    )
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None
    ) -> List[RetrievalResult]
    
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]
```

**qa_generator.py** - 问答生成器
```python
class QAGenerator:
    """基于 RAG 的问答生成器"""
    
    def __init__(
        self,
        llm_service: LLMService,  # 使用共享的 LLMService
        retriever: Retriever
    )
    
    def generate_answer(
        self,
        question: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        temperature: float = 0.7
    ) -> QAResponse
    
    def generate_answer_stream(
        self,
        question: str,
        document_ids: Optional[List[str]] = None
    ) -> Iterator[str]  # 流式响应
```

#### 2.3 服务层 (`app/services/knowledge_base_service.py`)

```python
class KnowledgeBaseService:
    """知识库业务逻辑服务"""
    
    def upload_document(
        self,
        file: UploadFile,
        title: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> DocumentInfo
    
    def list_documents(
        self,
        skip: int = 0,
        limit: int = 20
    ) -> List[DocumentInfo]
    
    def delete_document(self, document_id: str)
    
    def reindex_document(self, document_id: str)
    
    def ask_question(
        self,
        question: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> QAResponse
```

#### 2.4 API 层 (`app/api/v1/knowledge_base.py`)

```python
router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])

@router.post("/documents")
async def upload_document(
    file: UploadFile,
    title: Optional[str] = None,
    background_tasks: BackgroundTasks
) -> DocumentInfo

@router.get("/documents")
async def list_documents(
    skip: int = 0,
    limit: int = 20
) -> List[DocumentInfo]

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str)

@router.post("/documents/{document_id}/reindex")
async def reindex_document(document_id: str)

@router.post("/qa/ask")
async def ask_question(request: QARequest) -> QAResponse
```

## 数据模型

### DocumentChunk（文档片段）
```python
class DocumentChunk(BaseModel):
    id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
```

### SearchResult（检索结果）
```python
class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float  # 相似度分数
    metadata: Dict[str, Any]
```

### QAResponse（问答响应）
```python
class QAResponse(BaseModel):
    answer: str
    sources: List[DocumentChunk]  # 引用的文档片段
    confidence: float
    query_time: float  # 查询耗时
```

## 配置项

### 环境变量

```bash
# 向量数据库配置
KB_VECTOR_STORE_TYPE=chromadb  # chromadb, qdrant, pinecone
KB_VECTOR_STORE_PATH=./data/knowledge_base/vectors
KB_COLLECTION_NAME=documents

# Embedding 配置
KB_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
KB_EMBEDDING_DEVICE=cpu  # cpu, cuda

# 文本分割配置
KB_CHUNK_SIZE=500
KB_CHUNK_OVERLAP=50

# 检索配置
KB_DEFAULT_TOP_K=5
KB_RERANK_ENABLED=false
```

## 实现细节

### 1. 文档处理流程

```python
# 伪代码示例
from core.engine.base.embedding_service import EmbeddingService  # 使用共享服务

def process_document(file_path: str) -> DocumentInfo:
    # 1. 加载文档
    loader = DocumentLoader()
    text = loader.load(file_path)
    
    # 2. 分割文本
    splitter = TextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
    
    # 3. 向量化（使用共享的 EmbeddingService）
    embedding_service = EmbeddingService()  # 从 base 模块导入
    embeddings = embedding_service.embed_batch([chunk.content for chunk in chunks])
    
    # 4. 存储
    vector_store = VectorStore()
    chunk_ids = vector_store.add_documents(chunks, embeddings)
    
    return DocumentInfo(id=document_id, chunk_count=len(chunks))
```

### 2. 问答流程

```python
# 伪代码示例
from core.engine.base.llm_service import LLMService  # 使用共享服务
from core.engine.base.embedding_service import EmbeddingService  # 使用共享服务

def answer_question(question: str) -> QAResponse:
    # 1. 问题向量化（使用共享的 EmbeddingService）
    embedding_service = EmbeddingService()  # 从 base 模块导入
    query_embedding = embedding_service.embed_text(question)
    
    # 2. 检索相关文档片段
    vector_store = VectorStore()
    results = vector_store.search(query_embedding, top_k=5)
    
    # 3. 构建上下文
    context = "\n\n".join([r.chunk.content for r in results])
    
    # 4. 生成答案（使用共享的 LLMService）
    llm_service = LLMService()  # 从 base 模块导入，与测试用例生成共用
    prompt = build_qa_prompt(question, context)
    answer = llm_service.generate(prompt)
    
    # 5. 返回结果
    return QAResponse(
        answer=answer,
        sources=[r.chunk for r in results],
        confidence=calculate_confidence(results)
    )
```

## 前端界面设计

### 1. 知识库管理页面

**功能：**
- 文档上传（拖拽上传）
- 文档列表（表格展示）
- 文档预览
- 文档删除
- 文档重新索引

**组件：**
- `DocumentUpload.vue` - 上传组件
- `DocumentList.vue` - 列表组件
- `DocumentPreview.vue` - 预览组件

### 2. 问答页面

**功能：**
- 问题输入
- 答案展示（Markdown 渲染）
- 引用来源展示
- 问答历史记录

**组件：**
- `QAChat.vue` - 聊天式问答界面
- `AnswerDisplay.vue` - 答案展示组件
- `SourceCitation.vue` - 引用来源组件

## 性能优化

1. **批量处理**
   - 文档向量化使用批量处理
   - 异步处理文档上传

2. **缓存机制**
   - 常见问题答案缓存
   - Embedding 结果缓存

3. **索引优化**
   - 向量数据库索引优化
   - 文档元数据索引

## 扩展性考虑

1. **多向量数据库支持**
   - 抽象 VectorStore 接口
   - 实现多种后端（ChromaDB、Qdrant、Pinecone）

2. **多 Embedding 模型支持**
   - 抽象 EmbeddingService 接口
   - 支持本地和云端模型

3. **高级检索**
   - 混合检索（向量 + 关键词）
   - 重排序（reranking）
   - 多模态检索（图片、表格等）

4. **多轮对话**
   - 对话历史管理
   - 上下文理解

## 测试策略

1. **单元测试**
   - 文档加载器测试
   - 文本分割器测试
   - 向量化服务测试

2. **集成测试**
   - 端到端问答流程测试
   - API 接口测试

3. **性能测试**
   - 文档处理性能测试
   - 检索性能测试
   - 并发测试

