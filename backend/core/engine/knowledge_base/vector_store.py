# encoding: utf-8
"""
向量存储服务，使用ChromaDB存储文档向量。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

from app.config import settings
from core.logger import log


class VectorStore:
    """向量存储服务，用于存储和检索文档向量。"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """
        初始化向量存储。

        Args:
            db_path: 数据库路径，如果不提供则使用配置中的默认值
            collection_name: 集合名称，如果不提供则使用配置中的默认值
        """
        import os

        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb未安装，请运行: pip install chromadb\n"
                "或者安装所有依赖: pip install -e ."
            )

        self.db_path = db_path or os.getenv("CHROMA_DB_PATH", "./storage/knowledge_base/vectors")
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "feishu_documents")

        # 确保目录存在
        Path(self.db_path).mkdir(parents=True, exist_ok=True)

        # 初始化ChromaDB客户端
        self._client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False),
        )

        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # 使用余弦相似度
        )

        log.info(f"向量存储初始化成功: {self.db_path}/{self.collection_name}")

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """
        添加文档到向量存储。

        Args:
            texts: 文档文本列表
            metadatas: 文档元数据列表（每个文档一个字典）
            ids: 文档ID列表（可选，如果不提供则自动生成）
            embeddings: 预计算的向量列表（可选，如果不提供则ChromaDB会自动向量化）
        """
        if not texts:
            return

        if ids is None:
            # 自动生成ID
            ids = [f"doc_{i}" for i in range(len(texts))]

        if len(texts) != len(metadatas) or len(texts) != len(ids):
            raise ValueError("texts、metadatas和ids的长度必须一致")

        # 确保元数据是JSON可序列化的
        serialized_metadatas = []
        for meta in metadatas:
            serialized_meta = {}
            for key, value in meta.items():
                # 只保留可序列化的值
                if isinstance(value, (str, int, float, bool, type(None))):
                    serialized_meta[key] = value
                else:
                    serialized_meta[key] = str(value)
            serialized_metadatas.append(serialized_meta)

        try:
            # 如果提供了预计算的向量，使用它们；否则让ChromaDB自动向量化
            if embeddings:
                self._collection.add(
                    documents=texts,
                    metadatas=serialized_metadatas,
                    ids=ids,
                    embeddings=embeddings,
                )
            else:
                # ChromaDB会自动向量化（需要配置embedding函数）
                # 暂时先使用文本，后续可以配置自定义embedding函数
                self._collection.add(
                    documents=texts,
                    metadatas=serialized_metadatas,
                    ids=ids,
                )
            log.info(f"成功添加 {len(texts)} 个文档到向量存储")
        except Exception as e:
            log.error(f"添加文档到向量存储失败: {e}")
            raise

    def search(
        self,
        query_vectors: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档。

        Args:
            query_vectors: 查询向量列表（可选，如果提供则直接使用）
            query_texts: 查询文本列表（可选，如果不提供query_vectors则使用）
            n_results: 返回结果数量
            where: 过滤条件（可选）

        Returns:
            搜索结果列表，每个结果包含文档、元数据和相似度分数
        """
        try:
            # 如果提供了向量，直接使用；否则使用文本（ChromaDB会自动向量化）
            if query_vectors:
                results = self._collection.query(
                    query_embeddings=query_vectors,
                    n_results=n_results,
                    where=where,
                )
            elif query_texts:
                results = self._collection.query(
                    query_texts=query_texts,
                    n_results=n_results,
                    where=where,
                )
            else:
                raise ValueError("必须提供query_vectors或query_texts")

            # 格式化结果
            formatted_results = []
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]

            for i in range(len(documents)):
                formatted_results.append({
                    "id": ids[i],
                    "document": documents[i],
                    "metadata": metadatas[i] or {},
                    "distance": distances[i],
                    "similarity": 1 - distances[i],  # 余弦距离转换为相似度
                })

            return formatted_results

        except Exception as e:
            log.error(f"向量搜索失败: {e}")
            raise

    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> None:
        """
        删除文档。

        Args:
            ids: 要删除的文档ID列表（可选）
            where: 过滤条件（可选）
        """
        try:
            self._collection.delete(ids=ids, where=where)
            log.info(f"成功删除文档: ids={ids}, where={where}")
        except Exception as e:
            log.error(f"删除文档失败: {e}")
            raise

    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息。

        Returns:
            集合信息字典
        """
        count = self._collection.count()
        return {
            "name": self.collection_name,
            "count": count,
            "path": self.db_path,
        }

    def clear(self) -> None:
        """清空集合中的所有文档。"""
        try:
            # 获取所有文档ID
            all_docs = self._collection.get()
            if all_docs["ids"]:
                self._collection.delete(ids=all_docs["ids"])
                log.info("成功清空向量存储")
        except Exception as e:
            log.error(f"清空向量存储失败: {e}")
            raise

