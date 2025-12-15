# encoding: utf-8
"""知识库和飞书 OAuth 路由"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from shared.config import settings
from shared.logger import log
from models import (
    AskQuestionRequest,
    AskQuestionResponse,
    CollectionInfoResponse,
    SyncDocumentsRequest,
    SyncDocumentsResponse,
    WikiSpacesResponse,
)

# 知识库服务（可选，如果依赖未安装则跳过）
try:
    from domain.knowledge_base.service import KnowledgeBaseService
    KNOWLEDGE_BASE_AVAILABLE = True
except ImportError as e:
    KNOWLEDGE_BASE_AVAILABLE = False
    KnowledgeBaseService = None
    import warnings
    warnings.warn(
        f"知识库功能不可用（缺少依赖）: {e}\n"
        "如果需要使用知识库功能，请安装: pip install sentence-transformers chromadb",
        ImportWarning
    )

router = APIRouter(tags=["knowledge-base", "feishu-oauth"])


# ==================== 飞书 OAuth 路由 ====================

@router.get("/feishu/oauth/authorize")
def get_oauth_authorize_url(state: Optional[str] = None):
    """
    获取OAuth授权URL（用于用户身份权限）。
    
    Args:
        state: 状态参数（可选，用于防止CSRF攻击）
    
    Returns:
        授权URL
    """
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )
    
    try:
        from infrastructure.external.feishu.client import FeishuAPIClient
        
        client = FeishuAPIClient(use_user_token=True)
        redirect_uri = settings.feishu_redirect_uri
        
        oauth_url = client.get_oauth_url(redirect_uri=redirect_uri, state=state)
        return {
            "oauth_url": oauth_url,
            "message": "请访问此URL进行授权",
            "redirect_uri": redirect_uri,
            "tip": "如果遇到redirect_uri错误，请在飞书开放平台配置此回调地址"
        }
    except Exception as exc:
        log.exception("获取OAuth授权URL失败")
        raise HTTPException(status_code=500, detail=f"获取OAuth授权URL失败: {exc}") from exc


@router.get("/feishu/oauth/callback")
def oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None):
    """
    OAuth回调处理（用于用户身份权限）。
    
    Args:
        request: FastAPI请求对象（用于获取前端URL）
        code: OAuth授权码（可选，如果未提供则显示错误页面）
        state: 状态参数（可选）
    
    Returns:
        授权结果（HTML页面，自动跳转回前端）
    """
    try:
        # 动态获取前端URL（优先使用配置，如果没有则从请求头推断）
        frontend_url = settings.frontend_url
        
        # 尝试从请求头推断前端URL
        referer = request.headers.get("referer", "")
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        scheme = request.url.scheme if hasattr(request.url, 'scheme') else "http"
        
        log.info(f"OAuth回调 - 配置的前端URL: {frontend_url}")
        log.info(f"OAuth回调 - Referer: {referer}")
        log.info(f"OAuth回调 - Origin: {origin}")
        log.info(f"OAuth回调 - Host: {host}")
        log.info(f"OAuth回调 - 授权码: {code[:20] + '...' if code else 'None'}")
        
        # 检测是否是手机访问
        user_agent = request.headers.get("user-agent", "").lower()
        is_mobile = any(keyword in user_agent for keyword in ["mobile", "android", "iphone", "ipad", "ipod"])
        
        log.info(f"OAuth回调 - 是否手机访问: {is_mobile}")
        
        # 如果配置的是默认值，尝试从请求头推断
        if not frontend_url or frontend_url == "http://localhost:3000":
            if origin:
                frontend_url = origin
                log.info(f"从Origin推断前端URL: {frontend_url}")
            elif referer:
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                if parsed.path.startswith('/ai/') or parsed.path == '/' or not parsed.path.startswith('/api/'):
                    frontend_url = f"{parsed.scheme}://{parsed.netloc}"
                    log.info(f"从Referer推断前端URL: {frontend_url}")
                elif host and '8113' not in host:
                    frontend_url = f"{scheme}://{host}"
                    log.info(f"使用推断的前端URL: {frontend_url}")
                else:
                    frontend_url = settings.frontend_url
                    log.info(f"使用默认前端URL: {frontend_url}")
            elif host and '8113' not in host:
                frontend_url = f"{scheme}://{host}"
                log.info(f"从Host推断前端URL: {frontend_url}")
            else:
                frontend_url = settings.frontend_url
                log.info(f"使用默认前端URL: {frontend_url}")
        
        frontend_url = frontend_url.rstrip('/')
        
        if is_mobile and ('localhost' in frontend_url or '127.0.0.1' in frontend_url):
            log.warning(f"手机访问但前端URL是localhost，无法直接跳转: {frontend_url}")
        
        log.info(f"最终使用的前端URL: {frontend_url}")
    except Exception as e:
        log.error(f"获取前端URL失败: {e}")
        frontend_url = settings.frontend_url or "http://localhost:3000"
    
    if not code:
        log.warning("OAuth回调未收到授权码")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>授权失败</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f7fa; }}
                .error {{ color: #f56c6c; font-size: 24px; margin-bottom: 20px; }}
                .message {{ color: #666; margin-bottom: 30px; }}
                .debug {{ color: #999; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="error">❌ 授权失败</div>
            <div class="message">未收到授权码，请重新进行授权流程</div>
            <div class="debug">前端URL: {frontend_url}</div>
            <script>
                setTimeout(function() {{
                    window.location.href = '{frontend_url}/ai/knowledge-base';
                }}, 3000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=400)
    
    if not KNOWLEDGE_BASE_AVAILABLE:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>授权失败</title>
        </head>
        <body>
            <h1>授权失败</h1>
            <p>知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb</p>
            <script>
                setTimeout(function() {{
                    window.location.href = '{frontend_url}/ai/knowledge-base';
                }}, 3000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=503)
    
    try:
        from infrastructure.external.feishu.client import FeishuAPIClient
        client = FeishuAPIClient(use_user_token=True)
        client.set_user_code(code)
        
        try:
            token = client._token_manager.get_token()
            log.info(f"OAuth授权成功，token已获取。前端URL: {frontend_url}")
            
            redirect_url = f"{frontend_url.rstrip('/')}/ai/knowledge-base?auth_success=true"
            log.info(f"准备跳转到: {redirect_url}")
            
            # 如果是手机访问且前端URL是localhost，显示特殊提示页面
            if is_mobile and ('localhost' in frontend_url or '127.0.0.1' in frontend_url):
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>授权成功</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; text-align: center; padding: 30px 20px; background: #f5f7fa; max-width: 600px; margin: 0 auto; }}
                        .success {{ color: #67c23a; font-size: 28px; margin-bottom: 20px; font-weight: bold; }}
                        .message {{ color: #333; font-size: 16px; margin-bottom: 20px; line-height: 1.6; }}
                        .tip {{ color: #666; font-size: 14px; margin-bottom: 30px; line-height: 1.6; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                        .link-box {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; word-break: break-all; }}
                        .link {{ color: #409eff; font-size: 14px; text-decoration: none; word-break: break-all; }}
                        .copy-btn {{ background: #409eff; color: white; border: none; padding: 10px 20px; border-radius: 4px; font-size: 14px; cursor: pointer; margin-top: 10px; }}
                        .copy-btn:active {{ background: #337ecc; }}
                    </style>
                </head>
                <body>
                    <div class="success">✅ 授权成功！</div>
                    <div class="message">您的授权已成功完成</div>
                    <div class="tip">
                        <p><strong>📱 手机扫描提示：</strong></p>
                        <p>由于您使用手机扫描，无法直接跳转到电脑上的页面。</p>
                        <p>请在电脑浏览器中访问以下地址完成授权：</p>
                    </div>
                    <div class="link-box">
                        <div class="link" id="redirectLink">{redirect_url}</div>
                        <button class="copy-btn" onclick="copyLink()">复制链接</button>
                    </div>
                    <div class="tip">
                        <p><strong>💡 提示：</strong></p>
                        <p>1. 点击"复制链接"按钮</p>
                        <p>2. 在电脑浏览器中打开复制的链接</p>
                        <p>3. 或者直接在电脑浏览器中访问：<br>{frontend_url}/ai/knowledge-base</p>
                    </div>
                    <script>
                        function copyLink() {{
                            const link = document.getElementById('redirectLink').textContent;
                            if (navigator.clipboard) {{
                                navigator.clipboard.writeText(link).then(function() {{
                                    alert('链接已复制！请在电脑浏览器中打开');
                                }});
                            }} else {{
                                const textArea = document.createElement('textarea');
                                textArea.value = link;
                                document.body.appendChild(textArea);
                                textArea.select();
                                try {{
                                    document.execCommand('copy');
                                    alert('链接已复制！请在电脑浏览器中打开');
                                }} catch (err) {{
                                    alert('复制失败，请手动复制链接');
                                }}
                                document.body.removeChild(textArea);
                            }}
                        }}
                    </script>
                </body>
                </html>
                """
            else:
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>授权成功</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f7fa; }}
                        .success {{ color: #67c23a; font-size: 24px; margin-bottom: 20px; }}
                        .message {{ color: #666; margin-bottom: 30px; }}
                        .debug {{ color: #999; font-size: 12px; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="success">✅ 授权成功！</div>
                    <div class="message">正在跳转回知识库页面...</div>
                    <div class="debug">跳转地址: {redirect_url}</div>
                    <script>
                        console.log('OAuth回调成功，准备跳转到: {redirect_url}');
                        try {{
                            window.location.replace('{redirect_url}');
                        }} catch (e) {{
                            console.error('跳转失败:', e);
                            window.onload = function() {{
                                try {{
                                    window.location.replace('{redirect_url}');
                                }} catch (e2) {{
                                    window.location.href = '{redirect_url}';
                                }}
                            }};
                        }}
                        setTimeout(function() {{
                            if (window.location.href.indexOf('auth_success') === -1) {{
                                console.log('备用跳转方案触发');
                                try {{
                                    window.location.replace('{redirect_url}');
                                }} catch (e) {{
                                    window.location.href = '{redirect_url}';
                                }}
                            }}
                        }}, 2000);
                    </script>
                </body>
                </html>
                """
            return HTMLResponse(content=html_content)
        except Exception as e:
            log.error(f"授权码验证失败: {e}")
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>授权失败</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f7fa; }}
                    .error {{ color: #f56c6c; font-size: 24px; margin-bottom: 20px; }}
                    .message {{ color: #666; margin-bottom: 30px; }}
                </style>
            </head>
            <body>
                <div class="error">❌ 授权失败</div>
                <div class="message">授权码验证失败: {str(e)}</div>
                <div class="message">请尝试重新授权。如果问题持续存在，请检查飞书应用配置和权限。</div>
                <script>
                    setTimeout(function() {{
                        window.location.href = '{frontend_url}/ai/knowledge-base';
                    }}, 5000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=500)
    except Exception as exc:
        log.exception("OAuth回调处理失败")
        error_msg = str(exc)
        if 'frontend_url' not in locals():
            try:
                frontend_url = settings.frontend_url or "http://localhost:3000"
            except:
                frontend_url = "http://localhost:3000"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>授权失败</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f7fa; }}
                .error {{ color: #f56c6c; font-size: 24px; margin-bottom: 20px; }}
                .message {{ color: #666; margin-bottom: 30px; }}
                .debug {{ color: #999; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="error">❌ 授权失败</div>
            <div class="message">{error_msg}</div>
            <div class="message">请尝试重新授权。如果问题持续存在，请检查飞书应用配置和权限。</div>
            <div class="debug">前端URL: {frontend_url}</div>
            <div class="debug">错误详情: {type(exc).__name__}</div>
            <script>
                setTimeout(function() {{
                    window.location.href = '{frontend_url}/ai/knowledge-base';
                }}, 5000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)


# ==================== 知识库路由 ====================

def _check_knowledge_base_available():
    """检查知识库功能是否可用"""
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )


def _get_knowledge_base_service():
    """获取知识库服务实例"""
    _check_knowledge_base_available()
    service = KnowledgeBaseService()
    _ = service.rag_engine  # 触发延迟初始化，如果缺少依赖会抛出ImportError
    return service


@router.post("/knowledge-base/sync", response_model=SyncDocumentsResponse)
def sync_documents(payload: SyncDocumentsRequest) -> SyncDocumentsResponse:
    """
    同步知识库文档到向量存储。
    
    Args:
        payload: 同步请求，包含知识库空间ID（可选）
    
    Returns:
        同步结果
    """
    try:
        service = _get_knowledge_base_service()
        
        if payload.space_id:
            result = service.sync_documents_from_space(payload.space_id, incremental=payload.incremental)
        else:
            result = service.sync_all_spaces(incremental=payload.incremental)
        
        return SyncDocumentsResponse(**result)
    except ImportError as exc:
        log.warning(f"知识库依赖未安装: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("同步知识库文档失败")
        error_msg = str(exc)
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
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: {error_msg}。请先进行飞书授权。"
            ) from exc
        raise HTTPException(status_code=500, detail=f"同步知识库文档失败: {exc}") from exc


@router.post("/knowledge-base/ask", response_model=AskQuestionResponse)
def ask_question(payload: AskQuestionRequest) -> AskQuestionResponse:
    """
    回答用户问题（基于知识库）。
    
    Args:
        payload: 问答请求，包含用户问题和可选的知识库空间ID
    
    Returns:
        答案和引用来源
    """
    try:
        service = _get_knowledge_base_service()
        result = service.ask(
            payload.question, 
            space_id=payload.space_id,
            use_web_search=payload.use_web_search
        )
        
        # 转换sources格式
        sources = []
        for s in result.get("sources", []):
            source_info = {
                "title": s["title"],
                "url": s["url"],
            }
            if s.get("source") == "web_search":
                source_info["similarity"] = 0.0
            else:
                source_info["similarity"] = s.get("similarity", 0.0)
            sources.append(source_info)
        
        return AskQuestionResponse(
            success=result["success"],
            answer=result["answer"],
            sources=sources,
            has_web_search=result.get("has_web_search", False),
            suggest_web_search=result.get("suggest_web_search", False),
            max_similarity=result.get("max_similarity"),
        )
    except ImportError as exc:
        log.warning(f"知识库依赖未安装: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("回答问题失败")
        raise HTTPException(status_code=500, detail=f"回答问题失败: {exc}") from exc


@router.get("/knowledge-base/info", response_model=CollectionInfoResponse)
def get_collection_info() -> CollectionInfoResponse:
    """
    获取向量存储集合信息。
    
    Returns:
        集合信息
    """
    try:
        service = _get_knowledge_base_service()
        result = service.get_collection_info()
        return CollectionInfoResponse(**result)
    except ImportError as exc:
        log.warning(f"知识库依赖未安装: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("获取集合信息失败")
        raise HTTPException(status_code=500, detail=f"获取集合信息失败: {exc}") from exc


@router.get("/knowledge-base/spaces", response_model=WikiSpacesResponse)
def get_wiki_spaces() -> WikiSpacesResponse:
    """
    获取所有知识库空间列表。
    
    Returns:
        知识库空间列表
    """
    try:
        service = _get_knowledge_base_service()
        result = service.get_wiki_spaces()
        return WikiSpacesResponse(**result)
    except ImportError as exc:
        log.warning(f"知识库依赖未安装: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("获取知识库空间列表失败")
        error_msg = str(exc)
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
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: {error_msg}。请先进行飞书授权。"
            ) from exc
        raise HTTPException(status_code=500, detail=f"获取知识库空间列表失败: {exc}") from exc

