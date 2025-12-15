# encoding: utf-8
"""
知识库服务层，封装知识库相关业务逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

from infrastructure.external.feishu.loader import FeishuDocumentLoader
from infrastructure.vector_store.chroma import VectorStore
from domain.knowledge_base.rag import RAGEngine
from shared.logger import log

class KnowledgeBaseService:
    """知识库服务，提供文档同步和问答功能。"""

    def __init__(self):
        """初始化知识库服务。"""
        self.document_loader = FeishuDocumentLoader()
        self._rag_engine = None
        self._web_search_service = None
        # 创建结果保存目录
        project_root = Path(__file__).parent.parent.parent
        self.results_dir = project_root / 'data' / 'query_results'
        self.results_dir.mkdir(parents=True, exist_ok=True)

    @property
    def rag_engine(self) -> RAGEngine:
        """
        获取RAG引擎（延迟初始化）。
        
        Returns:
            RAG引擎实例
            
        Raises:
            ImportError: 如果缺少必要的依赖
        """
        if self._rag_engine is None:
            try:
                self._rag_engine = RAGEngine()
            except ImportError as e:
                raise ImportError(
                    f"知识库功能不可用（缺少依赖）: {e}\n"
                    "请安装依赖: pip install sentence-transformers chromadb"
                ) from e
        return self._rag_engine

    def sync_documents_from_space(self, space_id: str, incremental: bool = True) -> Dict[str, Any]:
        """
        从知识库空间同步文档（支持增量同步）。

        Args:
            space_id: 知识库空间ID
            incremental: 是否使用增量同步（默认True）

        Returns:
            同步结果，包含同步的文档数量和状态
        """
        try:
            log.info(f"开始同步知识库空间: {space_id} (增量模式: {incremental})")

            # 加载所有文档
            documents = self.document_loader.load_all_documents_from_space(space_id)

            if not documents:
                return {
                    "success": False,
                    "message": "未找到文档",
                    "document_count": 0,
                    "new_count": 0,
                    "updated_count": 0,
                    "skipped_count": 0,
                }

            # 增量同步：获取已有文档的更新时间
            existing_docs = {}
            if incremental:
                existing_docs = self.rag_engine.vector_store.get_documents_by_space(space_id)
                log.info(f"向量库中已有 {len(existing_docs)} 个文档")
            
            # 辅助函数：比较更新时间
            def compare_update_time(time1: Any, time2: Any) -> int:
                """
                比较两个更新时间，返回：
                -1: time1 < time2
                 0: time1 == time2
                 1: time1 > time2
                """
                if not time1 or not time2:
                    return 0  # 如果任一时间为空，认为相等（需要同步）
                
                # 转换为整数时间戳进行比较
                try:
                    t1 = int(time1) if isinstance(time1, (int, str)) else 0
                    t2 = int(time2) if isinstance(time2, (int, str)) else 0
                    if t1 < t2:
                        return -1
                    elif t1 > t2:
                        return 1
                    else:
                        return 0
                except (ValueError, TypeError):
                    # 如果转换失败，认为需要同步
                    return 0

            # 准备文档数据（只同步新增或更新的文档）
            doc_data = []
            new_count = 0
            updated_count = 0
            skipped_count = 0
            current_doc_tokens = set()

            for doc in documents:
                doc_token = doc["token"]
                current_doc_tokens.add(doc_token)
                doc_update_time = doc["meta"].get("update_time")
                
                # 增量同步：检查是否需要更新
                if incremental and doc_token in existing_docs:
                    existing_update_time = existing_docs[doc_token].get("update_time")
                    # 比较更新时间
                    cmp_result = compare_update_time(doc_update_time, existing_update_time)
                    if cmp_result <= 0:  # 文档未更新或时间相同
                        skipped_count += 1
                        log.debug(f"跳过未更新的文档: {doc['meta'].get('title', '未知')} (更新时间: {doc_update_time})")
                        continue
                    updated_count += 1
                    log.debug(f"文档已更新: {doc['meta'].get('title', '未知')} (旧: {existing_update_time}, 新: {doc_update_time})")
                else:
                    new_count += 1

                doc_data.append({
                    "id": doc_token,
                    "content": doc["content"],
                    "metadata": {
                        "title": doc["meta"].get("title", "未知标题"),
                        "url": doc["meta"].get("url", ""),
                        "space_id": space_id,
                        "document_id": doc["meta"].get("document_id", ""),
                        "update_time": doc_update_time,  # 添加更新时间
                    },
                })

            # 删除已不存在的文档（增量同步时）
            deleted_count = 0
            if incremental and existing_docs:
                deleted_tokens = set(existing_docs.keys()) - current_doc_tokens
                if deleted_tokens:
                    log.info(f"发现 {len(deleted_tokens)} 个已删除的文档，准备清理...")
                    for deleted_token in deleted_tokens:
                        # 删除该文档的所有chunk（chunk_id格式：{token}_chunk_{idx}）
                        try:
                            # 查询该文档的所有chunk
                            all_docs = self.rag_engine.vector_store._collection.get(
                                where={"space_id": space_id}
                            )
                            chunk_ids_to_delete = [
                                doc_id for doc_id in all_docs.get("ids", [])
                                if doc_id.startswith(f"{deleted_token}_chunk_") or doc_id == deleted_token
                            ]
                            if chunk_ids_to_delete:
                                self.rag_engine.vector_store.delete(ids=chunk_ids_to_delete)
                                deleted_count += 1
                                log.info(f"已删除文档: {deleted_token}")
                        except Exception as e:
                            log.warning(f"删除文档失败 {deleted_token}: {e}")

            # 如果有需要同步的文档，先删除旧版本再索引新版本
            if doc_data:
                # 先删除需要更新的文档的旧版本
                if incremental:
                    tokens_to_update = {doc["id"] for doc in doc_data}
                    for token in tokens_to_update:
                        try:
                            all_docs = self.rag_engine.vector_store._collection.get(
                                where={"space_id": space_id}
                            )
                            chunk_ids_to_delete = [
                                doc_id for doc_id in all_docs.get("ids", [])
                                if doc_id.startswith(f"{token}_chunk_") or doc_id == token
                            ]
                            if chunk_ids_to_delete:
                                self.rag_engine.vector_store.delete(ids=chunk_ids_to_delete)
                        except Exception as e:
                            log.warning(f"删除旧版本失败 {token}: {e}")

                # 索引文档
                indexed_count = self.rag_engine.index_documents(doc_data)
            else:
                indexed_count = 0
                log.info("没有需要同步的文档")

            return {
                "success": True,
                "message": "同步成功",
                "document_count": len(documents),
                "new_count": new_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "deleted_count": deleted_count,
                "indexed_count": indexed_count,
            }

        except Exception as e:
            log.error(f"同步文档失败: {e}")
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "document_count": 0,
                "new_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "deleted_count": 0,
            }

    def sync_all_spaces(self, incremental: bool = True) -> Dict[str, Any]:
        """
        同步所有知识库空间。

        Args:
            incremental: 是否使用增量同步（默认True）

        Returns:
            同步结果
        """
        try:
            # 获取所有知识库空间
            spaces = self.document_loader.load_wiki_spaces()

            total_documents = 0
            total_new = 0
            total_updated = 0
            total_skipped = 0
            total_deleted = 0
            success_count = 0
            failed_spaces = []

            for space in spaces:
                space_id = space.get("space_id", "")
                space_name = space.get("name", "未知")

                if not space_id:
                    continue

                log.info(f"同步知识库空间: {space_name} ({space_id})")

                result = self.sync_documents_from_space(space_id, incremental=incremental)
                if result["success"]:
                    success_count += 1
                    total_documents += result["document_count"]
                    total_new += result.get("new_count", 0)
                    total_updated += result.get("updated_count", 0)
                    total_skipped += result.get("skipped_count", 0)
                    total_deleted += result.get("deleted_count", 0)
                else:
                    failed_spaces.append({
                        "space_id": space_id,
                        "name": space_name,
                        "error": result["message"],
                    })

            sync_mode = "增量" if incremental else "全量"
            return {
                "success": True,
                "message": f"同步完成（{sync_mode}模式）：成功 {success_count} 个，失败 {len(failed_spaces)} 个",
                "total_spaces": len(spaces),
                "success_count": success_count,
                "failed_count": len(failed_spaces),
                "total_documents": total_documents,
                "new_count": total_new,
                "updated_count": total_updated,
                "skipped_count": total_skipped,
                "deleted_count": total_deleted,
                "failed_spaces": failed_spaces,
            }

        except Exception as e:
            error_msg = str(e)
            log.error(f"同步所有知识库失败: {e}")
            
            # 检查是否是权限错误，如果是则重新抛出以便API层处理
            is_auth_error = (
                "99991672" in error_msg or 
                "99991663" in error_msg or 
                "99991664" in error_msg or 
                "99991679" in error_msg or
                "权限" in error_msg or 
                "Access denied" in error_msg or
                "unauthorized" in error_msg.lower() or
                "forbidden" in error_msg.lower()
            )
            if is_auth_error:
                raise  # 重新抛出异常，让API层返回403
            
            return {
                "success": False,
                "message": f"同步失败: {error_msg}",
                "total_spaces": 0,
                "success_count": 0,
                "failed_count": 0,
                "total_documents": 0,
            }

    @property
    def web_search_service(self):
        """获取网络搜索服务（延迟初始化）"""
        if self._web_search_service is None:
            try:
                from infrastructure.external.web_search import WebSearchService
                self._web_search_service = WebSearchService()
            except Exception as e:
                log.warning(f"网络搜索服务不可用: {e}")
                self._web_search_service = None
        return self._web_search_service

    def ask(self, question: str, use_realtime_search: bool = True, space_id: Optional[str] = None, use_web_search: bool = False) -> Dict[str, Any]:
        """
        回答问题。
        
        支持两种模式：
        1. 实时搜索模式（默认）：直接使用飞书API搜索，无需先同步文档
        2. 向量搜索模式：使用本地向量存储进行语义搜索（需要先同步文档）

        Args:
            question: 用户问题
            use_realtime_search: 是否使用实时搜索模式（默认True）
            space_id: 指定搜索的知识库空间ID，如果不提供则搜索所有空间
            use_web_search: 是否启用网络搜索（默认False）。当知识库结果不理想时，会使用网络搜索补充

        Returns:
            答案和引用来源
        """
        try:
            # 检查向量存储中是否有文档
            collection_info = self.get_collection_info()
            has_local_docs = (
                collection_info.get("success") 
                and collection_info.get("info", {}).get("count", 0) > 0
            )
            
            # 如果向量存储为空，自动使用实时搜索模式
            if not has_local_docs:
                log.info("向量存储为空，使用实时搜索模式")
                use_realtime_search = True
            
            if use_realtime_search:
                kb_result = self._ask_with_realtime_search(question, space_id=space_id)
                
                # 计算最高相似度，用于判断是否需要网络搜索
                sources = kb_result.get("sources", [])
                max_similarity = max([s.get("similarity", 0) for s in sources]) if sources else 0.0
                
                # 判断是否建议使用网络搜索
                suggest_web_search = self._should_use_web_search(question, kb_result)
                
                # 如果启用了网络搜索，且知识库结果不理想，尝试网络搜索
                if use_web_search and suggest_web_search:
                    log.info("🌐 知识库结果不理想，尝试使用网络搜索补充...")
                    web_result = self._search_web_and_merge(question, kb_result)
                    return web_result
                
                # 如果未启用网络搜索，但建议使用，在结果中添加建议信息
                if not use_web_search:
                    kb_result["suggest_web_search"] = suggest_web_search
                    kb_result["max_similarity"] = max_similarity
                    if suggest_web_search:
                        log.info(f"💡 建议使用网络搜索（最高相似度: {max_similarity:.3f}）")
                
                return kb_result
            else:
                # 使用向量搜索模式（暂不支持指定space_id，搜索所有文档）
                if space_id:
                    log.warning("向量搜索模式暂不支持指定知识库，将搜索所有文档")
            result = self.rag_engine.qa(question)
            return {
                "success": True,
                "answer": result["answer"],
                "sources": result["sources"],
            }

        except Exception as e:
            log.error(f"回答问题失败: {e}")
            return {
                "success": False,
                "answer": f"抱歉，处理问题时出现错误: {str(e)}",
                "sources": [],
            }
    
    def get_wiki_spaces(self) -> Dict[str, Any]:
        """
        获取所有知识库空间列表。
        
        Returns:
            知识库空间列表
        """
        try:
            spaces = self.document_loader.load_wiki_spaces()
            space_list = []
            for space in spaces:
                space_list.append({
                    "space_id": space.get("space_id", ""),
                    "name": space.get("name", "未知"),
                    "description": space.get("description", ""),
                })
            
            return {
                "success": True,
                "spaces": space_list,
                "message": f"找到 {len(space_list)} 个知识库空间",
            }
        except Exception as e:
            log.error(f"获取知识库空间列表失败: {e}")
            error_msg = str(e)
            # 检查是否是权限错误（包括各种权限错误码）
            is_auth_error = (
                "99991672" in error_msg or 
                "99991663" in error_msg or 
                "99991664" in error_msg or 
                "99991679" in error_msg or
                "权限" in error_msg or 
                "Access denied" in error_msg or
                "unauthorized" in error_msg.lower() or
                "forbidden" in error_msg.lower()
            )
            if is_auth_error:
                return {
                    "success": False,
                    "spaces": [],
                    "message": f"权限不足: {error_msg}。请先进行飞书授权。",
                }
            return {
                "success": False,
                "spaces": [],
                "message": f"获取知识库空间列表失败: {error_msg}",
            }
    
    def _save_query_result(self, question: str, step: str, data: Dict[str, Any], query_timestamp: Optional[str] = None):
        """保存查询结果到文件"""
        try:
            # 如果提供了query_timestamp，使用它；否则生成新的
            if query_timestamp is None:
                query_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            filename = f"query_{query_timestamp}.json"
            filepath = self.results_dir / filename
            
            # 如果文件已存在，追加数据；否则创建新文件
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
            else:
                result_data = {
                    "question": question,
                    "timestamp": query_timestamp,
                    "steps": {}
                }
            
            result_data["steps"][step] = {
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "data": data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            log.info(f"💾 查询结果已保存到: {filepath} (步骤: {step})")
            return query_timestamp  # 返回时间戳，供后续步骤使用
        except Exception as e:
            log.warning(f"保存查询结果失败: {e}")
            return None
    
    def _ask_with_realtime_search(self, question: str, space_id: Optional[str] = None) -> Dict[str, Any]:
        """
        使用实时搜索模式回答问题（直接使用飞书API搜索，无需同步文档）。
        
        优化策略：
        1. 提取关键词进行多轮搜索
        2. 使用embedding对搜索结果进行重排序
        3. 智能提取文档相关片段
        4. 并行搜索多个空间
        
        Args:
            question: 用户问题
            
        Returns:
            答案和引用来源
        """
        try:
            from infrastructure.llm.service import LLMService
            from infrastructure.embedding.service import EmbeddingService
            import re
            
            log.info("="*80)
            log.info(f"🔍 使用实时搜索模式处理问题: {question}")
            log.info("="*80)
            
            # 生成查询时间戳（所有步骤使用同一个时间戳）
            query_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存问题
            self._save_query_result(question, "question", {"question": question, "space_id": space_id}, query_timestamp)
            
            # 获取知识空间列表
            if space_id:
                # 如果指定了space_id，只搜索该空间
                log.info(f"指定搜索知识库空间: {space_id}")
                # 先获取所有空间以验证space_id是否存在
                all_spaces = self.document_loader.load_wiki_spaces()
                spaces = [s for s in all_spaces if s.get("space_id") == space_id]
                if not spaces:
                    return {
                        "success": False,
                        "answer": f"未找到指定的知识库空间（ID: {space_id}），请检查空间ID是否正确",
                        "sources": [],
                    }
                # 找到匹配的空间，记录空间名称
                matched_space = spaces[0]
                log.info(f"找到指定的知识库空间: {matched_space.get('name', '未知')} ({space_id})")
            else:
                # 如果没有指定space_id，搜索所有空间
                spaces = self.document_loader.load_wiki_spaces()
                if not spaces:
                    return {
                        "success": False,
                        "answer": "未找到知识库空间，请检查权限配置",
                        "sources": [],
                    }
                log.info(f"将搜索所有 {len(spaces)} 个知识库空间")
            
            # 【问题类型识别】检测问题类型
            question_type_info = self._detect_question_type(question)
            question_type = question_type_info.get("type", "content_qa")
            type_confidence = question_type_info.get("confidence", 0.5)
            subtype = question_type_info.get("subtype", "normal")
            
            log.info(f"📋 问题类型识别:")
            log.info(f"  类型: {question_type} ({subtype})")
            log.info(f"  置信度: {type_confidence:.2f}")
            
            # 【AI分析问题】使用LLM分析问题并提取搜索关键词和策略
            search_strategy = self._analyze_question_with_ai(question)
            keywords = search_strategy.get("keywords", [])
            search_queries = search_strategy.get("search_queries", [question])
            related_concepts = search_strategy.get("related_concepts", [])
            
            # 如果是文档列表查询，优先使用检测到的关键词
            if question_type == "document_list" and question_type_info.get("keywords"):
                keywords = list(set(keywords + question_type_info["keywords"]))
            
            log.info(f"📊 AI分析结果:")
            log.info(f"  关键词: {keywords}")
            log.info(f"  搜索查询: {search_queries}")
            log.info(f"  相关概念: {related_concepts}")
            
            # 保存AI分析结果
            self._save_query_result(question, "ai_analysis", {
                "keywords": keywords,
                "search_queries": search_queries,
                "related_concepts": related_concepts
            }, query_timestamp)
            
            # 优化搜索查询：去除疑问词，提取核心关键词
            # 飞书搜索API不支持包含疑问词的完整问题，需要提取关键词
            import re
            def clean_query(query: str) -> str:
                """清理查询词，去除疑问词和标点"""
                # 去除常见的疑问词
                question_words = ['什么', '什么是', '是什么', '如何', '怎么', '为什么', '哪个', '哪些', '吗', '呢', '？', '?']
                cleaned = query
                for word in question_words:
                    cleaned = cleaned.replace(word, ' ')
                # 去除多余空格和标点
                cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', cleaned)
                cleaned = ' '.join(cleaned.split())
                return cleaned.strip()
            
            # 构建搜索查询列表：优先使用关键词，然后使用清理后的查询
            final_search_queries = []
            
            # 1. 使用提取的关键词（最重要）
            if keywords:
                # 使用前2个最重要的关键词
                for kw in keywords[:2]:
                    if kw and len(kw) >= 2:
                        final_search_queries.append(kw)
            
            # 2. 使用清理后的原始问题（去除疑问词）
            cleaned_question = clean_query(question)
            if cleaned_question and cleaned_question not in final_search_queries:
                final_search_queries.append(cleaned_question)
            
            # 3. 如果AI生成的搜索查询中有好的关键词，也加入
            for query in search_queries[:2]:
                cleaned = clean_query(query)
                if cleaned and cleaned not in final_search_queries and len(cleaned) >= 2:
                    final_search_queries.append(cleaned)
            
            # 去重并限制数量
            seen = set()
            unique_queries = []
            for q in final_search_queries:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    unique_queries.append(q)
            
            search_queries = unique_queries[:3]  # 最多3个查询
            log.info(f"🔍 优化后的搜索查询（去除疑问词）: {search_queries}")
            
            # 保存优化后的搜索查询
            self._save_query_result(question, "search_queries", {
                "final_queries": search_queries,
                "original_queries": search_strategy.get("search_queries", [])
            }, query_timestamp)
            
            # 在所有空间中搜索（使用AI提取的搜索策略）
            all_results = []
            client = self.document_loader.client
            
            import time
            
            # 如果指定了space_id，只搜索该空间；否则限制搜索的空间数量
            if space_id:
                # 指定了space_id，只搜索该空间（spaces已经过滤过了）
                spaces_to_search = spaces
                log.info(f"将搜索指定的知识库空间: {spaces[0].get('name', '未知')}")
            else:
                # 限制搜索的空间数量，优先搜索前3个空间
                spaces_to_search = spaces[:3] if len(spaces) > 3 else spaces
                if len(spaces) > 3:
                    log.info(f"优化：限制搜索空间数量为 {len(spaces_to_search)} 个，避免频率限制")
            
            for space_idx, space_item in enumerate(spaces_to_search):
                current_space_id = space_item.get("space_id", "")
                space_name = space_item.get("name", "未知")
                
                if not current_space_id:
                    continue
                
                # 每个空间之间添加延迟（第一个空间不需要延迟）
                if space_idx > 0:
                    time.sleep(1.0)  # 每个空间之间延迟1秒
                
                # 尝试多个搜索词（添加延迟以避免频率限制）
                for idx, query in enumerate(search_queries):
                    try:
                        # 每个查询之间添加延迟（第一个查询不需要延迟）
                        if idx > 0:
                            time.sleep(1.0)  # 每个查询间隔1秒（增加延迟时间）
                        
                        log.info(f"搜索知识库: {space_name} - 查询: {query}")
                        search_result = client.search_wiki_nodes(
                            space_id=current_space_id,
                            query=query,
                            limit=20  # 增加搜索数量
                        )
                        
                        if search_result.get("code") == 0:
                            items = search_result.get("data", {}).get("items", [])
                            log.info(f"在知识库 {space_name} 中找到 {len(items)} 个文档（查询: {query}）")
                            for item in items:
                                # 打印第一个item的所有字段以便调试
                                if len(all_results) == 0:
                                    import json
                                    log.info(f"📋 搜索结果原始数据结构（第一个item）: {json.dumps(item, indent=2, ensure_ascii=False)}")
                                
                                obj_token = item.get("obj_token", "")
                                # 飞书搜索API返回的字段可能是 node_token（字符串token），而不是 node_id（数字ID）
                                # 检查所有可能的字段名
                                node_token = item.get("node_token", "") or item.get("node_id", "")
                                # 如果 node_token 是字符串，说明它就是我们要用的token
                                # 如果 node_id 是数字，说明它是真正的数字ID
                                node_id = item.get("node_id", "")
                                # 如果 node_id 是字符串token，说明字段映射有问题，应该使用 node_token
                                if node_id and not str(node_id).isdigit():
                                    # node_id 是字符串token，说明它实际上是 node_token
                                    node_token = node_id
                                    node_id = ""  # 清空，因为没有真正的数字ID
                                
                                title = item.get("title", "未知标题")
                                
                                # 去重（基于obj_token，如果没有则使用node_token）
                                unique_key = obj_token or node_token or node_id
                                if not any(r.get("obj_token") == obj_token or 
                                          r.get("node_id") == node_id or 
                                          r.get("node_token") == node_token 
                                          for r in all_results):
                                    # 从搜索结果中提取URL（搜索API返回的结果包含url字段）
                                    url = item.get("url", "")
                                    all_results.append({
                                        "title": title,
                                        "obj_token": obj_token,
                                        "node_id": node_id,  # 保存node_id（数字ID，如果有）
                                        "node_token": node_token,  # 保存node_token（字符串token，用于wiki API）
                                        "space_id": current_space_id,
                                        "space_name": space_name,
                                        "search_query": query,  # 记录匹配的搜索词
                                        "url": url,  # 保存URL（搜索API返回的）
                                    })
                    except Exception as e:
                        error_str = str(e)
                        log.warning(f"搜索知识空间 {space_name} (查询: {query}) 失败: {e}")
                        
                        # 如果是频率限制错误，等待更长时间并跳过后续查询
                        if "frequency limit" in error_str.lower() or "99991400" in error_str:
                            log.warning("检测到频率限制，等待5秒后跳过当前空间...")
                            time.sleep(5)  # 等待5秒
                            break  # 跳过当前空间的其他查询
                        continue
                    
                    # 如果已经找到足够的结果，可以提前停止
                    if len(all_results) >= 20:
                        log.info(f"已找到足够的结果（{len(all_results)}个），提前停止搜索")
                        break
                
                # 如果已经找到足够的结果，提前停止搜索所有空间
                if len(all_results) >= 20:
                    break
            
            if not all_results:
                return {
                    "success": True,
                    "answer": "抱歉，未找到相关文档。建议：\n1. 尝试使用不同的关键词\n2. 或者先同步文档以获得更好的语义搜索效果",
                    "sources": [],
                }
            
            log.info(f"📚 找到 {len(all_results)} 个候选文档，开始加载内容并重排序...")
            
            # 保存搜索结果
            self._save_query_result(question, "search_results", {
                "total_count": len(all_results),
                "documents": [
                    {
                        "title": r.get("title", "未知"),
                        "url": r.get("url", ""),
                        "space_name": r.get("space_name", ""),
                        "search_query": r.get("search_query", "")
                    }
                    for r in all_results[:20]  # 只保存前20个
                ]
            }, query_timestamp)
            
            # 加载文档内容并计算相似度
            doc_results = []
            import time
            
            # 从搜索结果中提取URL（如果有）
            log.info(f"📋 准备加载 {len(all_results)} 个文档的内容（限制加载前15个）...")
            for idx, result in enumerate(all_results[:15]):  # 限制加载数量以提高性能
                log.info(f"📋 [{idx+1}/{min(len(all_results), 15)}] 处理文档: {result.get('title', '未知标题')}")
                try:
                    # 添加延迟以避免频率限制（每3个文档间隔0.5秒）
                    if idx > 0 and idx % 3 == 0:
                        time.sleep(0.5)
                    
                    # 尝试获取文档内容（知识库搜索返回的都是wiki节点）
                    doc_content = None
                    doc_meta = None
                    title = result.get("title", "未知标题")
                    url = result.get("url", "")  # 搜索返回的结果包含URL
                    node_id = result.get("node_id", "")
                    
                    # 如果搜索结果中没有URL，尝试从node_id构建
                    if not url and node_id:
                        # 从node_id构建wiki URL（格式：https://xxx.feishu.cn/wiki/{node_id}）
                        # 但我们需要知道域名，所以先尝试获取
                        pass  # 暂时跳过，使用搜索结果中的URL
                    
                    # 尝试获取文档内容（优化：优先使用搜索结果中的obj_token和obj_type，避免不必要的wiki API调用）
                    doc_content = None
                    try:
                        node_id = result.get("node_id", "")
                        node_token = result.get("node_token", "")
                        obj_token = result.get("obj_token", "")
                        obj_type = result.get("obj_type", "")
                        
                        # 打印搜索结果的所有字段以便调试
                        import json
                        result_keys = list(result.keys())
                        log.info(f"📋 搜索结果字段: {result_keys}")
                        log.info(f"📋 关键字段值: node_id={node_id[:30] if node_id else 'None'}... (类型: {type(node_id).__name__}), node_token={node_token[:30] if node_token else 'None'}..., obj_token={obj_token[:30] if obj_token else 'None'}..., obj_type={obj_type}")
                        
                        # 优化策略：如果搜索结果中已经有obj_token和obj_type，直接使用，避免不必要的wiki API调用
                        if obj_token:
                            # 如果obj_type是docx（类型8），直接使用docx API，跳过wiki API
                            if obj_type == "docx" or obj_type == 8:
                                log.info(f"📋 检测到obj_type={obj_type}（docx），直接使用obj_token调用docx API，跳过wiki API")
                                doc_content = self.document_loader.load_document_content(obj_token, is_wiki_node=False)
                                if doc_content and len(doc_content.strip()) >= 10:
                                    log.info(f"✅ 直接使用obj_token获取docx文档内容成功，长度: {len(doc_content)} 字符")
                                else:
                                    log.warning(f"⚠️ 使用obj_token获取docx文档内容失败（长度: {len(doc_content) if doc_content else 0}）")
                            else:
                                # obj_type不是docx，先尝试作为普通文档，失败后再尝试wiki API
                                log.info(f"📋 检测到obj_type={obj_type}，先尝试作为普通文档获取内容")
                                doc_content = self.document_loader.load_document_content(obj_token, is_wiki_node=False)
                                if doc_content and len(doc_content.strip()) >= 10:
                                    log.info(f"✅ 使用obj_token作为普通文档成功获取内容，长度: {len(doc_content)} 字符")
                                else:
                                    log.info(f"📋 obj_token作为普通文档失败，尝试作为wiki节点...")
                                    doc_content = self.document_loader.load_document_content(obj_token, is_wiki_node=True)
                                    if doc_content and len(doc_content.strip()) >= 10:
                                        log.info(f"✅ 使用obj_token作为wiki节点成功获取内容，长度: {len(doc_content)} 字符")
                                    else:
                                        log.warning(f"⚠️ 使用obj_token获取文档内容失败（长度: {len(doc_content) if doc_content else 0}）")
                        
                        # 如果没有obj_token，或者使用obj_token失败，才尝试使用wiki API
                        if not doc_content or len(doc_content.strip()) < 10:
                            # wiki API需要使用node_token（字符串token），而不是node_id（数字ID）
                            # 根据飞书API文档，wiki/v2/nodes/{node_token} 需要使用node_token（字符串）
                            # 如果node_id是字符串token，说明字段映射有问题，应该使用node_token
                            if node_id and not str(node_id).isdigit():
                                # node_id 是字符串token，说明它实际上是 node_token
                                log.debug(f"node_id字段包含字符串token，使用node_token")
                                node_token = node_id
                                node_id = ""
                            
                            # 优先使用node_token（字符串token），如果没有则使用node_id（数字ID）
                            wiki_node_token = node_token or node_id
                            
                            if wiki_node_token:
                                log.info(f"📋 尝试使用wiki API获取节点信息: {wiki_node_token[:30]}...")
                                try:
                                    # 先获取wiki节点信息，可能包含obj_token
                                    wiki_result = self.document_loader.client.get_wiki_node_content(wiki_node_token)
                                    if wiki_result.get("code") == 0:
                                        log.info(f"✅ wiki API获取节点信息成功")
                                        wiki_data = wiki_result.get("data", {})
                                        wiki_node = wiki_data.get("node", {})
                                        if wiki_node:
                                            # 从wiki节点中提取obj_token（文档的实际token）
                                            actual_obj_token = wiki_node.get("obj_token", "")
                                            actual_obj_type = wiki_node.get("obj_type", "")
                                            
                                            log.info(f"📋 从wiki节点提取信息 - obj_token: {actual_obj_token[:30] if actual_obj_token else 'None'}..., obj_type: {actual_obj_type}")
                                            
                                            if actual_obj_token:
                                                log.info(f"📋 使用从wiki节点获取的obj_token获取文档内容: {actual_obj_token[:30]}...")
                                                # 使用实际的obj_token获取文档内容
                                                # 如果obj_type是docx，说明obj_token是文档token，不是wiki节点
                                                if actual_obj_type == "docx" or actual_obj_type == 8:
                                                    log.info(f"📋 obj_type是docx，使用docs/docx API")
                                                    doc_content = self.document_loader.load_document_content(actual_obj_token, is_wiki_node=False)
                                                else:
                                                    log.info(f"📋 obj_type是{actual_obj_type}，先尝试wiki API，失败后尝试docs/docx API")
                                                    doc_content = self.document_loader.load_document_content(actual_obj_token, is_wiki_node=True)
                                                if doc_content and len(doc_content.strip()) >= 10:
                                                    log.info(f"✅ 通过wiki API成功获取文档内容，长度: {len(doc_content)} 字符")
                                                else:
                                                    log.warning(f"⚠️ 获取文档内容失败或内容为空（长度: {len(doc_content) if doc_content else 0}）")
                                            else:
                                                log.info(f"📋 wiki节点没有obj_token，尝试直接加载节点内容")
                                                # 如果wiki节点直接包含内容，尝试直接加载
                                                doc_content = self.document_loader.load_document_content(wiki_node_token, is_wiki_node=True)
                                                if doc_content and len(doc_content.strip()) >= 10:
                                                    log.info(f"✅ 通过wiki API直接获取节点内容成功，长度: {len(doc_content)} 字符")
                                                else:
                                                    log.warning(f"⚠️ 直接加载节点内容失败或内容为空（长度: {len(doc_content) if doc_content else 0}）")
                                    else:
                                        error_code = wiki_result.get("code")
                                        error_msg = wiki_result.get("msg", "")
                                        log.debug(f"wiki API返回错误: {error_msg} (code: {error_code})")
                                except Exception as e:
                                    error_str = str(e)
                                    if "404" in error_str or "99991679" in error_str:
                                        log.debug(f"wiki API权限不足或404: {type(e).__name__}: {str(e)[:200]}")
                                    else:
                                        log.debug(f"wiki API获取节点信息失败: {type(e).__name__}: {str(e)[:200]}")
                        if doc_content and len(doc_content.strip()) >= 10:
                            # 成功获取内容，尝试获取元信息
                            try:
                                doc_meta = self.document_loader.load_document_meta(result["obj_token"])
                                if doc_meta:
                                    title = doc_meta.get("title", title)
                                    # 如果元信息中有URL，优先使用
                                    meta_url = doc_meta.get("url", "")
                                    if meta_url:
                                        url = meta_url
                            except Exception:
                                # 元信息获取失败不影响，使用搜索结果中的信息
                                pass
                    except Exception as e:
                        # 静默处理，不输出大量错误日志（这些错误是预期的，因为权限不足）
                        # 只在DEBUG级别记录
                        log.debug(f"无法获取文档 {title} 的完整内容（权限限制）: {type(e).__name__}")
                        # 如果无法获取内容，继续处理，至少保留标题和URL
                    
                    # 如果无法获取文档内容，但至少保留标题和URL作为来源
                    if not doc_content or len(doc_content.strip()) < 10:
                        # 如果没有内容，但至少保留标题和URL
                        if title and title != "未知标题":
                            # 使用标题作为内容片段（至少让用户知道找到了相关文档）
                            log.info(f"⚠️ 文档 {title} 无法获取完整内容，但保留标题和URL")
                            doc_results.append({
                                "title": title,
                                "url": url,
                                "content": f"文档标题：{title}",
                                "full_content": "",
                                "similarity": 0.5,  # 给予中等相似度，因为至少标题匹配
                                "obj_token": result.get("obj_token", ""),
                                "has_content": False,  # 标记为没有完整内容
                            })
                        else:
                            log.warning(f"⚠️ 文档标题为空，跳过: obj_token={result.get('obj_token', '')[:30]}...")
                        continue
                    
                    # 提取最相关的文档片段
                    relevant_chunk = self._extract_relevant_chunk(doc_content, question, keywords)
                    
                    # 验证提取的片段是否有效
                    if not relevant_chunk or not relevant_chunk.strip():
                        log.warning(f"文档 {title} 提取的相关片段为空，使用原始内容计算相似度")
                        relevant_chunk = doc_content[:1000] if doc_content else ""  # 使用前1000字符作为回退
                    
                    if not relevant_chunk or not relevant_chunk.strip():
                        log.warning(f"文档 {title} 内容为空，跳过相似度计算")
                        similarity = 0.0
                    else:
                        # 计算相似度（使用embedding）- 使用提取的相关片段计算，而不是原始内容
                        # 注意：这里使用relevant_chunk而不是doc_content，因为relevant_chunk是提取的最相关部分
                        similarity = self._calculate_similarity(question, relevant_chunk)
                        log.debug(f"文档 {title} 相似度: {similarity:.3f} (片段长度: {len(relevant_chunk)})")
                    
                    doc_results.append({
                        "title": title,
                        "url": url,
                        "content": relevant_chunk,
                        "full_content": doc_content,
                        "similarity": similarity,
                        "obj_token": result["obj_token"],
                        "has_content": True,  # 标记为有完整内容
                    })
                except Exception as e:
                    log.warning(f"❌ 处理文档 {result.get('title', '未知')} 失败: {e}")
                    # 即使处理失败，也尝试保留标题和URL
                    title = result.get("title", "未知标题")
                    url = result.get("url", "")
                    if title and title != "未知标题":
                        log.info(f"⚠️ 文档 {title} 处理失败，但保留标题和URL")
                        doc_results.append({
                            "title": title,
                            "url": url,
                            "content": f"文档标题：{title}",
                            "full_content": "",
                            "similarity": 0.3,
                            "obj_token": result.get("obj_token", ""),
                            "has_content": False,
                        })
                    else:
                        log.warning(f"⚠️ 文档处理失败且标题为空，完全跳过: obj_token={result.get('obj_token', '')[:30]}...")
                    continue
            
            log.info(f"📊 内容加载完成：共处理 {len(doc_results)} 个文档结果")
            
            # 按相似度排序（优先有完整内容的文档）
            doc_results.sort(key=lambda x: (x.get("has_content", False), x["similarity"]), reverse=True)
            
            # 分离有内容和无内容的文档
            results_with_content = [r for r in doc_results if r.get("has_content", True)]
            results_without_content = [r for r in doc_results if not r.get("has_content", True)]
            
            # 根据问题类型设置不同的相似度阈值
            if question_type == "document_list":
                # 文档列表查询：使用更低的阈值，返回更多文档
                MIN_SIMILARITY_THRESHOLD = 0.2
                MAX_RESULTS = 30  # 返回更多文档
                log.info(f"📋 文档列表查询模式：阈值={MIN_SIMILARITY_THRESHOLD}, 最大结果数={MAX_RESULTS}")
            else:
                # 内容问答：使用较高的阈值，确保相关性
                MIN_SIMILARITY_THRESHOLD = 0.5
                MAX_RESULTS = 5  # 只返回最相关的几个文档
                log.info(f"💬 内容问答模式：阈值={MIN_SIMILARITY_THRESHOLD}, 最大结果数={MAX_RESULTS}")
            
            filtered_results = [r for r in results_with_content if r["similarity"] >= MIN_SIMILARITY_THRESHOLD]
            
            # 记录相似度信息用于调试
            if results_with_content:
                max_sim = max([r["similarity"] for r in results_with_content])
                avg_sim = sum([r["similarity"] for r in results_with_content]) / len(results_with_content)
                log.info(f"📊 文档相似度统计: 最高={max_sim:.3f}, 平均={avg_sim:.3f}, 阈值={MIN_SIMILARITY_THRESHOLD}")
                log.info(f"✅ 达到阈值（>={MIN_SIMILARITY_THRESHOLD}）的文档数: {len(filtered_results)}/{len(results_with_content)}")
                
                # 打印前10个文档的相似度
                log.info(f"📋 文档相似度列表（前10个）:")
                for i, doc in enumerate(results_with_content[:10], 1):
                    sim = doc.get("similarity", 0.0)
                    status = "✅" if sim >= MIN_SIMILARITY_THRESHOLD else "❌"
                    log.info(f"   {status} {i}. {doc.get('title', '未知')}: {sim:.3f}")
            
            # 保存相似度计算结果
            max_sim = max([r["similarity"] for r in results_with_content]) if results_with_content else 0.0
            avg_sim = sum([r["similarity"] for r in results_with_content]) / len(results_with_content) if results_with_content else 0.0
            self._save_query_result(question, "similarity_calculation", {
                "total_docs": len(doc_results),
                "with_content": len(results_with_content),
                "without_content": len(results_without_content),
                "filtered_count": len(filtered_results),
                "threshold": MIN_SIMILARITY_THRESHOLD,
                "max_similarity": max_sim,
                "avg_similarity": avg_sim,
                "documents": [
                    {
                        "title": r.get("title", "未知"),
                        "similarity": r.get("similarity", 0.0),
                        "has_content": r.get("has_content", False),
                        "url": r.get("url", "")
                    }
                    for r in results_with_content[:15]  # 保存前15个
                ]
            }, query_timestamp)
            
            # 如果是文档列表查询，即使没有达到阈值也返回文档列表
            if question_type == "document_list":
                # 文档列表查询：合并有内容和无内容的文档
                # 对于无内容的文档，给予默认相似度0.3（因为至少标题匹配）
                all_documents = []
                
                # 添加有内容的文档（按相似度排序）
                for doc in sorted(results_with_content, key=lambda x: x["similarity"], reverse=True):
                    all_documents.append(doc)
                
                # 添加无内容的文档（至少显示标题和URL）
                for doc in results_without_content:
                    # 确保无内容文档有相似度值（如果没有则使用默认值0.3）
                    if "similarity" not in doc or doc.get("similarity", 0) == 0:
                        doc["similarity"] = 0.3
                    all_documents.append(doc)
                
                # 限制返回数量
                document_list_results = all_documents[:MAX_RESULTS]
                
                log.info(f"📋 文档列表查询：找到 {len(document_list_results)} 个文档（有内容: {len(results_with_content)}, 无内容: {len(results_without_content)}）")
                
                if document_list_results:
                    # 格式化文档列表
                    answer_text = self._format_document_list(document_list_results, question, subtype)
                    
                    return {
                        "success": True,
                        "answer": answer_text,
                        "sources": [{"title": r["title"], "url": r["url"], "similarity": r.get("similarity", 0.3)} 
                                   for r in document_list_results],
                        "question_type": "document_list",
                        "max_similarity": max([r.get("similarity", 0.3) for r in document_list_results]) if document_list_results else 0.0,
                    }
                else:
                    # 没有找到文档
                    return {
                        "success": False,
                        "answer": "未找到相关文档。\n\n建议：\n1. 尝试使用不同的关键词重新搜索\n2. 或者检查知识库中是否有相关文档",
                        "sources": [],
                        "question_type": "document_list",
                        "max_similarity": 0.0,
                    }
            
            # 🔴 内容问答模式：如果没有达到阈值的文档，明确拒绝，不再强制返回
            if not filtered_results:
                log.warning(f"未找到相似度>={MIN_SIMILARITY_THRESHOLD}的相关文档")
                if results_with_content:
                    # 记录最高相似度，帮助用户理解为什么拒绝
                    max_sim = max([r["similarity"] for r in results_with_content])
                    top_titles = [r["title"] for r in sorted(results_with_content, key=lambda x: x["similarity"], reverse=True)[:3]]
            
                    # 判断是否建议使用网络搜索
                    suggest_web = self._should_use_web_search(question, {
                        "success": False,
                        "sources": [{"similarity": max_sim}]
                    })
                    
                    answer_text = (
                        f"抱歉，未找到与您的问题高度相关的文档。\n\n"
                        f"找到的文档最高相似度为 {max_sim:.3f}，低于阈值 {MIN_SIMILARITY_THRESHOLD}。\n\n"
                        f"找到的相关文档：\n" + "\n".join([f"- {title}" for title in top_titles]) + "\n\n"
                    )
                    
                    if suggest_web:
                        answer_text += (
                            f"💡 建议：\n"
                            f"1. 可以尝试使用网络搜索获取更多信息\n"
                            f"2. 或者尝试使用不同的关键词重新提问\n"
                            f"3. 或者检查知识库中是否有相关文档"
                        )
                    else:
                        answer_text += (
                            f"建议：\n"
                            f"1. 尝试使用不同的关键词重新提问\n"
                            f"2. 或者检查知识库中是否有相关文档"
                        )
                    
                    return {
                        "success": False,
                        "answer": answer_text,
                        "sources": [{"title": r["title"], "url": r["url"], "similarity": r["similarity"]} 
                                   for r in sorted(results_with_content, key=lambda x: x["similarity"], reverse=True)[:3]],
                        "suggest_web_search": suggest_web,
                        "max_similarity": max_sim,
                        "question_type": "content_qa",
                    }
                else:
                    # 如果没有有内容的文档，也不使用无内容的文档（避免误导）
                    # 判断是否建议使用网络搜索
                    suggest_web = self._should_use_web_search(question, {
                        "success": False,
                        "sources": []
                    })
                    
                    answer_text = (
                        "抱歉，未找到与您的问题相关的文档。\n\n"
                    )
                    
                    if suggest_web:
                        answer_text += (
                            "💡 建议：\n"
                            "1. 可以尝试使用网络搜索获取更多信息\n"
                            "2. 或者尝试使用不同的关键词重新提问\n"
                            "3. 或者检查知识库中是否有相关文档"
                        )
                    else:
                        answer_text += (
                            "建议：\n"
                            "1. 尝试使用不同的关键词重新提问\n"
                            "2. 或者检查知识库中是否有相关文档"
                        )
                    
                    return {
                        "success": False,
                        "answer": answer_text,
                        "sources": [],
                        "suggest_web_search": suggest_web,
                        "max_similarity": 0.0,
                    }
            
            # 如果没有有内容的文档，也不使用无内容的文档（避免误导）
            # 移除原来的逻辑：if not filtered_results and results_without_content
            
            # 根据问题类型取不同数量的结果
            top_results = filtered_results[:MAX_RESULTS]
            
            # 统计有内容和无内容的文档数量
            content_count = sum(1 for r in top_results if r.get("has_content", True))
            title_only_count = len(top_results) - content_count
            if title_only_count > 0:
                log.warning(f"找到 {len(top_results)} 个相关文档，其中 {title_only_count} 个无法获取完整内容（可能权限不足）")
            
            # 构建上下文（使用相关片段）
            context_parts = []
            sources = []
            has_content_results = []
            title_only_results = []
            
            for result in top_results:
                # 使用有完整内容的文档构建上下文
                if result.get("has_content", True):
                    # 优先使用full_content（完整内容），增加长度限制到8000字符
                    # 如果完整内容太长（超过8000字符），使用提取的相关片段
                    full_content = result.get("full_content", "")
                    extracted_chunk = result.get("content", "")
                    
                    if full_content and len(full_content) <= 8000:
                        # 使用完整内容（如果长度合理）
                        content_to_use = full_content
                    elif full_content and len(full_content) > 8000:
                        # 如果完整内容太长，使用提取的相关片段，但尽量保留更多上下文
                        # 尝试从完整内容中提取包含相关片段的部分（前后各保留1000字符）
                        if extracted_chunk:
                            # 找到提取片段在完整内容中的位置
                            chunk_start = full_content.find(extracted_chunk[:100])
                            if chunk_start >= 0:
                                # 提取片段前后各1000字符
                                context_start = max(0, chunk_start - 1000)
                                context_end = min(len(full_content), chunk_start + len(extracted_chunk) + 1000)
                                content_to_use = full_content[context_start:context_end]
                            else:
                                content_to_use = extracted_chunk
                        else:
                            content_to_use = full_content[:8000] + "..."
                    else:
                        # 没有完整内容，使用提取的片段
                        content_to_use = extracted_chunk
                    
                    # 结构化组织：保留文档标题，清晰分隔
                    context_parts.append(f"【文档：{result['title']}】\n\n{content_to_use}\n")
                    has_content_results.append(result)
                else:
                    # 即使没有完整内容，也记录标题信息
                    title_only_results.append(result)
                
                # 所有结果都添加到sources（包括只有标题的）
                sources.append({
                    "title": result["title"],
                    "url": result["url"],
                    "similarity": result["similarity"],
                })
            
            context = "\n\n".join(context_parts)
            
            # 如果是文档列表查询模式，且找到了文档，直接返回文档列表
            if question_type == "document_list" and top_results:
                log.info(f"📋 文档列表查询模式：返回 {len(top_results)} 个文档")
                answer_text = self._format_document_list(top_results, question, subtype)
                return {
                    "success": True,
                    "answer": answer_text,
                    "sources": [{"title": r["title"], "url": r["url"], "similarity": r["similarity"]} 
                               for r in top_results],
                    "question_type": "document_list",
                    "max_similarity": max([r["similarity"] for r in top_results]) if top_results else 0.0,
                }
            
            # 检查是否有文档内容
            has_document_content = len(has_content_results) > 0
            
            # 即使没有完整内容，也尝试使用标题信息生成答案
            if not has_document_content:
                log.warning("无法获取文档完整内容，尝试基于文档标题生成答案")
                
                # 构建基于标题的上下文
                title_context_parts = []
                for result in top_results[:5]:  # 使用前5个结果
                    title = result.get("title", "未知标题")
                    url = result.get("url", "")
                    similarity = result.get("similarity", 0)
                    search_query = result.get("search_query", "")
                    
                    # 构建标题上下文（包含标题、相似度和匹配的搜索词）
                    title_info = f"【文档：{title}】"
                    if search_query:
                        title_info += f"\n匹配的搜索词：{search_query}"
                    if similarity > 0:
                        title_info += f"\n相关性：{similarity:.2f}"
                    if url:
                        title_info += f"\n链接：{url}"
                    
                    title_context_parts.append(title_info)
                
                title_context = "\n\n".join(title_context_parts)
                
                # 使用LLM基于标题信息生成答案
                try:
                    llm_service = LLMService()
                    prompt = f"""你是一位专业的AI助手。用户提出了一个问题，但受限于权限，我只能获取到相关文档的标题信息，无法获取完整内容。

【用户问题】
{question}

【提取的关键词】
{', '.join(keywords) if keywords else '无'}

【相关概念】
{', '.join(related_concepts) if related_concepts else '无'}

【找到的相关文档（仅标题）】
{title_context}

【要求】
1. 基于文档标题，尝试推断这些文档可能包含哪些与问题相关的信息
2. 如果标题明显与问题相关，可以基于标题进行合理推断并给出答案
3. 如果标题信息不足以回答问题，请说明"根据文档标题，找到了以下相关文档，但由于权限限制无法获取完整内容"
4. 列出找到的相关文档标题，并建议用户点击链接查看完整内容
5. 使用简体中文，语言简洁明了

【答案】
请基于以上文档标题信息，回答用户问题：
"""
                    answer = llm_service.generate(prompt)
                except Exception as e:
                    log.warning(f"基于标题生成答案失败: {e}，使用默认提示")
                    # 回退到简单的提示
                    title_list = [r["title"] for r in top_results if r.get("title")]
                    answer = (
                        f"根据搜索，找到了以下相关文档：\n\n"
                        + "\n".join([f"{i+1}. {title}" for i, title in enumerate(title_list)])
                        + "\n\n"
                        + "⚠️ 注意：由于权限限制，无法获取文档的完整内容。\n"
                        + "建议：\n"
                        + "1. 点击上方文档链接查看完整内容\n"
                        + "2. 或者先同步文档到本地向量库以获得更好的搜索效果"
                    )
            else:
                # 【AI分析搜索结果】先让AI分析搜索结果的相关性和关键信息
                analysis_result = self._analyze_search_results_with_ai(question, has_content_results, keywords, related_concepts)
                
                # 【AI生成答案】使用LLM基于搜索结果和AI分析生成答案
                llm_service = LLMService()
                prompt = self._build_answer_prompt(question, context, has_content_results, analysis_result, keywords)
                
                answer = llm_service.generate(prompt)
            
                # 🔴 新增：验证答案相关性
                answer_relevance = self._verify_answer_relevance(question, answer, has_content_results)
                if not answer_relevance.get("is_relevant", True):
                    log.warning(f"答案相关性验证失败: {answer_relevance.get('reason', '未知原因')}")
                    # 如果答案不相关，返回提示信息
                    return {
                        "success": False,
                        "answer": (
                            f"抱歉，根据提供的文档，无法生成与您的问题高度相关的答案。\n\n"
                            f"找到的相关文档：\n" + "\n".join([f"- {s['title']}" for s in sources[:3]]) + "\n\n"
                            f"建议：\n"
                            f"1. 尝试使用不同的关键词重新提问\n"
                            f"2. 或者检查知识库中是否有更相关的文档"
                        ),
                        "sources": sources,
                        "question_type": "content_qa",
                    }
            
            # 计算最高相似度，判断是否需要建议网络搜索
            sources_with_similarity = [s for s in sources if s.get("similarity", 0) > 0]
            max_similarity = max([s.get("similarity", 0) for s in sources_with_similarity]) if sources_with_similarity else 0.0
            
            # 判断是否建议使用网络搜索（即使有答案，如果相似度较低，也建议网络搜索）
            suggest_web = False
            if max_similarity > 0 and max_similarity < 0.6:
                # 如果相似度在0.5-0.6之间，判断是否是通用概念问题
                if self._is_general_concept_question(question):
                    suggest_web = True
            
            result = {
                "success": True,
                "answer": answer.strip(),
                "sources": sources,
                "suggest_web_search": suggest_web,
                "max_similarity": max_similarity,
                "question_type": question_type,
            }
            
            # 保存最终结果并打印
            log.info("="*80)
            log.info(f"✅ 问题处理完成")
            log.info(f"   问题: {question}")
            log.info(f"   答案长度: {len(answer.strip())} 字符")
            log.info(f"   引用文档数: {len(sources)}")
            log.info(f"   最高相似度: {max_similarity:.3f}")
            if suggest_web:
                log.info(f"   💡 建议使用网络搜索补充信息")
            log.info("="*80)
            
            self._save_query_result(question, "final_result", {
                "success": True,
                "answer_length": len(answer.strip()),
                "sources_count": len(sources),
                "max_similarity": max_similarity,
                "suggest_web_search": suggest_web,
                "sources": sources[:10]  # 只保存前10个来源
            }, query_timestamp)
            
            return result
            
        except Exception as e:
            log.error(f"实时搜索模式失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "answer": f"实时搜索失败: {str(e)}",
                "sources": [],
            }
    
    def _detect_question_type(self, question: str) -> Dict[str, Any]:
        """
        检测问题类型：文档列表查询 vs 内容问答
        
        Args:
            question: 用户问题
            
        Returns:
            {
                "type": "document_list" | "content_qa" | "mixed",
                "confidence": 0.0-1.0,
                "keywords": ["关键词列表"]
            }
        """
        question_lower = question.lower()
        
        # 文档列表查询的关键词模式
        list_patterns = [
            "有哪些", "哪些文档", "相关文档", "文档列表", "列出", 
            "找到", "搜索", "查找", "文档", "哪些文档",
            "什么文档", "有什么文档", "包含哪些", "涉及哪些",
            "what documents", "list", "find documents", "search documents",
            "相关", "关于.*的文档", ".*文档.*有哪些"
        ]
        
        # 统计查询的关键词
        stats_patterns = [
            "有多少", "数量", "统计", "总数", "几个", "多少文档",
            "how many", "count", "number of"
        ]
        
        # 对比查询的关键词
        comparison_patterns = [
            "对比", "区别", "差异", "比较", "vs", "versus", "和.*的区别",
            "compare", "difference", "vs"
        ]
        
        # 检查文档列表查询
        list_score = 0.0
        for pattern in list_patterns:
            if pattern in question_lower:
                list_score += 0.3
                if pattern in ["有哪些", "哪些文档", "文档列表", "list"]:
                    list_score += 0.4  # 更强的信号
        
        # 检查统计查询
        stats_score = 0.0
        for pattern in stats_patterns:
            if pattern in question_lower:
                stats_score += 0.5
        
        # 检查对比查询
        comparison_score = 0.0
        for pattern in comparison_patterns:
            if pattern in question_lower:
                comparison_score += 0.5
        
        # 提取关键词（用于后续搜索）
        keywords = self._extract_keywords(question)
        
        # 判断问题类型
        if list_score >= 0.5:
            return {
                "type": "document_list",
                "confidence": min(list_score, 1.0),
                "keywords": keywords,
                "subtype": "stats" if stats_score > 0.3 else "list"
            }
        elif stats_score >= 0.3:
            return {
                "type": "document_list",  # 统计查询也归类为文档列表
                "confidence": min(stats_score, 1.0),
                "keywords": keywords,
                "subtype": "stats"
            }
        elif comparison_score >= 0.3:
            return {
                "type": "content_qa",  # 对比查询需要内容分析
                "confidence": min(comparison_score, 1.0),
                "keywords": keywords,
                "subtype": "comparison"
            }
        else:
            # 默认是内容问答
            return {
                "type": "content_qa",
                "confidence": 0.5,
                "keywords": keywords,
                "subtype": "normal"
            }
    
    def _analyze_question_with_ai(self, question: str) -> Dict[str, Any]:
        """
        使用AI分析问题并提取搜索关键词和策略。
        
        Args:
            question: 用户问题
            
        Returns:
            包含关键词、搜索查询和相关概念的字典
        """
        try:
            from infrastructure.llm.service import LLMService
            import json
            import re
            
            llm_service = LLMService()
            
            prompt = f"""分析以下问题，提取用于搜索知识库的关键词和查询策略。

用户问题：{question}

请分析：
1. 问题的核心主题是什么？
2. 需要搜索哪些关键词？（提取2-5个最重要的关键词）
3. 有哪些同义词或相关概念？
4. 可以尝试哪些不同的搜索查询？（生成3-5个不同的搜索查询，包括原问题的不同表达方式）

请以JSON格式返回，格式如下：
{{
    "keywords": ["关键词1", "关键词2"],
    "search_queries": ["搜索查询1", "搜索查询2", "搜索查询3"],
    "related_concepts": ["相关概念1", "相关概念2"]
}}

要求：
- keywords：提取的核心关键词，去除疑问词（什么、如何、怎么等）
- search_queries：多个搜索查询，包括原问题的不同表达方式、简化版本、关键词组合等
- related_concepts：相关概念或同义词

只返回JSON，不要其他文字。
"""
            
            log.info("使用AI分析问题并提取搜索策略...")
            response = llm_service.generate(prompt)
            
            # 尝试从响应中提取JSON
            json_match = re.search(r'\{[^{}]*"keywords"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 如果没有找到JSON，尝试解析整个响应
                json_str = response.strip()
                # 移除可能的markdown代码块标记
                json_str = re.sub(r'```json\s*', '', json_str)
                json_str = re.sub(r'```\s*', '', json_str)
                json_str = json_str.strip()
            
            try:
                result = json.loads(json_str)
                
                # 验证和清理结果
                keywords = result.get("keywords", [])
                search_queries = result.get("search_queries", [])
                related_concepts = result.get("related_concepts", [])
                
                # 确保至少有一个搜索查询
                if not search_queries:
                    search_queries = [question]
                else:
                    # 确保原问题在搜索查询中
                    if question not in search_queries:
                        search_queries.insert(0, question)
                
                # 限制数量
                keywords = keywords[:5]
                search_queries = search_queries[:5]
                related_concepts = related_concepts[:3]
                
                return {
                    "keywords": keywords,
                    "search_queries": search_queries,
                    "related_concepts": related_concepts,
                }
            except json.JSONDecodeError as e:
                log.warning(f"AI返回的JSON解析失败: {e}，响应: {response[:200]}")
                # 回退到正则表达式提取关键词
                return self._fallback_extract_keywords(question)
                
        except Exception as e:
            log.warning(f"AI分析问题失败: {e}，回退到正则表达式提取")
            # 回退到正则表达式提取关键词
            return self._fallback_extract_keywords(question)
    
    def _fallback_extract_keywords(self, question: str) -> Dict[str, Any]:
        """
        回退方案：使用正则表达式提取关键词。
        
        Args:
            question: 用户问题
            
        Returns:
            包含关键词和搜索查询的字典
        """
        keywords = self._extract_keywords(question)
        search_queries = [question] + keywords[:2]
        
        return {
            "keywords": keywords,
            "search_queries": search_queries,
            "related_concepts": [],
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从问题中提取关键词。
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        import re
        
        # 移除标点符号，保留空格
        text_clean = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        
        keywords = []
        
        # 提取中文词汇（2-4个字符，避免提取整个问题）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text_clean)
        keywords.extend(chinese_words)
        
        # 提取英文单词（3个字符以上）
        english_words = re.findall(r'\b[a-zA-Z]{3,}\b', text_clean)
        keywords.extend(english_words)
        
        # 过滤常见停用词和疑问词
        stop_words = {
            '什么', '如何', '怎么', '为什么', '哪个', '哪些', '这个', '那个', 
            '是', '的', '了', '在', '有', '和', '与', '或', '为',
            '是什么', '如何', '怎么', '为什么', '哪个', '哪些',
            'the', 'is', 'are', 'a', 'an', 'and', 'or', 'what', 'how', 'why'
        }
        keywords = [kw for kw in keywords if kw not in stop_words and len(kw) >= 2]
        
        # 进一步过滤：如果关键词包含停用词，尝试提取核心部分
        filtered_keywords = []
        for kw in keywords:
            # 移除常见的疑问词前缀/后缀
            kw_clean = kw
            for stop in ['什么', '如何', '怎么', '为什么', '是', '的']:
                if kw_clean.startswith(stop):
                    kw_clean = kw_clean[len(stop):]
                if kw_clean.endswith(stop):
                    kw_clean = kw_clean[:-len(stop)]
            if kw_clean and len(kw_clean) >= 2 and kw_clean not in stop_words:
                filtered_keywords.append(kw_clean)
        
        keywords = filtered_keywords if filtered_keywords else keywords
        
        # 去重（保持顺序）
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)
        
        # 如果提取的关键词太少，尝试提取2-3字的短语
        if len(unique_keywords) < 2:
            # 提取2-3字的中文短语
            phrases = re.findall(r'[\u4e00-\u9fff]{2,3}', text)
            for phrase in phrases:
                if phrase not in stop_words and phrase not in seen:
                    seen.add(phrase.lower())
                    unique_keywords.append(phrase)
                    if len(unique_keywords) >= 3:
                        break
        
        return unique_keywords[:5]  # 最多返回5个关键词
    
    def _format_document_list(self, documents: List[Dict[str, Any]], question: str, subtype: str = "list") -> str:
        """
        格式化文档列表为答案文本。
        
        Args:
            documents: 文档列表
            question: 用户问题
            subtype: 问题子类型（list/stats）
            
        Returns:
            格式化后的答案文本
        """
        if not documents:
            return "未找到相关文档。"
        
        # 统计查询
        if subtype == "stats":
            answer = f"找到 {len(documents)} 个相关文档：\n\n"
        else:
            answer = f"找到以下 {len(documents)} 个相关文档：\n\n"
        
        # 按相似度分组（高/中/低）
        high_relevance = [d for d in documents if d.get("similarity", 0) >= 0.5]
        medium_relevance = [d for d in documents if 0.3 <= d.get("similarity", 0) < 0.5]
        low_relevance = [d for d in documents if d.get("similarity", 0) < 0.3]
        
        # 格式化文档列表
        doc_index = 1
        if high_relevance:
            answer += "**高相关性文档：**\n"
            for doc in high_relevance:
                similarity = doc.get("similarity", 0)
                similarity_str = f"（相关性: {similarity:.1%}）" if similarity > 0 else ""
                answer += f"{doc_index}. {doc['title']}{similarity_str}\n"
                doc_index += 1
            answer += "\n"
        
        if medium_relevance:
            answer += "**中等相关性文档：**\n"
            for doc in medium_relevance:
                similarity = doc.get("similarity", 0)
                similarity_str = f"（相关性: {similarity:.1%}）" if similarity > 0 else ""
                answer += f"{doc_index}. {doc['title']}{similarity_str}\n"
                doc_index += 1
            answer += "\n"
        
        if low_relevance:
            answer += "**其他相关文档：**\n"
            for doc in low_relevance:
                similarity = doc.get("similarity", 0)
                similarity_str = f"（相关性: {similarity:.1%}）" if similarity > 0 else ""
                answer += f"{doc_index}. {doc['title']}{similarity_str}\n"
                doc_index += 1
        
        # 添加提示
        answer += "\n💡 提示：点击文档标题可以查看完整内容。"
        
        return answer
    
    def _extract_relevant_chunk(self, content: str, question: str, keywords: List[str], chunk_size: int = 4000) -> str:
        """
        从文档中提取与问题最相关的片段。
        
        Args:
            content: 文档内容
            question: 用户问题
            keywords: 关键词列表
            chunk_size: 片段大小（增加到2000以提供更多上下文）
            
        Returns:
            相关片段
        """
        import re
        
        if not content:
            return ""
        
        # 如果文档较短，直接返回
        if len(content) <= chunk_size:
            return content
        
        # 按段落分割
        paragraphs = re.split(r'\n+', content)
        
        # 计算每个段落的相关性分数
        scored_paragraphs = []
        for para in paragraphs:
            if not para.strip():
                continue
            
            score = 0
            para_lower = para.lower()
            question_lower = question.lower()
            
            # 检查是否包含问题中的关键词
            for keyword in keywords:
                if keyword.lower() in para_lower:
                    score += 2
            
            # 检查是否包含问题中的完整短语
            if question_lower in para_lower:
                score += 5
            
            # 检查是否包含问题中的部分词汇
            question_words = question_lower.split()
            for word in question_words:
                if len(word) >= 2 and word in para_lower:
                    score += 1
            
            if score > 0:
                scored_paragraphs.append((score, para))
        
        # 按分数排序
        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
        
        # 选择最相关的段落组合（增加到最多15个段落，提供更多上下文）
        # 使用embedding计算段落相似度，而不是简单的关键词匹配
        selected_text = ""
        selected_count = 0
        max_paragraphs = 15  # 增加段落数量
        
        # 如果段落数量较多，尝试使用embedding计算相似度（更准确）
        if len(scored_paragraphs) > 5:
            try:
                from infrastructure.embedding.service import EmbeddingService
                import numpy as np
                
                embedding_service = EmbeddingService()
                question_vector = np.array(embedding_service.embed_text(question))
                
                # 重新计算每个段落的相似度分数（结合关键词匹配和语义相似度）
                enhanced_scored_paragraphs = []
                for score, para in scored_paragraphs[:20]:  # 只处理前20个段落以提高性能
                    # 计算语义相似度
                    para_vector = np.array(embedding_service.embed_text(para[:500]))
                    semantic_score = np.dot(question_vector, para_vector) / (
                        np.linalg.norm(question_vector) * np.linalg.norm(para_vector) + 1e-8
                    )
                    # 结合关键词匹配分数和语义相似度分数
                    combined_score = score * 0.4 + semantic_score * 100 * 0.6
                    enhanced_scored_paragraphs.append((combined_score, para))
                
                # 重新排序
                enhanced_scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
                scored_paragraphs = enhanced_scored_paragraphs
            except Exception as e:
                log.debug(f"使用embedding计算相似度失败，回退到关键词匹配: {e}")
                # 如果失败，继续使用原来的关键词匹配结果
        
        # 选择段落时，保留上下文窗口（每个相关段落前后各保留一个段落）
        selected_indices = set()
        
        # 构建段落到索引的映射（用于快速查找）
        para_to_index = {}
        for idx, orig_para in enumerate(paragraphs):
            if orig_para.strip():
                para_key = orig_para.strip()[:100]  # 使用前100字符作为key
                if para_key not in para_to_index:
                    para_to_index[para_key] = []
                para_to_index[para_key].append(idx)
        
        # 选择最相关的段落及其上下文
        for score, para in scored_paragraphs[:max_paragraphs]:
            # 找到这个段落在原文中的索引
            para_key = para.strip()[:100]
            para_indices = para_to_index.get(para_key, [])
            
            if para_indices:
                # 使用第一个匹配的索引
                para_index = para_indices[0]
                # 选择当前段落及其前后各一个段落（上下文窗口）
                for ctx_idx in range(max(0, para_index - 1), min(len(paragraphs), para_index + 2)):
                    selected_indices.add(ctx_idx)
            else:
                # 如果找不到精确匹配，尝试模糊匹配
                para_stripped = para.strip()
                for idx, orig_para in enumerate(paragraphs):
                    if orig_para.strip() and para_stripped[:50] in orig_para.strip():
                        para_index = idx
                        # 选择当前段落及其前后各一个段落
                        for ctx_idx in range(max(0, para_index - 1), min(len(paragraphs), para_index + 2)):
                            selected_indices.add(ctx_idx)
                        break
        
        # 按顺序提取选中的段落
        for idx in sorted(selected_indices):
            para = paragraphs[idx]
            if not para.strip():
                continue
            
            if len(selected_text) + len(para) <= chunk_size:
                selected_text += para + "\n\n"
            else:
                # 如果超过长度限制，尝试截取部分
                remaining = chunk_size - len(selected_text)
                if remaining > 200:  # 至少保留200字符
                    selected_text += para[:remaining] + "..."
                break
        
        # 如果没有找到相关段落，返回开头部分（增加长度）
        if not selected_text:
            # 返回更多内容，包括文档开头
            selected_text = content[:chunk_size] + "..."
        
        return selected_text.strip()
    
    def _calculate_similarity(self, question: str, content: str) -> float:
        """
        计算问题和文档内容的相似度（使用embedding）。
        
        Args:
            question: 用户问题
            content: 文档内容
            
        Returns:
            相似度分数（0-1）
        """
        try:
            from infrastructure.embedding.service import EmbeddingService
            import numpy as np
            
            # 初始化embedding服务
            embedding_service = EmbeddingService()
            
            # 向量化问题和内容
            # 注意：content应该是已经提取的相关片段，不需要再截取前500字符
            # 如果content太长（超过2000字符），截取前2000字符以提高性能
            content_to_embed = content[:2000] if len(content) > 2000 else content
            
            # 确保内容不为空
            if not content_to_embed or not content_to_embed.strip():
                log.warning(f"内容为空，返回相似度0.0")
                return 0.0
            
            # 记录embedding服务信息
            model_name = embedding_service.get_model_name()
            log.debug(f"使用embedding模型: {model_name}")
            
            # 向量化问题
            question_vector_raw = embedding_service.embed_text(question)
            question_vector = np.array(question_vector_raw)
            
            # 向量化内容
            content_vector_raw = embedding_service.embed_text(content_to_embed)
            content_vector = np.array(content_vector_raw)
            
            # 验证向量是否有效
            if question_vector.size == 0 or content_vector.size == 0:
                log.warning(f"向量为空，返回相似度0.0 (question_size={question_vector.size}, content_size={content_vector.size})")
                return 0.0
            
            # 检查向量维度是否匹配
            if question_vector.shape != content_vector.shape:
                log.error(f"向量维度不匹配: question={question_vector.shape}, content={content_vector.shape}")
                return 0.0
            
            # 检查向量是否全为零
            if np.all(question_vector == 0) or np.all(content_vector == 0):
                log.warning(f"检测到零向量: question_all_zero={np.all(question_vector == 0)}, content_all_zero={np.all(content_vector == 0)}")
                log.warning(f"问题向量前5个值: {question_vector[:5]}")
                log.warning(f"内容向量前5个值: {content_vector[:5]}")
                # 如果向量全为零，使用关键词匹配作为回退
                keywords = self._extract_keywords(question)
                content_lower = content.lower() if content else ""
                match_count = sum(1 for kw in keywords if kw.lower() in content_lower)
                estimated_similarity = min(0.4, 0.1 + match_count * 0.05)
                log.info(f"检测到零向量，使用关键词匹配估计相似度: {estimated_similarity:.3f} (匹配关键词数: {match_count})")
                return estimated_similarity
            
            # 计算余弦相似度
            dot_product = np.dot(question_vector, content_vector)
            norm_q = np.linalg.norm(question_vector)
            norm_c = np.linalg.norm(content_vector)
            
            if norm_q == 0 or norm_c == 0:
                log.warning(f"向量模长为0，返回相似度0.0 (norm_q={norm_q}, norm_c={norm_c})")
                return 0.0
            
            similarity = dot_product / (norm_q * norm_c)
            
            # 🔴 修复：处理负数相似度
            # 余弦相似度范围是-1到1，负数表示向量方向相反或接近垂直
            # 负数相似度应该被视为低相关性，但不应该被直接截断为0.0
            if similarity < 0:
                # 负数相似度表示不相关，设为0.0
                # 但记录日志以便排查问题
                log.debug(f"检测到负数相似度: {similarity:.3f} (问题: {question[:50]}..., 内容长度: {len(content_to_embed)})")
                log.debug(f"点积: {dot_product:.3f}, norm_q: {norm_q:.3f}, norm_c: {norm_c:.3f}")
                similarity = 0.0
            else:
            # 确保相似度在0-1范围内
                similarity = min(1.0, float(similarity))
            
            # 添加调试日志（仅在相似度异常时）
            if similarity < 0.1:
                log.debug(f"相似度较低: {similarity:.3f} (问题: {question[:50]}..., 内容长度: {len(content_to_embed)}, 向量维度: {question_vector.shape[0]})")
                log.debug(f"问题向量统计: min={question_vector.min():.3f}, max={question_vector.max():.3f}, mean={question_vector.mean():.3f}")
                log.debug(f"内容向量统计: min={content_vector.min():.3f}, max={content_vector.max():.3f}, mean={content_vector.mean():.3f}")
            
            return similarity
            
        except Exception as e:
            log.error(f"计算相似度失败: {e}，使用关键词匹配估计值")
            import traceback
            log.debug(traceback.format_exc())
            # 如果计算失败，基于关键词匹配返回一个估计值（但标记为低相似度）
            keywords = self._extract_keywords(question)
            content_lower = content.lower() if content else ""
            match_count = sum(1 for kw in keywords if kw.lower() in content_lower)
            # 降低默认值，避免误判为相关
            estimated_similarity = min(0.4, 0.1 + match_count * 0.05)  # 基础分数0.1，每个关键词匹配+0.05，最高0.4
            log.info(f"使用关键词匹配估计相似度: {estimated_similarity:.3f} (匹配关键词数: {match_count})")
            return estimated_similarity
    
    def _analyze_search_results_with_ai(
        self, 
        question: str, 
        search_results: List[Dict[str, Any]], 
        keywords: List[str],
        related_concepts: List[str]
    ) -> Dict[str, Any]:
        """
        使用AI分析搜索结果的相关性和关键信息。
        
        Args:
            question: 用户问题
            search_results: 搜索结果列表
            keywords: 提取的关键词
            related_concepts: 相关概念
            
        Returns:
            分析结果，包含：
            - relevance_summary: 相关性总结
            - key_points: 关键信息点
            - answer_strategy: 答案生成策略
        """
        try:
            from infrastructure.llm.service import LLMService
            import json
            import re
            
            llm_service = LLMService()
            
            # 构建搜索结果摘要（只包含标题和相似度，避免token过多）
            results_summary = []
            for i, result in enumerate(search_results[:5], 1):
                results_summary.append({
                    "序号": i,
                    "标题": result.get("title", "未知"),
                    "相似度": f"{result.get('similarity', 0):.2f}",
                    "内容摘要": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", "")
                })
            
            prompt = f"""你是一位专业的AI助手，需要分析搜索结果与用户问题的相关性。

【用户问题】
{question}

【提取的关键词】
{', '.join(keywords) if keywords else '无'}

【相关概念】
{', '.join(related_concepts) if related_concepts else '无'}

【搜索结果】
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

请分析：
1. 这些搜索结果与用户问题的相关性如何？
2. 哪些结果最相关？为什么？
3. 从这些结果中可以提取哪些关键信息点？
4. 应该如何组织答案？（直接回答、分点说明、对比说明等）

请以JSON格式返回：
{{
    "relevance_summary": "相关性总结（1-2句话）",
    "key_points": ["关键信息点1", "关键信息点2", "关键信息点3"],
    "answer_strategy": "答案生成策略（如：直接回答、分点说明、对比说明等）",
    "most_relevant_results": [1, 2]  // 最相关的结果序号列表
}}

只返回JSON，不要其他文字。
"""
            
            log.info("使用AI分析搜索结果...")
            response = llm_service.generate(prompt)
            
            # 尝试从响应中提取JSON
            json_match = re.search(r'\{[^{}]*"relevance_summary"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response.strip()
                json_str = re.sub(r'```json\s*', '', json_str)
                json_str = re.sub(r'```\s*', '', json_str)
                json_str = json_str.strip()
            
            try:
                result = json.loads(json_str)
                return result
            except json.JSONDecodeError as e:
                log.warning(f"AI分析结果JSON解析失败: {e}，响应: {response[:200]}")
                return {
                    "relevance_summary": "搜索结果与问题相关",
                    "key_points": [],
                    "answer_strategy": "直接回答",
                    "most_relevant_results": [1, 2, 3],
                }
                
        except Exception as e:
            log.warning(f"AI分析搜索结果失败: {e}")
            return {
                "relevance_summary": "搜索结果与问题相关",
                "key_points": [],
                "answer_strategy": "直接回答",
                "most_relevant_results": [1, 2, 3],
            }
    
    def _build_answer_prompt(
        self,
        question: str,
        context: str,
        search_results: List[Dict[str, Any]],
        analysis_result: Dict[str, Any],
        keywords: List[str]
    ) -> str:
        """
        构建答案生成的Prompt，让AI更好地利用搜索结果。
        
        Args:
            question: 用户问题
            context: 文档上下文
            search_results: 搜索结果列表
            analysis_result: AI分析结果
            keywords: 关键词列表
            
        Returns:
            完整的Prompt
        """
        # 构建搜索结果信息
        results_info = []
        for i, result in enumerate(search_results, 1):
            similarity = result.get("similarity", 0)
            title = result.get("title", "未知")
            results_info.append(f"{i}. {title} (相似度: {similarity:.2f})")
        
        results_summary = "\n".join(results_info)
        
        # 获取AI分析的关键信息
        relevance_summary = analysis_result.get("relevance_summary", "")
        key_points = analysis_result.get("key_points", [])
        answer_strategy = analysis_result.get("answer_strategy", "直接回答")
        most_relevant = analysis_result.get("most_relevant_results", [])
        
        # 构建关键信息点
        key_points_text = ""
        if key_points:
            key_points_text = "\n".join([f"- {point}" for point in key_points[:5]])
        
        # 构建最相关结果提示
        most_relevant_text = ""
        if most_relevant:
            most_relevant_titles = [
                search_results[i-1].get("title", "") 
                for i in most_relevant 
                if 1 <= i <= len(search_results)
            ]
            if most_relevant_titles:
                most_relevant_text = f"\n【最相关文档】优先参考以下文档：{', '.join(most_relevant_titles)}"
        
        prompt = f"""你是一位资深的AI知识库助手，擅长深入分析文档内容并生成高质量、结构化的答案。

【任务】
基于提供的文档内容，深入分析并回答用户的问题。你需要：
1. **深入理解**：仔细阅读文档内容，理解上下文和细节
2. **提取关键信息**：识别与问题相关的核心信息、关键步骤、重要概念
3. **综合分析**：如果涉及多个文档，要综合不同文档的信息，形成完整的答案
4. **结构化组织**：按照逻辑顺序组织答案，使用清晰的段落和分点说明
5. **深入阐述**：不仅要引用文档内容，还要进行解释、分析和总结

【用户问题】
{question}

【提取的关键词】
{', '.join(keywords) if keywords else '无'}

【搜索结果分析】
{relevance_summary if relevance_summary else '搜索结果与问题相关'}

【关键信息点】
{key_points_text if key_points_text else '需要从文档中提取'}

【答案生成策略】
{answer_strategy}{most_relevant_text}

【文档内容】
{context}

【搜索结果列表】
{results_summary}

【核心要求】
1. **深度分析**：
   - 不要简单引用文档中的一两句话
   - 要深入理解文档内容，提取关键信息并进行解释
   - 如果文档提到某个功能或概念，要详细说明其作用、使用方法、注意事项等

2. **完整性**：
   - 如果文档中有多个相关信息点，要全部提取并综合回答
   - 不要遗漏重要的细节、步骤、条件、限制等
   - 如果涉及多个方面，要全面覆盖

3. **结构化组织**：
   - 使用清晰的段落结构
   - 对于复杂问题，使用分点说明（1. 2. 3.）或分类说明
   - 按照逻辑顺序组织：概述 → 详细说明 → 总结

4. **可读性和专业性**：
   - 使用简体中文，语言流畅自然
   - 使用专业术语，但确保易于理解
   - 避免冗余和重复
   - 适当使用过渡词，使答案连贯

5. **引用和标注**：
   - 在答案开头或关键部分提及文档来源（如"根据《XXX文档》..."）
   - 如果信息来自多个文档，可以分别标注

【答案结构建议】
- **开头**：简要说明找到了哪些相关信息（可提及文档名称）
- **主体**：详细回答问题的各个方面，使用分点或分段说明
- **结尾**：如有必要，进行总结或补充说明

【注意事项】
- **相关性检查（最重要）**：
  - 首先判断文档内容是否真的与用户问题相关
  - 如果文档内容与问题**完全不相关**或**相关性很低**（相似度<0.5），必须明确说明"根据提供的文档，没有找到与问题相关的信息"
  - **不要**强行关联不相关的内容
  - **不要**基于不相关的文档生成答案
  - 如果文档相似度很低，应该明确拒绝回答，而不是强行生成答案

- 如果文档中没有直接回答问题的信息，可以基于相关内容进行合理推断，但要说明这是基于文档的推断
- 如果文档内容与问题不完全匹配，说明文档中找到了哪些相关信息，并解释这些信息如何帮助回答问题
- 如果多个文档有冲突信息，要对比说明并指出差异
- 如果文档中没有相关信息，明确说明"根据提供的文档，没有找到相关信息"

【答案】
请基于以上文档内容，深入分析并回答用户问题。要求答案完整、深入、有条理：
"""
        
        return prompt

    def _verify_answer_relevance(self, question: str, answer: str, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证答案是否真的回答了用户的问题。
        
        Args:
            question: 用户问题
            answer: 生成的答案
            search_results: 搜索结果列表
            
        Returns:
            验证结果，包含is_relevant和reason
        """
        try:
            # 如果搜索结果的平均相似度很低，直接认为不相关
            if search_results:
                avg_similarity = sum([r.get("similarity", 0) for r in search_results]) / len(search_results)
                if avg_similarity < 0.4:
                    return {
                        "is_relevant": False,
                        "reason": f"搜索结果平均相似度过低 ({avg_similarity:.3f} < 0.4)"
                    }
            
            # 提取问题关键词
            question_keywords = self._extract_keywords(question)
            if not question_keywords:
                return {"is_relevant": True, "reason": "无法提取问题关键词"}
            
            # 检查答案是否包含问题的主要关键词
            answer_lower = answer.lower()
            matched_keywords = [kw for kw in question_keywords if kw.lower() in answer_lower]
            match_ratio = len(matched_keywords) / len(question_keywords) if question_keywords else 0
            
            # 如果匹配的关键词少于50%，认为不相关
            if match_ratio < 0.5:
                return {
                    "is_relevant": False,
                    "reason": f"答案中匹配的关键词比例过低 ({match_ratio:.2%} < 50%)"
                }
            
            return {"is_relevant": True, "reason": "答案相关性验证通过"}
            
        except Exception as e:
            log.warning(f"答案相关性验证失败: {e}")
            # 验证失败时，默认认为相关（避免误判）
            return {"is_relevant": True, "reason": f"验证过程出错: {e}"}
    
    def _should_use_web_search(self, question: str, kb_result: Dict[str, Any]) -> bool:
        """
        判断是否需要使用网络搜索。
        
        Args:
            question: 用户问题
            kb_result: 知识库搜索结果
            
        Returns:
            是否需要网络搜索
        """
        # 如果知识库搜索成功且有相关文档，检查相似度
        if kb_result.get("success") and len(kb_result.get("sources", [])) > 0:
            sources = kb_result.get("sources", [])
            max_similarity = max([s.get("similarity", 0) for s in sources])
            
            # 如果最高相似度>=0.6，认为知识库结果足够好，不需要网络搜索
            if max_similarity >= 0.6:
                return False
            
            # 如果相似度在0.5-0.6之间，判断是否是通用概念问题
            if max_similarity >= 0.5:
                # 判断是否是通用概念问题（如"是什么"、"定义"等）
                if self._is_general_concept_question(question):
                    log.info(f"检测到通用概念问题，且文档相似度较低({max_similarity:.3f})，建议使用网络搜索")
                    return True
            
            # 如果相似度<0.5，建议使用网络搜索
            if max_similarity < 0.5:
                log.info(f"文档相似度过低({max_similarity:.3f})，建议使用网络搜索")
                return True
        
        # 如果知识库搜索失败或没有找到文档，建议使用网络搜索
        if not kb_result.get("success") or len(kb_result.get("sources", [])) == 0:
            log.info("知识库未找到相关文档，建议使用网络搜索")
            return True
        
        return False
    
    def _is_general_concept_question(self, question: str) -> bool:
        """
        判断是否是通用概念问题。
        
        Args:
            question: 用户问题
            
        Returns:
            是否是通用概念问题
        """
        # 通用概念问题的关键词
        concept_keywords = [
            "是什么", "什么是", "定义", "含义", "意思", "概念",
            "介绍", "说明", "解释", "如何理解", "怎么理解"
        ]
        
        question_lower = question.lower()
        for keyword in concept_keywords:
            if keyword in question_lower:
                return True
        
        return False
    
    def _search_web_and_merge(self, question: str, kb_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索网络并合并结果。
        
        Args:
            question: 用户问题
            kb_result: 知识库搜索结果
            
        Returns:
            合并后的结果
        """
        try:
            web_service = self.web_search_service
            if not web_service:
                log.warning("网络搜索服务不可用，返回知识库结果")
                return kb_result
            
            # 搜索网络
            web_results = web_service.search(question, max_results=5)
            
            if not web_results:
                log.warning("网络搜索未找到结果，返回知识库结果")
                return kb_result
            
            # 使用LLM合并知识库和网络搜索结果
            from infrastructure.llm.service import LLMService
            llm_service = LLMService()
            
            # 构建合并提示词
            kb_answer = kb_result.get("answer", "")
            kb_sources = kb_result.get("sources", [])
            
            # 构建网络搜索结果摘要
            web_summary = "\n".join([
                f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}..."
                for r in web_results[:3]
            ])
            
            # 构建合并提示词
            prompt = f"""你是一位专业的AI助手，需要结合知识库信息和网络搜索结果来回答用户问题。

【用户问题】
{question}

【知识库信息】
{'找到了以下相关文档：' if kb_sources else '未找到相关文档'}
{chr(10).join([f'- {s.get("title", "")} (相似度: {s.get("similarity", 0):.2f})' for s in kb_sources[:3]]) if kb_sources else '无'}

{'【知识库答案】' if kb_answer and kb_result.get('success') else ''}
{kb_answer if kb_answer and kb_result.get('success') else '知识库未找到相关信息'}

【网络搜索结果】
{web_summary}

【要求】
1. 优先使用知识库信息（如果知识库有相关信息）
2. 使用网络搜索结果补充知识库信息的不足
3. 明确标注信息来源：
   - 如果信息来自知识库，标注"根据知识库文档..."
   - 如果信息来自网络搜索，标注"根据网络搜索..."
4. 如果知识库和网络信息有冲突，优先使用知识库信息
5. 答案要完整、准确、有条理
6. 使用简体中文回答

【答案】
请结合以上信息，回答用户问题：
"""
            
            # 生成合并后的答案
            merged_answer = llm_service.generate(prompt)
            
            # 合并来源
            merged_sources = list(kb_sources)
            for web_result in web_results[:3]:
                merged_sources.append({
                    "title": web_result.get("title", ""),
                    "url": web_result.get("url", ""),
                    "source": "web_search",
                    "similarity": 0.0,  # 网络搜索结果没有相似度
                })
            
            # 保存网络搜索结果
            query_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self._save_query_result(question, "web_search", {
                "results_count": len(web_results),
                "results": web_results[:5]
            }, query_timestamp)
            
            log.info("✅ 网络搜索结果已合并到答案中")
            
            return {
                "success": True,
                "answer": merged_answer.strip(),
                "sources": merged_sources,
                "has_web_search": True,  # 标记使用了网络搜索
                "suggest_web_search": False,  # 已经使用了，不再建议
                "max_similarity": max([s.get("similarity", 0) for s in kb_sources]) if kb_sources else 0.0,
            }
            
        except Exception as e:
            log.error(f"网络搜索和合并失败: {e}")
            # 如果网络搜索失败，返回知识库结果
            return kb_result
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取向量存储信息。

        Returns:
            集合信息
        """
        try:
            info = self.rag_engine.vector_store.get_collection_info()
            return {
                "success": True,
                "info": info,
            }
        except Exception as e:
            log.error(f"获取集合信息失败: {e}")
            return {
                "success": False,
                "info": {},
            }

