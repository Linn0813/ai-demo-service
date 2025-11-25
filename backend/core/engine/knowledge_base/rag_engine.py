# encoding: utf-8
"""
RAG引擎，实现检索增强生成功能。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from core.engine.base.embedding_service import EmbeddingService
from core.engine.base.llm_service import LLMService
from core.logger import log
from .text_splitter import TextSplitter
from .vector_store import VectorStore


class RAGEngine:
    """RAG引擎，实现检索增强生成。"""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        max_context_length: Optional[int] = None,
    ):
        """
        初始化RAG引擎。

        Args:
            vector_store: 向量存储服务，如果不提供则自动创建
            embedding_service: Embedding服务，如果不提供则自动创建
            llm_service: LLM服务，如果不提供则自动创建
            top_k: 检索返回的文档数量，如果不提供则使用配置中的默认值
            similarity_threshold: 相似度阈值，如果不提供则使用配置中的默认值
            max_context_length: 上下文最大长度，如果不提供则使用配置中的默认值
        """
        # 延迟初始化，只有在实际使用时才创建（避免导入时检查依赖）
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_service = llm_service
        self.text_splitter = TextSplitter(chunk_size=500, chunk_overlap=50)

        # 从环境变量或配置读取参数
        self.top_k = top_k or int(os.getenv("RAG_TOP_K", "5"))
        self.similarity_threshold = similarity_threshold or float(
            os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7")
        )
        self.max_context_length = max_context_length or int(
            os.getenv("RAG_MAX_CONTEXT_LENGTH", "2000")
        )

    @property
    def vector_store(self) -> VectorStore:
        """获取向量存储（延迟初始化）。"""
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store

    @property
    def embedding_service(self) -> EmbeddingService:
        """获取Embedding服务（延迟初始化）。"""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    @property
    def llm_service(self) -> LLMService:
        """获取LLM服务（延迟初始化）。"""
        if self._llm_service is None:
            self._llm_service = LLMService()
        return self._llm_service

    def index_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 10,
    ) -> int:
        """
        索引文档到向量存储。

        Args:
            documents: 文档列表，每个文档包含：
                - content: 文档内容
                - metadata: 文档元数据（包含title、url等）
                - id: 文档ID（可选）
            batch_size: 批量处理大小

        Returns:
            成功索引的文档数量
        """
        indexed_count = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            texts = []
            metadatas = []
            ids = []

            for doc in batch:
                content = doc.get("content", "")
                if not content or not content.strip():
                    continue

                # 分割文本
                chunks = self.text_splitter.split_text(content)

                # 为每个块创建向量
                for chunk_idx, chunk in enumerate(chunks):
                    doc_id = doc.get("id", f"doc_{i}_{chunk_idx}")
                    chunk_id = f"{doc_id}_chunk_{chunk_idx}"

                    texts.append(chunk)
                    metadatas.append({
                        **doc.get("metadata", {}),
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                    })
                    ids.append(chunk_id)

            if texts:
                # 批量向量化
                vectors = self.embedding_service.embed_batch(texts)

                # 添加到向量存储（使用预计算的向量）
                self.vector_store.add_documents(
                    texts=texts,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=vectors,
                )

                indexed_count += len(texts)

        log.info(f"成功索引 {indexed_count} 个文档块")
        return indexed_count

    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        搜索相关文档。

        Args:
            query: 查询文本
            top_k: 返回结果数量，如果不提供则使用默认值

        Returns:
            搜索结果列表，每个结果包含文档、元数据和相似度
        """
        if not query or not query.strip():
            return []

        top_k = top_k or self.top_k

        # 将查询向量化
        query_vector = self.embedding_service.embed_text(query)

        # 在向量存储中搜索
        results = self.vector_store.search(
            query_vectors=[query_vector],
            n_results=top_k,
        )

        # 过滤低相似度结果
        filtered_results = [
            result
            for result in results
            if result.get("similarity", 0) >= self.similarity_threshold
        ]

        return filtered_results

    def generate_answer(
        self,
        question: str,
        context_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        生成答案。

        Args:
            question: 用户问题
            context_documents: 上下文文档列表，如果不提供则自动检索

        Returns:
            答案字典，包含：
                - answer: 生成的答案
                - sources: 引用来源列表
                - context: 使用的上下文
        """
        # 如果没有提供上下文文档，则自动检索
        if context_documents is None:
            context_documents = self.search(question)

        # 构建上下文
        context_parts = []
        sources = []

        for doc in context_documents:
            content = doc.get("document", "")
            metadata = doc.get("metadata", {})
            similarity = doc.get("similarity", 0)

            if content:
                context_parts.append(content)
                sources.append({
                    "title": metadata.get("title", "未知标题"),
                    "url": metadata.get("url", ""),
                    "similarity": similarity,
                })

        # 限制上下文长度
        context = "\n\n".join(context_parts)
        if len(context) > self.max_context_length:
            context = context[: self.max_context_length] + "..."

        # 构建Prompt
        prompt = self._build_qa_prompt(question, context)

        # 生成答案
        try:
            answer = self.llm_service.generate(prompt)
        except Exception as e:
            log.error(f"生成答案失败: {e}")
            answer = "抱歉，生成答案时出现错误，请稍后重试。"

        return {
            "answer": answer.strip(),
            "sources": sources,
            "context": context,
        }

    def _build_qa_prompt(self, question: str, context: str) -> str:
        """
        构建问答Prompt。

        Args:
            question: 用户问题
            context: 上下文文档

        Returns:
            完整的Prompt
        """
        return f"""你是一位专业的AI助手，擅长从提供的文档内容中回答问题。

请仔细阅读以下文档内容，然后回答用户的问题。

【文档内容】
{context}

【用户问题】
{question}

【要求】
1. 基于提供的文档内容回答问题
2. 如果文档中没有相关信息，请明确说明"根据提供的文档，没有找到相关信息"
3. 答案要准确、简洁、有条理
4. 如果文档中有多个相关信息，请综合回答
5. 使用简体中文回答

【答案】
"""

    def qa(self, question: str) -> Dict[str, Any]:
        """
        完整的问答流程：检索 + 生成答案。

        Args:
            question: 用户问题

        Returns:
            答案字典，包含answer、sources、context
        """
        log.info(f"处理问题: {question}")

        # 检索相关文档
        context_documents = self.search(question)
        log.info(f"检索到 {len(context_documents)} 个相关文档")

        # 生成答案
        result = self.generate_answer(question, context_documents)

        return result

