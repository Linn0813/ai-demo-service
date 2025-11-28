# encoding: utf-8
"""
文档加载器，用于从飞书获取文档内容。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.logger import log
from .feishu_client import FeishuAPIClient


class FeishuDocumentLoader:
    """飞书文档加载器，用于获取和处理飞书文档内容。"""

    def __init__(self, feishu_client: Optional[FeishuAPIClient] = None):
        """
        初始化文档加载器。

        Args:
            feishu_client: 飞书API客户端，如果不提供则自动创建（会根据配置自动选择用户身份或应用身份）
        """
        from app.config import settings
        if feishu_client is None:
            # 优先使用用户身份权限（如果已通过OAuth授权）
            # 检查全局缓存中是否有user_access_token
            use_user_token = settings.feishu_use_user_token
            if not use_user_token:
                # 尝试从全局缓存检查是否有user_token
                from .feishu_client import _get_cached_token
                cached_user_token = _get_cached_token(settings.feishu_app_id, True)
                if cached_user_token:
                    # 如果缓存中有user_token，优先使用它
                    use_user_token = True
                    log.info("检测到已授权的user_access_token，将使用用户身份权限")
            feishu_client = FeishuAPIClient(use_user_token=use_user_token)
        self.client = feishu_client

    def load_wiki_spaces(self, query: str = "") -> List[Dict[str, Any]]:
        """
        加载知识库空间列表。

        Args:
            query: 搜索关键词（可选）

        Returns:
            知识库空间列表
        """
        try:
            result = self.client.search_wiki_spaces(query=query, limit=50)
            
            # 处理响应格式
            if result.get("code") == 0:
                data = result.get("data", {})
                # 根据飞书API文档，响应格式：data.items 包含空间列表
                items = data.get("items", [])
                
                if items:
                    log.info(f"找到 {len(items)} 个知识空间")
                    return items
                else:
                    log.warning(f"知识空间列表为空（响应数据: {data}）")
                    return []
            else:
                error_msg = result.get("msg", "未知错误")
                error_code = result.get("code", "未知")
                log.error(f"获取知识空间列表失败: {error_msg} (code: {error_code})")
                
                # 常见错误码处理
                if error_code == 99991672 or error_code == 99991663:
                    # 权限错误，抛出异常以便前端检测
                    raise RuntimeError(
                        f"权限不足: {error_msg} (code: {error_code})。"
                        "请先进行飞书授权或申请应用身份权限。"
                    )
                elif error_code == 99991664:
                    # 权限错误，抛出异常以便前端检测
                    raise RuntimeError(
                        f"权限不足: 知识空间不存在或无权访问 (code: {error_code})。"
                        "请先进行飞书授权或申请应用身份权限。"
                    )
                elif "404" in str(error_code) or "not found" in error_msg.lower():
                    log.error("API端点可能不正确，请检查飞书API文档")
                    return []
                else:
                    # 其他错误也抛出异常，让上层处理
                    raise RuntimeError(f"获取知识空间列表失败: {error_msg} (code: {error_code})")
        except RuntimeError:
            # 重新抛出RuntimeError（包括权限错误），让上层处理
            raise
        except Exception as e:
            error_str = str(e)
            # 检查是否是权限相关的错误
            if "99991672" in error_str or "99991663" in error_str or "99991664" in error_str or "权限" in error_str:
                # 权限错误，重新抛出
                raise RuntimeError(f"权限不足: {error_str}。请先进行飞书授权或申请应用身份权限。") from e
            log.error(f"加载知识库空间失败: {e}")
            raise RuntimeError(f"加载知识库空间失败: {error_str}") from e

    def load_document_content(self, document_token: str, is_wiki_node: bool = True) -> Optional[str]:
        """
        加载文档内容并转换为纯文本。

        Args:
            document_token: 文档token
            is_wiki_node: 是否为知识库节点（wiki node），默认True（因为搜索返回的都是wiki节点）

        Returns:
            文档的纯文本内容，如果失败则返回None
        """
        try:
            # 获取文档内容（优先使用wiki API）
            result = self.client.get_document_content(document_token, is_wiki_node=is_wiki_node)
            if result.get("code") != 0:
                # 静默处理权限错误，不输出WARNING日志
                error_code = result.get("code")
                if error_code in (404, 99991679):
                    log.debug(f"无法获取文档内容（权限限制）: {document_token[:30]}...")
                else:
                    log.warning(f"获取文档内容失败: {result.get('msg')}")
                return None

            data = result.get("data", {})
            
            # wiki API返回的格式可能不同，需要适配
            # 如果是wiki节点，可能需要特殊处理
            if is_wiki_node:
                # 检查是否是wiki节点结构
                node = data.get("node", {})
                if node:
                    # wiki节点可能包含obj_type和obj_token，需要进一步获取实际文档内容
                    obj_type = node.get("obj_type", "")
                    obj_token = node.get("obj_token", "")
                    
                    # 如果是docx类型，使用obj_token获取文档内容
                    if obj_type == "docx" and obj_token:
                        log.debug(f"wiki节点是docx类型，使用obj_token获取内容: {obj_token[:30]}...")
                        # 递归调用，但这次不是wiki节点
                        return self.load_document_content(obj_token, is_wiki_node=False)
                    
                    # 如果wiki节点直接包含内容，提取文本
                    content = node.get("content", {})
                    if content:
                        text = self._extract_text_from_content(content)
                        if text:
                            return text
                    
                    # 如果都没有，尝试从node的其他字段提取
                    title = node.get("title", "")
                    if title:
                        log.debug(f"wiki节点没有内容，仅返回标题: {title}")
                        return title  # 至少返回标题
                
                # 如果wiki API返回的不是node结构，尝试直接获取content
                # 或者document_token本身就是文档token（不是wiki节点token）
                # 这种情况下，尝试使用docs/docx API
                log.debug("wiki API返回格式不符合预期，尝试使用docs/docx API...")
                # 不抛出异常，让下面的代码继续处理
            
            # 标准文档内容格式
            # 检查是否有raw_content格式（docx API的raw_content端点返回的格式）
            raw_content = data.get("content", {})
            if raw_content:
                # raw_content可能是字符串或字典
                if isinstance(raw_content, str):
                    # 如果是字符串，进行清理和格式化
                    log.info(f"✅ 获取到raw_content字符串，长度: {len(raw_content)} 字符")
                    cleaned_content = self._clean_raw_content(raw_content)
                    return cleaned_content
                elif isinstance(raw_content, dict):
                    # 如果是字典，尝试提取文本
                    text = self._extract_text_from_content(raw_content)
                    if text:
                        return text
            
            # 标准文档内容格式（content字段）
            content = data.get("content", {})
            if content:
                # 提取文本内容
                text = self._extract_text_from_content(content)
                return text

            return None

        except Exception as e:
            # 静默处理错误，不输出大量ERROR日志（这些错误是预期的，因为权限限制）
            # 只在DEBUG级别记录详细信息
            error_str = str(e)
            if "404" in error_str or "99991679" in error_str or "权限" in error_str:
                # 权限或404错误是预期的，只记录DEBUG级别
                log.debug(f"无法获取文档内容（权限限制或文档不存在）: {document_token[:30]}...")
            else:
                # 其他错误才记录WARNING
                log.warning(f"加载文档内容失败: {type(e).__name__}: {str(e)[:100]}")
            return None

    def load_document_meta(self, document_token: str) -> Optional[Dict[str, Any]]:
        """
        加载文档元信息。

        Args:
            document_token: 文档token

        Returns:
            文档元信息字典，包含标题、URL等信息
        """
        try:
            result = self.client.get_document_meta(document_token)
            if result.get("code") != 0:
                # 静默处理权限错误，不输出大量WARNING日志
                error_code = result.get("code")
                if error_code in (404, 99991679):
                    log.debug(f"无法获取文档元信息（权限限制）: {document_token[:30]}...")
                else:
                    log.warning(f"获取文档元信息失败: {result.get('msg')}")
                return None

            data = result.get("data", {})
            document = data.get("document", {})

            return {
                "document_id": document.get("document_id"),
                "title": document.get("title"),
                "url": document.get("url"),
                "create_time": document.get("create_time"),
                "update_time": document.get("update_time"),
                "owner_id": document.get("owner_id"),
            }

        except Exception as e:
            # 静默处理权限错误，不输出ERROR日志
            error_str = str(e)
            if "404" in error_str or "99991679" in error_str or "权限" in error_str:
                log.debug(f"无法获取文档元信息（权限限制）: {document_token[:30]}...")
            else:
                log.warning(f"加载文档元信息失败: {type(e).__name__}: {str(e)[:100]}")
            return None

    def _extract_text_from_content(self, content: Dict[str, Any]) -> str:
        """
        从飞书文档内容中提取纯文本。

        Args:
            content: 飞书文档内容结构

        Returns:
            提取的纯文本
        """
        text_parts: List[str] = []

        # 递归提取文本
        def extract_from_block(block: Dict[str, Any]) -> None:
            block_type = block.get("block_type", "")
            text_elem = block.get("text", {})

            # 提取文本元素
            if text_elem:
                text_content = self._extract_text_from_elem(text_elem)
                if text_content:
                    text_parts.append(text_content)

            # 处理子块
            children = block.get("children", [])
            for child in children:
                extract_from_block(child)

        # 从文档内容中提取
        blocks = content.get("blocks", [])
        for block in blocks:
            extract_from_block(block)

        return "\n".join(text_parts)

    def _extract_text_from_elem(self, text_elem: Dict[str, Any]) -> str:
        """
        从文本元素中提取文本。

        Args:
            text_elem: 文本元素

        Returns:
            提取的文本
        """
        if isinstance(text_elem, str):
            return text_elem

        if isinstance(text_elem, dict):
            # 提取文本内容
            elements = text_elem.get("elements", [])
            text_parts = []

            for elem in elements:
                if isinstance(elem, dict):
                    text_run = elem.get("text_run", {})
                    if text_run:
                        content = text_run.get("content", "")
                        if content:
                            text_parts.append(content)
                    elif isinstance(elem, str):
                        text_parts.append(elem)

            return "".join(text_parts)

        return ""
    
    def _clean_raw_content(self, content: str) -> str:
        """
        清理raw_content中的markdown标记和特殊字符，保留文档结构。
        
        Args:
            content: 原始内容字符串
            
        Returns:
            清理后的内容
        """
        if not content:
            return ""
        
        # 1. 清理多余的空白字符（保留段落分隔）
        # 将多个连续的空行合并为两个空行（段落分隔）
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 2. 清理markdown标记（如果存在）
        # 移除markdown标题标记（但保留标题文本）
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
        
        # 3. 清理特殊字符（保留中文、英文、数字、标点）
        # 移除控制字符，但保留换行符和制表符
        content = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', content)
        
        # 4. 统一换行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # 5. 清理行首行尾空白
        lines = content.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        content = '\n'.join(cleaned_lines)
        
        # 6. 移除文档开头和结尾的空白
        content = content.strip()
        
        return content

    def load_all_documents_from_space(self, space_id: str) -> List[Dict[str, Any]]:
        """
        从知识库空间加载所有文档。

        Args:
            space_id: 知识库空间ID

        Returns:
            文档列表，每个文档包含内容和元信息
        """
        documents = []

        try:
            # 获取知识库节点
            result = self.client.get_wiki_nodes(space_id)
            if result.get("code") != 0:
                log.warning(f"获取知识库节点失败: {result.get('msg')}")
                return []

            data = result.get("data", {})
            
            # 添加调试日志（使用INFO级别确保能看到）
            log.info(f"知识库空间 {space_id} 的API响应: code={result.get('code')}, data keys={list(data.keys())}")
            
            # 处理API返回格式：可能是items列表或node树结构
            items = data.get("items", [])
            node = data.get("node", {})
            
            # 递归处理节点项的函数（使用集合避免重复处理）
            processed_tokens = set()  # 记录已处理的obj_token，避免重复加载
            
            def process_node_item(item: Dict[str, Any], depth: int = 0) -> None:
                """处理单个节点项（支持items列表格式和node树格式）。"""
                obj_type = item.get("obj_type", "")  # docx, file等
                obj_token = item.get("obj_token", "")
                node_title = item.get("title", "未知")
                has_child = item.get("has_child", False)
                node_token = item.get("node_token", "")
                indent = "  " * depth
                
                log.info(f"{indent}处理节点: {node_title}, obj_type: {obj_type}, has_child: {has_child}")
                
                # 如果是docx类型的文档，加载内容（避免重复加载）
                if obj_type == "docx" and obj_token:
                    if obj_token in processed_tokens:
                        log.debug(f"{indent}跳过已处理的文档: {node_title}")
                        return
                    
                    processed_tokens.add(obj_token)
                    log.info(f"{indent}找到文档: {node_title}, 开始加载内容...")
                    content = self.load_document_content(obj_token)
                    meta = self.load_document_meta(obj_token)

                    if content and meta:
                        documents.append({
                            "token": obj_token,
                            "content": content,
                            "meta": meta,
                            "space_id": space_id,
                        })
                        log.info(f"{indent}✅ 文档加载成功: {node_title}, 内容长度: {len(content)} 字符")
                    else:
                        log.warning(f"{indent}❌ 文档加载失败: {node_title}, content={bool(content)}, meta={bool(meta)}")
                elif obj_type:
                    log.debug(f"{indent}跳过非docx节点: {node_title} (obj_type: {obj_type})")
                
                # 如果有子节点，递归获取子节点列表
                if has_child and node_token:
                    log.debug(f"{indent}节点有子节点，获取子节点列表...")
                    try:
                        child_result = self.client.get_wiki_nodes(space_id, parent_node_id=node_token)
                        if child_result.get("code") == 0:
                            child_data = child_result.get("data", {})
                            child_items = child_data.get("items", [])
                            child_node = child_data.get("node", {})
                            
                            if child_items:
                                log.debug(f"{indent}找到 {len(child_items)} 个子节点")
                                for child_item in child_items:
                                    process_node_item(child_item, depth + 1)
                            elif child_node:
                                process_node_item(child_node, depth + 1)
                    except Exception as e:
                        log.warning(f"{indent}获取子节点失败: {e}")
            
            # 处理根节点
            if items:
                # API返回的是items列表格式
                log.info(f"知识库空间 {space_id} 返回了 {len(items)} 个根节点")
                for item in items:
                    process_node_item(item, depth=0)
            elif node:
                # API返回的是node树格式
                log.info(f"知识库空间 {space_id} 返回了节点树结构")
                process_node_item(node, depth=0)
            else:
                log.warning(f"知识库空间 {space_id} 的节点数据为空，可能知识库是空的或API返回格式不对")
                log.info(f"完整的API响应数据: {result}")
                return []

            log.info(f"从知识库空间 {space_id} 加载了 {len(documents)} 个文档")
            return documents

        except Exception as e:
            log.error(f"加载知识库文档失败: {e}")
            return []

