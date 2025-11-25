# encoding: utf-8
"""
文本向量化服务（Embedding Service）。
支持两种方式：
1. Ollama API（本地部署，推荐）
2. sentence-transformers（HuggingFace模型）
"""
from __future__ import annotations

from typing import List, Optional

import requests

from core.engine.base.config import EMBEDDING_CONFIG
from core.logger import log


class EmbeddingService:
    """文本向量化服务，用于将文本转换为向量。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ):
        """
        初始化Embedding服务。

        Args:
            provider: 提供者类型（"ollama" 或 "sentence-transformers"），如果不提供则使用配置中的默认值
            model_name: 模型名称（sentence-transformers使用），如果不提供则使用配置中的默认值
            device: 运行设备（cpu/cuda，sentence-transformers使用），如果不提供则使用配置中的默认值
            batch_size: 批量处理大小，如果不提供则使用配置中的默认值
            ollama_base_url: Ollama服务地址，如果不提供则使用配置中的默认值
            ollama_model: Ollama模型名称，如果不提供则使用配置中的默认值
        """
        self.provider = provider or EMBEDDING_CONFIG.get("provider", "ollama")
        self.model_name = model_name or EMBEDDING_CONFIG.get("model", "")
        self.device = device or EMBEDDING_CONFIG.get("device", "cpu")
        self.batch_size = batch_size or EMBEDDING_CONFIG.get("batch_size", 32)
        self.ollama_base_url = ollama_base_url or EMBEDDING_CONFIG.get("ollama_base_url", "http://localhost:11434")
        self.ollama_model = ollama_model or EMBEDDING_CONFIG.get("ollama_model", "qwen2.5:7b")
        self._model = None
        self._tokenizer = None
        self._vector_dimension = None  # 缓存向量维度

    def _load_model(self) -> None:
        """延迟加载模型（首次使用时加载）。"""
        if self._model is not None:
            return

        if self.provider == "ollama":
            # 使用Ollama API，不需要加载模型
            log.info(f"使用Ollama Embedding服务: {self.ollama_base_url}, 模型: {self.ollama_model}")
            # 测试连接
            try:
                response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    log.info("Ollama服务连接成功")
                else:
                    log.warning(f"Ollama服务响应异常: {response.status_code}")
            except Exception as e:
                log.warning(f"无法连接到Ollama服务: {e}，将尝试使用sentence-transformers")
                # 如果Ollama不可用，回退到sentence-transformers
                self.provider = "sentence-transformers"
        
        if self.provider == "sentence-transformers":
            try:
                log.info(f"正在加载Embedding模型: {self.model_name}")
                log.info("提示: 首次使用需要从HuggingFace下载模型（约471MB），请耐心等待...")

                # 动态导入sentence_transformers（可选依赖）
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError:
                    raise ImportError(
                        "sentence-transformers未安装，请运行: pip install sentence-transformers"
                    )

                self._model = SentenceTransformer(self.model_name, device=self.device)
                log.info(f"Embedding模型加载成功: {self.model_name}")
            except Exception as e:
                log.error(f"加载Embedding模型失败: {e}")
                raise

    def embed_text(self, text: str) -> List[float]:
        """
        将单个文本转换为向量。

        Args:
            text: 输入文本

        Returns:
            向量列表（浮点数列表）
        """
        if not text or not text.strip():
            # 返回零向量（维度取决于模型）
            dim = self.get_vector_dimension()
            return [0.0] * dim

        if self.provider == "ollama":
            return self._embed_with_ollama([text])[0]
        else:
            self._load_model()
            vector = self._model.encode([text], batch_size=1)[0]
        return vector.tolist()
    
    def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
        """使用Ollama API进行向量化"""
        vectors = []
        for text in texts:
            try:
                response = requests.post(
                    f"{self.ollama_base_url}/api/embeddings",
                    json={
                        "model": self.ollama_model,
                        "prompt": text,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                vector = result.get("embedding", [])
                if vector:
                    vectors.append(vector)
                    # 缓存向量维度
                    if self._vector_dimension is None:
                        self._vector_dimension = len(vector)
                else:
                    raise ValueError("Ollama返回的embedding为空")
            except Exception as e:
                log.error(f"Ollama embedding失败: {e}")
                raise RuntimeError(f"使用Ollama进行向量化失败: {e}") from e
        return vectors

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量将文本转换为向量。

        Args:
            texts: 文本列表

        Returns:
            向量列表的列表
        """
        if not texts:
            return []

        # 过滤空文本
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            # 返回空向量列表
            return []

        if self.provider == "ollama":
            return self._embed_with_ollama(valid_texts)
        else:
            self._load_model()
            # 批量处理
            vectors = self._model.encode(valid_texts, batch_size=self.batch_size, show_progress_bar=False)
            return vectors.tolist()

    def get_model_name(self) -> str:
        """
        获取当前使用的模型名称。

        Returns:
            模型名称
        """
        if self.provider == "ollama":
            return f"ollama:{self.ollama_model}"
        else:
            return self.model_name

    def get_vector_dimension(self) -> int:
        """
        获取向量的维度。

        Returns:
            向量维度
        """
        if self._vector_dimension is not None:
            return self._vector_dimension
        
        if self.provider == "ollama":
            # 使用测试文本获取向量维度
            try:
                test_vector = self._embed_with_ollama(["test"])[0]
                self._vector_dimension = len(test_vector)
                return self._vector_dimension
            except Exception as e:
                log.error(f"获取Ollama向量维度失败: {e}")
                # 默认返回一个常见的维度
                return 4096  # Ollama模型常见的维度
        else:
            self._load_model()
            # 使用空字符串获取向量维度
            dummy_vector = self._model.encode([""])[0]
            self._vector_dimension = len(dummy_vector)
            return self._vector_dimension

