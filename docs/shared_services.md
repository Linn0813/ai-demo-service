# 共享基础服务设计

## 概述

测试用例生成和知识库问答两个功能共享相同的基础 AI 服务，包括：
- **LLM 服务**：大语言模型调用（两个功能都需要）
- **Embedding 服务**：文本向量化（知识库需要）
- **配置管理**：统一的配置管理
- **日志服务**：统一的日志记录
- **调试记录**：统一的调试数据记录

## 目录结构

```
backend/core/engine/
├── base/                    # 基础共享服务
│   ├── __init__.py
│   ├── config.py           # 通用配置（LLM、Embedding等）
│   ├── llm_service.py      # LLM 服务（共享）
│   ├── embedding_service.py # Embedding 服务（共享）
│   └── debug_recorder.py   # 调试记录（共享）
│
├── test_case/              # 测试用例生成（业务特定）
│   ├── extractors.py       # 使用 base.llm_service
│   ├── test_case_generator.py  # 使用 base.llm_service
│   └── ...
│
└── knowledge_base/         # 知识库（业务特定）
    ├── qa_generator.py     # 使用 base.llm_service
    ├── retriever.py        # 使用 base.embedding_service
    └── ...
```

## 共享服务设计

### 1. LLM 服务 (`base/llm_service.py`)

**职责**：统一的大语言模型调用服务，两个功能模块共用

**接口设计**：
```python
class LLMService:
    """LLM 服务 - 测试用例生成和知识库问答共用"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """初始化 LLM 服务
        
        Args:
            base_url: LLM 服务地址（如 Ollama）
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
        """
    
    def generate(
        self,
        prompt: str,
        max_retries: int = 2,
        stream: bool = False
    ) -> Union[str, Iterator[str]]:
        """生成文本
        
        Args:
            prompt: 提示词
            max_retries: 最大重试次数
            stream: 是否流式返回
            
        Returns:
            生成的文本或文本流
        """
    
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """流式生成文本（用于知识库问答的流式响应）"""
```

**使用示例**：
```python
# 测试用例生成中使用
from core.engine.base.llm_service import LLMService

llm_service = LLMService(model="qwen2.5:7b")
test_cases = llm_service.generate(prompt)

# 知识库问答中使用
from core.engine.base.llm_service import LLMService

llm_service = LLMService(model="qwen2.5:7b")
answer = llm_service.generate(prompt)
```

### 2. Embedding 服务 (`base/embedding_service.py`)

**职责**：文本向量化服务，知识库功能使用

**接口设计**：
```python
class EmbeddingService:
    """文本向量化服务 - 知识库使用"""
    
    def __init__(self, model_name: Optional[str] = None):
        """初始化 Embedding 服务
        
        Args:
            model_name: Embedding 模型名称
        """
    
    def embed_text(self, text: str) -> List[float]:
        """将单个文本向量化
        
        Args:
            text: 输入文本
            
        Returns:
            向量表示
        """
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量化（性能优化）
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
    
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
    
    def get_dimension(self) -> int:
        """获取向量维度"""
```

**使用示例**：
```python
# 知识库中使用
from core.engine.base.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
query_vector = embedding_service.embed_text("用户问题")
document_vectors = embedding_service.embed_batch(document_texts)
```

### 3. 配置管理 (`base/config.py`)

**职责**：统一管理所有 AI 服务的配置

**配置结构**：
```python
# LLM 配置（两个功能共用）
LLM_CONFIG = {
    "base_url": "http://localhost:11434",
    "default_model": "qwen2.5:7b",
    "temperature": 0.7,
    "max_tokens": 8000,
    "timeout": 600,
}

# Embedding 配置（知识库使用）
EMBEDDING_CONFIG = {
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "device": "cpu",  # cpu, cuda
    "batch_size": 32,
}

# 模型预设（两个功能共用）
MODEL_PRESETS = {
    "qwen2.5": {
        "model": "qwen2.5:7b",
        "description": "Qwen 2.5 7B - 中文能力强",
        "recommended": True,
    },
    # ...
}
```

### 4. 日志服务 (`core/logger.py`)

**职责**：统一的日志记录（已在 core 根目录）

**使用**：
```python
from core.logger import log

log.info("信息")
log.error("错误")
log.debug("调试")
```

### 5. 调试记录 (`base/debug_recorder.py`)

**职责**：统一的调试数据记录（两个功能共用）

**接口设计**：
```python
def record_ai_debug(
    run_type: str,
    input_data: Dict[str, Any],
    output_data: Dict[str, Any],
    run_id: Optional[str] = None
) -> str:
    """记录 AI 调试数据
    
    Args:
        run_type: 运行类型（"test_case" 或 "knowledge_base"）
        input_data: 输入数据
        output_data: 输出数据
        run_id: 运行 ID
        
    Returns:
        保存的文件路径
    """
```

## 依赖关系

```
┌─────────────────────────────────────┐
│        应用层 (app/)                 │
│  - test_case_service                │
│  - knowledge_base_service           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      业务逻辑层 (core/engine/)       │
│  ┌───────────────────────────────┐  │
│  │ test_case/                    │  │
│  │  - test_case_generator        │  │
│  │  - extractors                 │  │
│  └───────────┬──────────────────┘  │
│              │                       │
│  ┌───────────▼──────────────────┐  │
│  │ knowledge_base/               │  │
│  │  - qa_generator               │  │
│  │  - retriever                  │  │
│  └───────────┬──────────────────┘  │
│              │                       │
└──────────────┼──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      基础服务层 (core/engine/base/) │
│  - llm_service (共享)               │
│  - embedding_service (共享)         │
│  - config (共享)                    │
│  - debug_recorder (共享)             │
└─────────────────────────────────────┘
```

## 优势

1. **代码复用**：避免重复实现相同的功能
2. **统一配置**：所有 AI 服务使用统一的配置管理
3. **易于维护**：修改基础服务时，两个功能自动受益
4. **性能优化**：可以统一优化 LLM 调用（如连接池、缓存等）
5. **扩展性**：新增功能时可以直接使用现有基础服务

## 实施注意事项

1. **向后兼容**：保持现有 LLMService 接口不变
2. **配置隔离**：不同功能可以使用不同的模型配置，但共享服务实例
3. **错误处理**：统一的错误处理和重试机制
4. **性能监控**：统一的性能监控和日志记录

