# encoding: utf-8
"""
知识库服务层，封装知识库相关业务逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.engine.knowledge_base import (
    FeishuDocumentLoader,
    RAGEngine,
    VectorStore,
)
from core.logger import log


class KnowledgeBaseService:
    """知识库服务，提供文档同步和问答功能。"""

    def __init__(self):
        """初始化知识库服务。"""
        self.document_loader = FeishuDocumentLoader()
        self._rag_engine = None

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

    def sync_documents_from_space(self, space_id: str) -> Dict[str, Any]:
        """
        从知识库空间同步文档。

        Args:
            space_id: 知识库空间ID

        Returns:
            同步结果，包含同步的文档数量和状态
        """
        try:
            log.info(f"开始同步知识库空间: {space_id}")

            # 加载所有文档
            documents = self.document_loader.load_all_documents_from_space(space_id)

            if not documents:
                return {
                    "success": False,
                    "message": "未找到文档",
                    "document_count": 0,
                }

            # 准备文档数据
            doc_data = []
            for doc in documents:
                doc_data.append({
                    "id": doc["token"],
                    "content": doc["content"],
                    "metadata": {
                        "title": doc["meta"].get("title", "未知标题"),
                        "url": doc["meta"].get("url", ""),
                        "space_id": space_id,
                        "document_id": doc["meta"].get("document_id", ""),
                    },
                })

            # 索引文档
            indexed_count = self.rag_engine.index_documents(doc_data)

            return {
                "success": True,
                "message": "同步成功",
                "document_count": len(documents),
                "indexed_count": indexed_count,
            }

        except Exception as e:
            log.error(f"同步文档失败: {e}")
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "document_count": 0,
            }

    def sync_all_spaces(self) -> Dict[str, Any]:
        """
        同步所有知识库空间。

        Returns:
            同步结果
        """
        try:
            # 获取所有知识库空间
            spaces = self.document_loader.load_wiki_spaces()

            total_documents = 0
            success_count = 0
            failed_spaces = []

            for space in spaces:
                space_id = space.get("space_id", "")
                space_name = space.get("name", "未知")

                if not space_id:
                    continue

                log.info(f"同步知识库空间: {space_name} ({space_id})")

                result = self.sync_documents_from_space(space_id)
                if result["success"]:
                    success_count += 1
                    total_documents += result["document_count"]
                else:
                    failed_spaces.append({
                        "space_id": space_id,
                        "name": space_name,
                        "error": result["message"],
                    })

            return {
                "success": True,
                "message": f"同步完成：成功 {success_count} 个，失败 {len(failed_spaces)} 个",
                "total_spaces": len(spaces),
                "success_count": success_count,
                "failed_count": len(failed_spaces),
                "total_documents": total_documents,
                "failed_spaces": failed_spaces,
            }

        except Exception as e:
            error_msg = str(e)
            log.error(f"同步所有知识库失败: {e}")
            
            # 检查是否是权限错误，如果是则重新抛出以便API层处理
            if "99991672" in error_msg or "权限" in error_msg or "Access denied" in error_msg:
                raise  # 重新抛出异常，让API层返回403
            
            return {
                "success": False,
                "message": f"同步失败: {error_msg}",
                "total_spaces": 0,
                "success_count": 0,
                "failed_count": 0,
                "total_documents": 0,
            }

    def ask(self, question: str, use_realtime_search: bool = True, space_id: Optional[str] = None) -> Dict[str, Any]:
        """
        回答问题。
        
        支持两种模式：
        1. 实时搜索模式（默认）：直接使用飞书API搜索，无需先同步文档
        2. 向量搜索模式：使用本地向量存储进行语义搜索（需要先同步文档）

        Args:
            question: 用户问题
            use_realtime_search: 是否使用实时搜索模式（默认True）
            space_id: 指定搜索的知识库空间ID，如果不提供则搜索所有空间

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
                return self._ask_with_realtime_search(question, space_id=space_id)
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
            # 检查是否是权限错误
            if "99991672" in error_msg or "权限" in error_msg or "Access denied" in error_msg:
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
            from core.engine.base.llm_service import LLMService
            from core.engine.base.embedding_service import EmbeddingService
            import re
            
            log.info(f"使用实时搜索模式处理问题: {question}")
            
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
            
            # 【AI分析问题】使用LLM分析问题并提取搜索关键词和策略
            search_strategy = self._analyze_question_with_ai(question)
            keywords = search_strategy.get("keywords", [])
            search_queries = search_strategy.get("search_queries", [question])
            related_concepts = search_strategy.get("related_concepts", [])
            
            log.info(f"AI分析结果:")
            log.info(f"  关键词: {keywords}")
            log.info(f"  搜索查询: {search_queries}")
            log.info(f"  相关概念: {related_concepts}")
            
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
            log.info(f"优化后的搜索查询（去除疑问词）: {search_queries}")
            
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
            
            log.info(f"找到 {len(all_results)} 个候选文档，开始加载内容并重排序...")
            
            # 加载文档内容并计算相似度
            doc_results = []
            import time
            
            # 从搜索结果中提取URL（如果有）
            for idx, result in enumerate(all_results[:15]):  # 限制加载数量以提高性能
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
                            doc_results.append({
                                "title": title,
                                "url": url,
                                "content": f"文档标题：{title}",
                                "full_content": "",
                                "similarity": 0.5,  # 给予中等相似度，因为至少标题匹配
                                "obj_token": result.get("obj_token", ""),
                                "has_content": False,  # 标记为没有完整内容
                            })
                        continue
                    
                    # 提取最相关的文档片段
                    relevant_chunk = self._extract_relevant_chunk(doc_content, question, keywords)
                    
                    # 计算相似度（使用embedding）- 使用提取的相关片段计算，而不是原始内容
                    # 注意：这里使用relevant_chunk而不是doc_content，因为relevant_chunk是提取的最相关部分
                    similarity = self._calculate_similarity(question, relevant_chunk)
                    
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
                    log.warning(f"处理文档 {result.get('title', '未知')} 失败: {e}")
                    # 即使处理失败，也尝试保留标题和URL
                    title = result.get("title", "未知标题")
                    url = result.get("url", "")
                    if title and title != "未知标题":
                        doc_results.append({
                            "title": title,
                            "url": url,
                            "content": f"文档标题：{title}",
                            "full_content": "",
                            "similarity": 0.3,
                            "obj_token": result.get("obj_token", ""),
                            "has_content": False,
                        })
                    continue
            
            # 按相似度排序（优先有完整内容的文档）
            doc_results.sort(key=lambda x: (x.get("has_content", False), x["similarity"]), reverse=True)
            
            # 分离有内容和无内容的文档
            results_with_content = [r for r in doc_results if r.get("has_content", True)]
            results_without_content = [r for r in doc_results if not r.get("has_content", True)]
            
            # 优先使用有内容的文档，相似度阈值0.3
            filtered_results = [r for r in results_with_content if r["similarity"] >= 0.3]
            
            # 如果没有高相似度的有内容文档，至少返回前几个有内容的
            if not filtered_results:
                filtered_results = results_with_content[:3] if results_with_content else []
            
            # 如果没有有内容的文档，使用无内容的文档（至少标题匹配）
            if not filtered_results and results_without_content:
                filtered_results = results_without_content[:5]
                log.info(f"无法获取文档完整内容，使用文档标题作为来源（{len(filtered_results)}个）")
            
            # 取前5个最相关的结果
            top_results = filtered_results[:5]
            
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
            
            return {
                "success": True,
                "answer": answer.strip(),
                "sources": sources,
            }
            
        except Exception as e:
            log.error(f"实时搜索模式失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "answer": f"实时搜索失败: {str(e)}",
                "sources": [],
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
            from core.engine.base.llm_service import LLMService
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
                from core.engine.base.embedding_service import EmbeddingService
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
            from core.engine.base.embedding_service import EmbeddingService
            import numpy as np
            
            # 初始化embedding服务
            embedding_service = EmbeddingService()
            
            # 向量化问题和内容
            # 注意：content应该是已经提取的相关片段，不需要再截取前500字符
            # 如果content太长（超过2000字符），截取前2000字符以提高性能
            content_to_embed = content[:2000] if len(content) > 2000 else content
            question_vector = np.array(embedding_service.embed_text(question))
            content_vector = np.array(embedding_service.embed_text(content_to_embed))
            
            # 计算余弦相似度
            dot_product = np.dot(question_vector, content_vector)
            norm_q = np.linalg.norm(question_vector)
            norm_c = np.linalg.norm(content_vector)
            
            if norm_q == 0 or norm_c == 0:
                return 0.0
            
            similarity = dot_product / (norm_q * norm_c)
            
            # 确保相似度在0-1范围内
            return max(0.0, min(1.0, float(similarity)))
            
        except Exception as e:
            log.warning(f"计算相似度失败: {e}，使用默认值")
            # 如果计算失败，基于关键词匹配返回一个估计值
            keywords = self._extract_keywords(question)
            content_lower = content.lower()
            match_count = sum(1 for kw in keywords if kw.lower() in content_lower)
            return min(0.8, 0.3 + match_count * 0.1)  # 基础分数0.3，每个关键词匹配+0.1
    
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
            from core.engine.base.llm_service import LLMService
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
- 如果文档中没有直接回答问题的信息，可以基于相关内容进行合理推断，但要说明这是基于文档的推断
- 如果文档内容与问题不完全匹配，说明文档中找到了哪些相关信息，并解释这些信息如何帮助回答问题
- 如果多个文档有冲突信息，要对比说明并指出差异
- 如果文档中没有相关信息，明确说明"根据提供的文档，没有找到相关信息"

【答案】
请基于以上文档内容，深入分析并回答用户问题。要求答案完整、深入、有条理：
"""
        
        return prompt

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

