# encoding: utf-8
"""FastAPI 路由定义。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from core.logger import log
from app.config import settings
from app.schemas.common import (
    AskQuestionRequest,
    AskQuestionResponse,
    CollectionInfoResponse,
    ExtractModulesRequest,
    ExtractModulesResponse,
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    HealthResponse,
    ModelInfo,
    RematchModuleRequest,
    RematchModuleResponse,
    SyncDocumentsRequest,
    SyncDocumentsResponse,
    WikiSpacesResponse,
    WordUploadResponse,
)
from app.services import AIDemoTestCaseService
from app.utils.word_parser import parse_word_document

# 知识库服务（可选，如果依赖未安装则跳过）
try:
    from app.services.knowledge_base_service import KnowledgeBaseService
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

router = APIRouter(prefix="/api/v1", tags=["ai-demo"])


def _build_service(payload: GenerateTestCasesRequest | ExtractModulesRequest | RematchModuleRequest) -> AIDemoTestCaseService:
    return AIDemoTestCaseService(
        base_url=str(payload.base_url) if payload.base_url else None,
        model=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version, name=settings.app_name)


@router.get("/models", response_model=List[ModelInfo])
def list_models() -> List[ModelInfo]:
    service = AIDemoTestCaseService()
    models = service.get_available_models()
    return [ModelInfo(**model) for model in models]


@router.post("/function-modules/extract", response_model=ExtractModulesResponse)
def extract_function_modules(payload: ExtractModulesRequest) -> ExtractModulesResponse:
    try:
        service = _build_service(payload)
        modules = service.extract_function_modules_with_content(payload.requirement_doc, trace_id=payload.task_id)
        return ExtractModulesResponse(function_points=modules, requirement_doc=payload.requirement_doc)
    except Exception as exc:  # noqa: BLE001
        log.exception("提取功能模块失败")
        raise HTTPException(status_code=500, detail=f"提取功能模块失败: {exc}") from exc


@router.post("/test-cases/generate", response_model=GenerateTestCasesResponse)
def generate_test_cases(payload: GenerateTestCasesRequest) -> GenerateTestCasesResponse:
    try:
        service = _build_service(payload)
        result = service.generate_test_cases(
            requirement_doc=payload.requirement_doc,
            limit=payload.limit,
            max_workers=payload.max_workers,
            model_name=payload.model_name,
            confirmed_function_points=payload.confirmed_function_points,
            trace_id=payload.task_id,
        )
        return GenerateTestCasesResponse(**result)
    except Exception as exc:  # noqa: BLE001
        log.exception("生成测试用例失败")
        raise HTTPException(status_code=500, detail=f"生成测试用例失败: {exc}") from exc


@router.post("/modules/rematch", response_model=RematchModuleResponse)
def rematch_module_content(payload: RematchModuleRequest) -> RematchModuleResponse:
    try:
        service = _build_service(payload)
        result = service.rematch_module_content(
            requirement_doc=payload.requirement_doc,
            module_data=payload.module_data,
            all_modules=payload.all_modules,
        )
        return RematchModuleResponse(**result)
    except Exception as exc:  # noqa: BLE001
        log.exception("模块重匹配失败")
        raise HTTPException(status_code=500, detail=f"模块重匹配失败: {exc}") from exc


@router.post("/upload/word", response_model=WordUploadResponse, tags=["upload"])
async def upload_word_document(file: UploadFile = File(...)) -> WordUploadResponse:
    """
    上传并解析 Word 文档（.docx 格式）。

    Args:
        file: 上传的 Word 文档文件

    Returns:
        WordUploadResponse: 包含解析后的文本内容和统计信息
    """
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式的 Word 文档")

    try:
        # 读取文件内容
        file_content = await file.read()

        # 验证文件大小（限制为 10MB）
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_content) > max_size:
            raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 10MB），当前文件大小: {len(file_content) / 1024 / 1024:.2f}MB")

        # 解析 Word 文档
        result = parse_word_document(file_content)

        log.info(f"成功解析 Word 文档: {file.filename}, 段落数: {result['total_paragraphs']}, 标题数: {result['total_headings']}")

        return WordUploadResponse(**result)
    except HTTPException:
        raise
    except ValueError as exc:
        log.exception(f"解析 Word 文档失败: {file.filename}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception(f"上传 Word 文档失败: {file.filename}")
        raise HTTPException(status_code=500, detail=f"上传 Word 文档失败: {exc}") from exc


# ==================== 知识库相关路由 ====================

@router.get("/feishu/oauth/authorize", tags=["feishu-oauth"])
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
        from core.engine.knowledge_base.feishu_client import FeishuAPIClient
        from fastapi import Request
        
        client = FeishuAPIClient(use_user_token=True)
        
        # 使用配置的回调地址，如果没有配置则使用当前请求的host
        redirect_uri = settings.feishu_redirect_uri
        if not redirect_uri or redirect_uri == "http://localhost:8113/api/v1/feishu/oauth/callback":
            # 如果没有配置，尝试从请求中获取
            # 注意：这需要从请求对象中获取，但这里没有request参数
            # 所以使用配置的默认值
            pass
        
        oauth_url = client.get_oauth_url(redirect_uri=redirect_uri, state=state)
        return {
            "oauth_url": oauth_url,
            "message": "请访问此URL进行授权",
            "redirect_uri": redirect_uri,  # 返回配置的回调地址，方便调试
            "tip": "如果遇到redirect_uri错误，请在飞书开放平台配置此回调地址"
        }
    except Exception as exc:
        log.exception("获取OAuth授权URL失败")
        raise HTTPException(status_code=500, detail=f"获取OAuth授权URL失败: {exc}") from exc


@router.get("/feishu/oauth/callback", tags=["feishu-oauth"])
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
        
        # 尝试从请求头推断前端URL（OAuth回调时，referer可能包含前端URL）
        referer = request.headers.get("referer", "")
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        scheme = request.url.scheme if hasattr(request.url, 'scheme') else "http"
        
        log.info(f"OAuth回调 - 配置的前端URL: {frontend_url}")
        log.info(f"OAuth回调 - Referer: {referer}")
        log.info(f"OAuth回调 - Origin: {origin}")
        log.info(f"OAuth回调 - Host: {host}")
        log.info(f"OAuth回调 - Scheme: {scheme}")
        log.info(f"OAuth回调 - 授权码: {code[:20] + '...' if code else 'None'}")
        
        # 检测是否是手机访问（通过 User-Agent）
        user_agent = request.headers.get("user-agent", "").lower()
        is_mobile = any(keyword in user_agent for keyword in ["mobile", "android", "iphone", "ipad", "ipod"])
        
        log.info(f"OAuth回调 - User-Agent: {user_agent[:100]}")
        log.info(f"OAuth回调 - 是否手机访问: {is_mobile}")
        
        # 如果配置的是默认值，尝试从请求头推断
        if not frontend_url or frontend_url == "http://localhost:3000":
            if origin:
                # 从origin提取协议和域名（最可靠）
                frontend_url = origin
                log.info(f"从Origin推断前端URL: {frontend_url}")
            elif referer:
                # 从referer提取协议和域名（可能是前端页面）
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                # 如果referer是前端页面，使用它
                if parsed.path.startswith('/ai/') or parsed.path == '/' or not parsed.path.startswith('/api/'):
                    frontend_url = f"{parsed.scheme}://{parsed.netloc}"
                    log.info(f"从Referer推断前端URL: {frontend_url}")
                else:
                    # referer是后端API，尝试从host推断前端（假设前端在3000端口）
                    if host and '8113' not in host:
                        frontend_url = f"{scheme}://{host}"
                    else:
                        # 使用默认值
                        frontend_url = settings.frontend_url
                    log.info(f"使用推断的前端URL: {frontend_url}")
            elif host:
                # 如果host不是8113端口，可能是前端
                if '8113' not in host:
                    frontend_url = f"{scheme}://{host}"
                    log.info(f"从Host推断前端URL: {frontend_url}")
                else:
                    # host是后端，使用默认前端端口
                    frontend_url = settings.frontend_url
                    log.info(f"使用默认前端URL: {frontend_url}")
            else:
                # 使用默认值
                frontend_url = settings.frontend_url
                log.info(f"使用默认前端URL: {frontend_url}")
        
        # 确保 frontend_url 格式正确（移除末尾的斜杠）
        frontend_url = frontend_url.rstrip('/')
        
        # 如果是手机访问且前端URL是localhost，说明无法直接跳转，需要特殊处理
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
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f5f7fa;
                }}
                .error {{
                    color: #f56c6c;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                .message {{
                    color: #666;
                    margin-bottom: 30px;
                }}
                .debug {{
                    color: #999;
                    font-size: 12px;
                    margin-top: 20px;
                }}
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
        html_content = """
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
                setTimeout(function() {
                    window.location.href = '""" + frontend_url + """/ai/knowledge-base';
                }, 3000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=503)
    
    try:
        from core.engine.knowledge_base.feishu_client import FeishuAPIClient
        client = FeishuAPIClient(use_user_token=True)
        client.set_user_code(code)
        
        # 尝试获取token以验证授权码是否有效
        try:
            token = client._token_manager.get_token()
            log.info(f"OAuth授权成功，token已获取。前端URL: {frontend_url}")
            
            # 构建跳转URL（确保格式正确）
            redirect_url = f"{frontend_url.rstrip('/')}/ai/knowledge-base?auth_success=true"
            log.info(f"准备跳转到: {redirect_url}")
            log.info(f"前端URL: {frontend_url}")
            log.info(f"是否手机访问: {is_mobile}")
            
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
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                            text-align: center;
                            padding: 30px 20px;
                            background: #f5f7fa;
                            max-width: 600px;
                            margin: 0 auto;
                        }}
                        .success {{
                            color: #67c23a;
                            font-size: 28px;
                            margin-bottom: 20px;
                            font-weight: bold;
                        }}
                        .message {{
                            color: #333;
                            font-size: 16px;
                            margin-bottom: 20px;
                            line-height: 1.6;
                        }}
                        .tip {{
                            color: #666;
                            font-size: 14px;
                            margin-bottom: 30px;
                            line-height: 1.6;
                            background: #fff;
                            padding: 20px;
                            border-radius: 8px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                        }}
                        .link-box {{
                            background: #fff;
                            padding: 20px;
                            border-radius: 8px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            margin-bottom: 20px;
                            word-break: break-all;
                        }}
                        .link {{
                            color: #409eff;
                            font-size: 14px;
                            text-decoration: none;
                            word-break: break-all;
                        }}
                        .copy-btn {{
                            background: #409eff;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            font-size: 14px;
                            cursor: pointer;
                            margin-top: 10px;
                        }}
                        .copy-btn:active {{
                            background: #337ecc;
                        }}
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
                                // 备用方案：选中文本
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
                # 返回HTML页面，自动跳转回前端
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>授权成功</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            text-align: center;
                            padding: 50px;
                            background: #f5f7fa;
                        }}
                        .success {{
                            color: #67c23a;
                            font-size: 24px;
                            margin-bottom: 20px;
                        }}
                        .message {{
                            color: #666;
                            margin-bottom: 30px;
                        }}
                        .debug {{
                            color: #999;
                            font-size: 12px;
                            margin-top: 20px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="success">✅ 授权成功！</div>
                    <div class="message">正在跳转回知识库页面...</div>
                    <div class="debug">跳转地址: {redirect_url}</div>
                    <script>
                        // 立即跳转，不等待window.onload
                        console.log('OAuth回调成功，准备跳转到: {redirect_url}');
                        console.log('当前URL:', window.location.href);
                        // 尝试立即跳转
                        try {{
                            // 使用 replace 而不是 href，避免在历史记录中留下回调页面
                            window.location.replace('{redirect_url}');
                        }} catch (e) {{
                            console.error('跳转失败:', e);
                            // 如果立即跳转失败，等待页面加载完成后再跳转
                            window.onload = function() {{
                                try {{
                                    window.location.replace('{redirect_url}');
                                }} catch (e2) {{
                                    window.location.href = '{redirect_url}';
                                }}
                            }};
                        }}
                        // 备用方案：2秒后强制跳转
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
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background: #f5f7fa;
                    }}
                    .error {{
                        color: #f56c6c;
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .message {{
                        color: #666;
                        margin-bottom: 30px;
                    }}
                </style>
            </head>
            <body>
                <div class="error">❌ 授权失败</div>
                <div class="message">授权码验证失败: {str(e)}</div>
                <div class="message">请尝试重新授权。如果问题持续存在，请检查飞书应用配置和权限。</div>
                <script>
                    setTimeout(function() {{
                        window.location.href = '""" + frontend_url + """/ai/knowledge-base';
                    }}, 5000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=500)
    except Exception as exc:
        log.exception("OAuth回调处理失败")
        error_msg = str(exc)
        # 确保 frontend_url 有值
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
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f5f7fa;
                }}
                .error {{
                    color: #f56c6c;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                .message {{
                    color: #666;
                    margin-bottom: 30px;
                }}
                .debug {{
                    color: #999;
                    font-size: 12px;
                    margin-top: 20px;
                }}
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


@router.post("/knowledge-base/sync", response_model=SyncDocumentsResponse, tags=["knowledge-base"])
def sync_documents(payload: SyncDocumentsRequest) -> SyncDocumentsResponse:
    """
    同步知识库文档到向量存储。
    
    Args:
        payload: 同步请求，包含知识库空间ID（可选）
    
    Returns:
        同步结果
    """
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )
    
    try:
        service = KnowledgeBaseService()
        # 尝试访问rag_engine以触发依赖检查
        _ = service.rag_engine  # 这会触发延迟初始化，如果缺少依赖会抛出ImportError
        
        if payload.space_id:
            # 同步指定空间
            result = service.sync_documents_from_space(payload.space_id, incremental=payload.incremental)
        else:
            # 同步所有空间
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
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: {error_msg}。请先进行飞书授权。"
            ) from exc
        raise HTTPException(status_code=500, detail=f"同步知识库文档失败: {exc}") from exc


@router.post("/knowledge-base/ask", response_model=AskQuestionResponse, tags=["knowledge-base"])
def ask_question(payload: AskQuestionRequest) -> AskQuestionResponse:
    """
    回答用户问题（基于知识库）。
    
    Args:
        payload: 问答请求，包含用户问题和可选的知识库空间ID
    
    Returns:
        答案和引用来源
    """
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )
    
    try:
        service = KnowledgeBaseService()
        # 尝试访问rag_engine以触发依赖检查
        _ = service.rag_engine  # 这会触发延迟初始化，如果缺少依赖会抛出ImportError
        result = service.ask(
            payload.question, 
            space_id=payload.space_id,
            use_web_search=payload.use_web_search
        )
        
        # 转换sources格式（过滤掉网络搜索来源的similarity，因为网络搜索没有相似度）
        sources = []
        for s in result.get("sources", []):
            source_info = {
                "title": s["title"],
                "url": s["url"],
            }
            # 如果是网络搜索来源，similarity为0；否则使用实际相似度
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


@router.get("/knowledge-base/info", response_model=CollectionInfoResponse, tags=["knowledge-base"])
def get_collection_info() -> CollectionInfoResponse:
    """
    获取向量存储集合信息。
    
    Returns:
        集合信息
    """
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )
    
    try:
        service = KnowledgeBaseService()
        # 尝试访问rag_engine以触发依赖检查
        _ = service.rag_engine  # 这会触发延迟初始化，如果缺少依赖会抛出ImportError
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


@router.get("/knowledge-base/spaces", response_model=WikiSpacesResponse, tags=["knowledge-base"])
def get_wiki_spaces() -> WikiSpacesResponse:
    """
    获取所有知识库空间列表。
    
    Returns:
        知识库空间列表
    """
    if not KNOWLEDGE_BASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="知识库功能不可用，请安装依赖: pip install sentence-transformers chromadb"
        )
    
    try:
        service = KnowledgeBaseService()
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
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: {error_msg}。请先进行飞书授权。"
            ) from exc
        raise HTTPException(status_code=500, detail=f"获取知识库空间列表失败: {exc}") from exc
