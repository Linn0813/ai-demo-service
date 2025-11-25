# encoding: utf-8
"""
飞书API客户端，用于调用飞书开放平台API。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.engine.base.config import LLM_CONFIG
from core.logger import log
try:
    from app.config import settings
except ImportError:
    # 如果无法导入settings，使用默认值
    import os
    class Settings:
        feishu_redirect_uri = os.getenv("FEISHU_REDIRECT_URI", "http://localhost:8113/api/v1/feishu/oauth/callback")
    settings = Settings()


# Token持久化文件路径
_TOKEN_FILE = Path(__file__).parent.parent.parent.parent.parent / "data" / "feishu_tokens.json"


def _ensure_token_dir() -> None:
    """确保token文件目录存在。"""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_tokens_from_file() -> Dict[str, Dict[str, Any]]:
    """从文件加载token缓存。"""
    if not _TOKEN_FILE.exists():
        return {}
    
    try:
        with open(_TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            log.debug(f"从文件加载token缓存: {_TOKEN_FILE}")
            return data
    except Exception as e:
        log.warning(f"加载token文件失败: {e}，将使用空缓存")
        return {}


def _save_tokens_to_file(cache: Dict[str, Dict[str, Any]]) -> None:
    """将token缓存保存到文件。"""
    try:
        _ensure_token_dir()
        with open(_TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        log.debug(f"保存token缓存到文件: {_TOKEN_FILE}")
    except Exception as e:
        log.warning(f"保存token文件失败: {e}")


# 全局token存储，用于在多个FeishuTokenManager实例之间共享token
# 键格式：f"{app_id}:{use_user_token}"
# 启动时从文件加载
_global_token_cache: Dict[str, Dict[str, Any]] = _load_tokens_from_file()


def _get_cache_key(app_id: str, use_user_token: bool) -> str:
    """获取缓存键。"""
    return f"{app_id}:{use_user_token}"


def _get_cached_token(app_id: str, use_user_token: bool) -> Optional[str]:
    """从全局缓存获取token。"""
    cache_key = _get_cache_key(app_id, use_user_token)
    cache = _global_token_cache.get(cache_key)
    if cache:
        token = cache.get("token")
        expire_time = cache.get("expire_time", 0)
        if token and time.time() < expire_time - 60:  # 提前60秒刷新
            return token
    return None


def _set_cached_token(app_id: str, use_user_token: bool, token: str, expire_time: float) -> None:
    """将token保存到全局缓存并持久化到文件。"""
    cache_key = _get_cache_key(app_id, use_user_token)
    _global_token_cache[cache_key] = {
        "token": token,
        "expire_time": expire_time,
    }
    # 持久化到文件
    _save_tokens_to_file(_global_token_cache)


def _get_cached_user_code(app_id: str) -> Optional[str]:
    """从全局缓存获取授权码。"""
    cache_key = _get_cache_key(app_id, True)  # user_token的缓存键
    cache = _global_token_cache.get(cache_key)
    if cache:
        return cache.get("user_code")
    return None


def _set_cached_user_code(app_id: str, code: str) -> None:
    """将授权码保存到全局缓存并持久化到文件。"""
    cache_key = _get_cache_key(app_id, True)  # user_token的缓存键
    if cache_key not in _global_token_cache:
        _global_token_cache[cache_key] = {}
    _global_token_cache[cache_key]["user_code"] = code
    # 持久化到文件
    _save_tokens_to_file(_global_token_cache)


class FeishuTokenManager:
    """飞书访问令牌管理器，自动刷新Token。"""

    def __init__(self, app_id: str, app_secret: str, use_user_token: bool = False):
        """
        初始化Token管理器。

        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            use_user_token: 是否使用用户访问令牌（user_access_token）
                           True: 使用user_access_token（适用于用户身份权限）
                           False: 使用tenant_access_token（适用于应用身份权限）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.use_user_token = use_user_token
        self._token: Optional[str] = None
        self._token_expire_time: float = 0.0
        self._api_base_url = settings.feishu_api_base_url
        self._user_code: Optional[str] = None  # OAuth授权码
        
        # 尝试从全局缓存加载token和授权码
        cached_token = _get_cached_token(app_id, use_user_token)
        if cached_token:
            self._token = cached_token
            cache = _global_token_cache.get(_get_cache_key(app_id, use_user_token))
            if cache:
                self._token_expire_time = cache.get("expire_time", 0)
        
        if use_user_token:
            cached_code = _get_cached_user_code(app_id)
            if cached_code:
                self._user_code = cached_code

    def get_token(self) -> str:
        """
        获取访问令牌，如果过期则自动刷新。

        Returns:
            访问令牌字符串
        """
        # 先尝试从全局缓存获取
        cached_token = _get_cached_token(self.app_id, self.use_user_token)
        if cached_token:
            self._token = cached_token
            cache = _global_token_cache.get(_get_cache_key(self.app_id, self.use_user_token))
            if cache:
                self._token_expire_time = cache.get("expire_time", 0)
        
        # 如果Token未过期，直接返回
        if self._token and time.time() < self._token_expire_time - 60:  # 提前60秒刷新
            return self._token

        # 刷新Token
        token = self._refresh_token(self.use_user_token)
        
        # 保存到全局缓存
        _set_cached_token(self.app_id, self.use_user_token, token, self._token_expire_time)
        
        return token
    
    def set_user_code(self, code: str) -> None:
        """
        设置OAuth授权码（用于获取user_access_token）。

        Args:
            code: OAuth授权码
        """
        self._user_code = code
        # 保存到全局缓存
        _set_cached_user_code(self.app_id, code)
        # 清除现有token，强制刷新
        self._token = None
        self._token_expire_time = 0.0
    
    def get_oauth_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        获取OAuth授权URL（用于用户身份权限）。

        Args:
            redirect_uri: 重定向URI
            state: 状态参数（可选，用于防止CSRF攻击）

        Returns:
            OAuth授权URL
        """
        from urllib.parse import urlencode
        
        params = {
            "app_id": self.app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            # OAuth权限范围（必须与飞书开放平台中配置的权限一致）
            # 根据你的配置，已开通的权限：
            # - wiki:wiki:readonly - 知识库只读权限（搜索、获取节点列表）✅
            # - docs:document.content:read - 文档内容读取权限（docs API）✅
            # - docx:document:readonly - docx文档只读权限（docx API）✅
            # 
            # 注意：
            # 1. drive:drive:doc:readonly 权限无效（错误码20043），已移除
            # 2. 当前使用已配置的权限，包括docx权限以支持docx文档内容获取
            "scope": "wiki:wiki:readonly docs:document.content:read docx:document:readonly",
        }
        if state:
            params["state"] = state
        
        return f"https://open.feishu.cn/open-apis/authen/v1/authorize?{urlencode(params)}"

    def _refresh_token(self, use_user_token: bool = False) -> str:
        """
        刷新访问令牌。

        Args:
            use_user_token: 是否使用用户访问令牌（user_access_token）
                           True: 使用user_access_token（适用于用户身份权限）
                           False: 使用tenant_access_token（适用于应用身份权限）

        Returns:
            新的访问令牌

        Raises:
            ConnectionError: 无法连接到飞书API
            RuntimeError: 获取Token失败
        """
        if use_user_token:
            # 用户访问令牌（用户身份）
            if not self._user_code:
                raise RuntimeError(
                    "需要OAuth授权码才能获取user_access_token。"
                    "请先调用get_oauth_url()获取授权URL，用户授权后获取code，"
                    "然后调用set_user_code(code)设置授权码。"
                )
            
            # 飞书OAuth换取user_access_token的API
            # 参考：https://open.feishu.cn/document/uAjLw4CM/ukzM4UjL5MDN14yM5QjN
            # 注意：换取token时需要先获取tenant_access_token，然后使用它来换取user_access_token
            # 或者使用app_access_token（需要先获取）
            
            # 先获取tenant_access_token（用于后续API调用）
            tenant_token_manager = FeishuTokenManager(self.app_id, self.app_secret, use_user_token=False)
            tenant_access_token = tenant_token_manager.get_token()
            
            url = f"{self._api_base_url}/authen/v1/oidc/access_token"
            redirect_uri = settings.feishu_redirect_uri
            payload = {
                "grant_type": "authorization_code",
                "code": self._user_code,
                "redirect_uri": redirect_uri,  # 必须与授权时使用的redirect_uri一致
            }

            try:
                log.debug("正在刷新飞书访问令牌（用户身份）...")
                log.debug(f"使用授权码: {self._user_code[:10]}...")
                log.debug(f"使用redirect_uri: {redirect_uri}")
                
                # 用户访问令牌需要使用tenant_access_token作为Authorization
                headers = {
                    "Authorization": f"Bearer {tenant_access_token}",
                    "Content-Type": "application/json",
                }
                
                log.debug(f"请求URL: {url}")
                log.debug(f"请求体: {payload}")
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                # 记录响应状态
                log.debug(f"响应状态码: {response.status_code}")
                
                if not response.ok:
                    try:
                        error_body = response.json()
                        error_code = error_body.get("code")
                        # 对于预期的权限错误，降级为DEBUG日志
                        if error_code in (404, 99991679, 99991664):
                            log.debug(f"飞书API错误响应（权限限制）: code={error_code}")
                        else:
                            log.error(f"飞书API错误响应: {error_body}")
                    except ValueError:
                        # 对于404错误，静默处理
                        if response.status_code != 404:
                            log.error(f"飞书API错误响应（非JSON）: {response.text[:500]}")
                        else:
                            log.debug(f"飞书API错误响应（非JSON）: 404 page not found")
                
                response.raise_for_status()
                result = response.json()

                log.debug(f"飞书API响应: {result}")

                if result.get("code") == 0:
                    data = result.get("data", {})
                    self._token = data.get("access_token")
                    expire = data.get("expires_in", 7200)  # 默认2小时
                    self._token_expire_time = time.time() + expire
                    
                    # 保存到全局缓存
                    _set_cached_token(self.app_id, True, self._token, self._token_expire_time)

                    log.info(f"飞书访问令牌刷新成功（用户身份），有效期: {expire}秒")
                    return self._token
                else:
                    error_code = result.get("code")
                    error_msg = result.get("msg", "未知错误")
                    error_detail = f"获取用户Token失败: {error_msg} (code: {error_code})"
                    log.error(error_detail)
                    log.error(f"完整错误响应: {result}")
                    
                    # 错误码20014可能是授权码已使用或无效
                    if error_code == 20014:
                        raise RuntimeError(
                            f"{error_detail}\n"
                            "可能原因：\n"
                            "1. 授权码已使用过（授权码只能使用一次）\n"
                            "2. 授权码已过期（通常10分钟）\n"
                            "3. 授权码无效\n"
                            "4. redirect_uri不匹配（已添加redirect_uri参数）\n"
                            "请重新进行OAuth授权流程。"
                        )
                    raise RuntimeError(error_detail)

            except requests.exceptions.RequestException as e:
                error_msg = f"无法连接到飞书API: {e}"
                log.error(error_msg)
                raise ConnectionError(error_msg) from e
        else:
            # 租户访问令牌（应用身份）
            url = f"{self._api_base_url}/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            }

            try:
                log.debug("正在刷新飞书访问令牌（应用身份）...")
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()

                result = response.json()

                if result.get("code") == 0:
                    self._token = result.get("tenant_access_token")
                    expire = result.get("expire", 7200)  # 默认2小时
                    self._token_expire_time = time.time() + expire
                    
                    # 保存到全局缓存
                    _set_cached_token(self.app_id, False, self._token, self._token_expire_time)

                    log.info(f"飞书访问令牌刷新成功（应用身份），有效期: {expire}秒")
                    return self._token
                else:
                    error_msg = f"获取Token失败: {result.get('msg')} (code: {result.get('code')})"
                    log.error(error_msg)
                    raise RuntimeError(error_msg)

            except requests.exceptions.RequestException as e:
                error_msg = f"无法连接到飞书API: {e}"
                log.error(error_msg)
                raise ConnectionError(error_msg) from e


# 权限到API端点的映射表
# 格式: {权限名称: [API端点列表，按优先级排序]}
PERMISSION_API_MAPPING = {
    # 文档内容相关权限
    "docs:document.content:read": [
        {"endpoint": "docs/v1/documents/{token}/content", "method": "GET", "name": "docs_content"},
        {"endpoint": "docx/v1/documents/{token}/content", "method": "GET", "name": "docx_content"},
    ],
    "docx:document:readonly": [
        {"endpoint": "docx/v1/documents/{token}/content", "method": "GET", "name": "docx_content"},
        {"endpoint": "docs/v1/documents/{token}/content", "method": "GET", "name": "docs_content"},
    ],
    "docx:document": [
        {"endpoint": "docx/v1/documents/{token}/content", "method": "GET", "name": "docx_content"},
        {"endpoint": "docs/v1/documents/{token}/content", "method": "GET", "name": "docs_content"},
    ],
    # 文档元信息相关权限
    "docs:document.meta:read": [
        {"endpoint": "docs/v1/documents/{token}", "method": "GET", "name": "docs_meta"},
        {"endpoint": "docx/v1/documents/{token}", "method": "GET", "name": "docx_meta"},
    ],
    "docx:document:readonly": [  # 这个权限也包含元信息读取
        {"endpoint": "docx/v1/documents/{token}", "method": "GET", "name": "docx_meta"},
        {"endpoint": "docs/v1/documents/{token}", "method": "GET", "name": "docs_meta"},
    ],
    "docx:document": [  # 这个权限也包含元信息读取
        {"endpoint": "docx/v1/documents/{token}", "method": "GET", "name": "docx_meta"},
        {"endpoint": "docs/v1/documents/{token}", "method": "GET", "name": "docs_meta"},
    ],
}


class FeishuAPIClient:
    """飞书API客户端，封装常用API调用。"""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        use_user_token: Optional[bool] = None,
    ):
        """
        初始化飞书API客户端。

        Args:
            app_id: 飞书应用ID，如果不提供则从配置读取
            app_secret: 飞书应用密钥，如果不提供则从配置读取
            use_user_token: 是否使用用户访问令牌，如果不提供则从配置读取
        """
        self.app_id = app_id or settings.feishu_app_id
        self.app_secret = app_secret or settings.feishu_app_secret
        self.use_user_token = use_user_token if use_user_token is not None else settings.feishu_use_user_token

        if not self.app_id or not self.app_secret:
            raise ValueError("飞书应用凭证未配置，请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")

        self._token_manager = FeishuTokenManager(self.app_id, self.app_secret, self.use_user_token)
        self._api_base_url = settings.feishu_api_base_url
        # 缓存已检测的权限（避免重复检测）
        self._detected_permissions: Optional[Dict[str, List[str]]] = None
    
    def set_user_code(self, code: str) -> None:
        """
        设置OAuth授权码（用于获取user_access_token）。

        Args:
            code: OAuth授权码
        """
        self._token_manager.set_user_code(code)
    
    def get_oauth_url(self, redirect_uri: Optional[str] = None, state: Optional[str] = None) -> str:
        """
        获取OAuth授权URL（用于用户身份权限）。

        Args:
            redirect_uri: 重定向URI，如果不提供则使用配置中的默认值
            state: 状态参数（可选，用于防止CSRF攻击）

        Returns:
            OAuth授权URL
        """
        redirect_uri = redirect_uri or settings.feishu_redirect_uri
        return self._token_manager.get_oauth_url(redirect_uri, state)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        发送API请求。

        Args:
            method: HTTP方法（GET、POST等）
            endpoint: API端点（相对路径）
            params: URL参数
            json_data: JSON请求体
            timeout: 超时时间（秒）

        Returns:
            API响应数据

        Raises:
            ConnectionError: 网络连接错误
            RuntimeError: API调用失败
        """
        url = f"{self._api_base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._token_manager.get_token()}",
            "Content-Type": "application/json",
        }

        try:
            log.debug(f"调用飞书API: {method} {endpoint}")
            log.debug(f"请求URL: {url}")
            if params:
                log.debug(f"请求参数: {params}")
            if json_data:
                log.debug(f"请求体: {json_data}")

            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, params=params, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            # 记录响应状态
            log.debug(f"响应状态码: {response.status_code}")

            # 如果状态码不是2xx，记录详细错误信息
            if not response.ok:
                try:
                    error_body = response.json()
                    error_code = error_body.get("code")
                    error_msg = error_body.get("msg", "未知错误")
                    
                    # 对于404错误，记录完整的错误信息以便调试
                    if response.status_code == 404:
                        log.warning(f"飞书API 404错误: {endpoint}")
                        log.warning(f"   错误码: {error_code}")
                        log.warning(f"   错误消息: {error_msg}")
                        log.warning(f"   完整错误响应: {json.dumps(error_body, indent=2, ensure_ascii=False)}")
                    
                    # 对于预期的权限错误，降级为DEBUG日志
                    if error_code in (404, 99991679, 99991664):
                        log.debug(f"飞书API错误响应（权限限制）: code={error_code}")
                    else:
                        log.error(f"飞书API错误响应: {error_body}")
                except ValueError:
                    # 对于404错误，尝试解析响应文本
                    if response.status_code == 404:
                        log.warning(f"飞书API 404错误: {endpoint}")
                        log.warning(f"   响应内容: {response.text[:500]}")
                        # 尝试解析响应头中的错误信息
                        if response.headers.get('Content-Type', '').startswith('application/json'):
                            try:
                                error_body = response.json()
                                log.warning(f"   错误响应: {json.dumps(error_body, indent=2, ensure_ascii=False)}")
                            except:
                                pass
                    elif response.status_code != 404:
                        log.error(f"飞书API错误响应（非JSON）: {response.text[:500]}")
                    
                    # 400错误可能是参数问题或token类型问题
                    if response.status_code == 400:
                            log.error(
                                f"⚠️  400错误可能原因：\n"
                                f"1. API参数格式不正确\n"
                                f"2. 权限类型不匹配（当前使用tenant_access_token，但权限类型是'用户身份'）\n"
                                f"3. API端点或参数名称不正确\n"
                                f"错误详情: {error_msg} (code: {error_code})"
                            )
                except ValueError:
                    # 对于404错误，静默处理
                    if response.status_code != 404:
                        log.error(f"飞书API错误响应（非JSON）: {response.text[:500]}")
                    else:
                        log.debug(f"飞书API错误响应（非JSON）: 404 page not found")

            response.raise_for_status()

            # 尝试解析JSON响应
            try:
                result = response.json()
            except ValueError:
                # 如果不是JSON，返回文本内容
                log.warning(f"飞书API返回非JSON响应: {response.text[:200]}")
                return {"text": response.text}

            # 检查业务错误码
            if result.get("code") != 0:
                error_code = result.get("code")
                error_msg = result.get("msg", "未知错误")
                
                # 对于预期的权限错误（404, 99991679等），降级为DEBUG日志
                if error_code in (404, 99991679, 99991664):
                    log.debug(f"飞书API返回业务错误（权限限制）: {error_msg} (code: {error_code})")
                else:
                    # 其他错误才记录ERROR
                    log.error(f"飞书API返回业务错误: {error_msg} (code: {error_code})")
                    log.debug(f"完整错误响应: {result}")
                
                # 常见错误码处理
                if error_code == 99991663:
                    raise RuntimeError(
                        f"权限错误: {error_msg} (code: {error_code})\n"
                        f"提示：如果权限类型是'用户身份'，需要使用user_access_token而不是tenant_access_token"
                    )
                elif error_code == 99991664:
                    raise RuntimeError(f"资源不存在或无权访问: {error_msg} (code: {error_code})")
                elif error_code == 1254000:
                    raise RuntimeError(
                        f"请求参数错误: {error_msg} (code: {error_code})\n"
                        f"请检查API参数是否正确，或确认权限类型是否匹配"
                    )

            return result

        except requests.exceptions.HTTPError as e:
            # HTTP错误（如400, 401, 403等）
            error_msg = f"飞书API HTTP错误: {method} {endpoint}, 状态码: {e.response.status_code}"
            
            # 检查是否是频率限制错误（400状态码 + 99991400错误码）
            if e.response.status_code == 400:
                try:
                    error_body = e.response.json()
                    error_code = error_body.get("code")
                    if error_code == 99991400:
                        # 频率限制错误，抛出特殊异常以便重试机制处理
                        raise RuntimeError(
                            f"飞书API频率限制: {error_body.get('msg', 'request trigger frequency limit')} "
                            f"(code: {error_code})"
                        ) from e
                    elif error_code in (404, 99991679, 99991664):
                        # 权限或404错误，静默处理（不输出ERROR日志）
                        log.debug(f"飞书API HTTP错误（权限限制）: {method} {endpoint}, 状态码: {e.response.status_code}")
                        raise ConnectionError(error_msg) from e
                except (ValueError, KeyError):
                    pass
            
            # 对于404和权限相关错误，降级为DEBUG日志
            if e.response.status_code in (404, 400):
                log.debug(f"飞书API HTTP错误: {method} {endpoint}, 状态码: {e.response.status_code}")
            else:
                log.error(error_msg)
            
            try:
                error_body = e.response.json()
                if e.response.status_code not in (404, 400):
                    log.error(f"错误详情: {error_body}")
            except ValueError:
                if e.response.status_code not in (404, 400):
                    log.error(f"错误响应（非JSON）: {e.response.text[:500]}")
            
            raise ConnectionError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"飞书API请求失败: {method} {endpoint}, 错误: {e}"
            log.error(error_msg)
            raise ConnectionError(error_msg) from e

    def search_wiki_spaces(
        self, query: str = "", limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """
        获取知识空间列表。

        Args:
            query: 搜索关键词（暂未使用，飞书API可能不支持搜索参数）
            limit: 返回数量限制（最大50）
            offset: 偏移量（使用page_token进行分页）

        Returns:
            知识空间列表响应
        """
        # 飞书知识空间API：获取知识空间列表
        # 参考：https://open.feishu.cn/document/server-docs/docs/wiki-v2/space/list
        # 注意：如果权限类型是"用户身份"，可能需要使用POST方法或不同的参数格式
        
        # 先尝试GET方法（标准RESTful方式）
        endpoint = "wiki/v2/spaces"
        params = {
            "page_size": min(limit, 50),  # 飞书API限制最大50
        }
        
        try:
            return self._request("GET", endpoint, params=params)
        except ConnectionError as e:
            # 如果GET方法失败（如400错误），尝试POST方法
            if "400" in str(e) or "Bad Request" in str(e):
                log.warning("GET方法失败，尝试使用POST方法...")
                endpoint = "wiki/v2/spaces/list"
                payload = {
                    "page_size": min(limit, 50),
                }
                try:
                    return self._request("POST", endpoint, json_data=payload)
                except Exception:
                    # 如果POST也失败，重新抛出原始错误
                    raise e
            else:
                raise

    def get_wiki_nodes(self, space_id: str, parent_node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取知识空间子节点列表。

        Args:
            space_id: 知识空间ID
            parent_node_id: 父节点ID（可选，不提供则获取根节点）

        Returns:
            节点列表响应
        """
        # 飞书知识空间API：获取知识空间子节点列表
        # 参考：https://open.feishu.cn/document/server-docs/docs/wiki-v2/space-node/list
        endpoint = f"wiki/v2/spaces/{space_id}/nodes"
        params = {}
        if parent_node_id:
            params["parent_node_id"] = parent_node_id
        
        # 尝试GET方法
        try:
            return self._request("GET", endpoint, params=params)
        except Exception:
            # 如果GET失败，尝试POST方法（某些版本可能使用POST）
            endpoint = "wiki/v2/spaces/get_node"
            payload = {
                "space_id": space_id,
            }
            if parent_node_id:
                payload["parent_node_id"] = parent_node_id
            return self._request("POST", endpoint, json_data=payload)

    def search_wiki_nodes(
        self,
        space_id: str,
        query: str = "",
        limit: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        搜索知识库节点（文档）。

        Args:
            space_id: 知识空间ID
            query: 搜索关键词
            limit: 返回数量限制（最大50）
            page_token: 分页token（可选）

        Returns:
            搜索结果响应，包含匹配的节点列表
        """
        import time
        
        # 飞书知识库搜索API：搜索知识库节点
        # 参考：https://open.feishu.cn/document/server-docs/docs/wiki-v2/node/search
        endpoint = "wiki/v2/nodes/search"
        payload = {
            "space_id": space_id,
            "query": query,
            "limit": min(limit, 50),  # 飞书API限制最大50
        }
        if page_token:
            payload["page_token"] = page_token
        
        # 添加频率限制处理：重试机制
        max_retries = 3
        retry_delay = 1  # 初始延迟1秒
        
        for attempt in range(max_retries):
            try:
                result = self._request("POST", endpoint, json_data=payload)
                
                # 检查是否是频率限制错误
                if result.get("code") == 99991400:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # 指数退避：1s, 2s, 4s
                        log.warning(f"触发频率限制，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        log.error("达到最大重试次数，频率限制错误")
                        raise RuntimeError(
                            f"飞书API频率限制: {result.get('msg', 'request trigger frequency limit')}\n"
                            f"建议：减少搜索请求频率，或等待一段时间后重试"
                        )
                
                return result
            except RuntimeError as e:
                # 检查是否是频率限制相关的错误
                error_str = str(e)
                if "99991400" in error_str or "frequency limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        log.warning(f"触发频率限制，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                raise
        
        # 如果所有重试都失败
        raise RuntimeError("搜索知识库节点失败：达到最大重试次数")
    
    def get_wiki_node_content(self, node_token: str) -> Dict[str, Any]:
        """
        获取知识库节点（文档）内容。
        
        注意：知识库中的文档需要使用wiki API，而不是docs/docx API。
        
        Args:
            node_token: 知识库节点token（obj_token）
            
        Returns:
            节点内容响应
        """
        # 飞书知识库节点内容API
        # 参考：https://open.feishu.cn/document/server-docs/docs/wiki-v2/node/get
        # 注意：wiki API需要使用node_id（数字ID），而不是node_token（字符串token）
        # 如果传入的是node_token，可能需要先转换为node_id
        endpoint = f"wiki/v2/nodes/{node_token}"
        
        try:
            return self._request("GET", endpoint)
        except Exception as e:
            # 静默处理wiki API失败，不输出WARNING日志（这些错误是预期的）
            error_str = str(e)
            if "404" in error_str or "99991679" in error_str:
                # 权限或404错误，静默处理
                pass
            else:
                log.debug(f"wiki API获取失败: {type(e).__name__}，尝试其他方法...")
            # 如果wiki API失败，尝试使用docs/docx API（向后兼容）
            raise

    def _detect_available_permissions(self, document_token: str, is_wiki_node: bool = False) -> Dict[str, List[str]]:
        """
        检测用户可用的权限（通过实际API调用测试）。
        
        Args:
            document_token: 用于测试的文档token
            is_wiki_node: 是否为知识库节点，如果是则优先测试wiki API
            
        Returns:
            权限到可用API的映射，格式: {"content": ["wiki_content", "docs_content", "docx_content"], "meta": ["wiki_meta", "docs_meta", "docx_meta"]}
        """
        # 移除缓存机制，每次都重新检测（因为不同的token可能需要不同的API）
        # 这样可以避免第一次检测失败后，后续所有调用都返回空列表
        
        detected = {
            "content": [],
            "meta": [],
        }
        
        # 如果是wiki节点，优先测试wiki API
        # 注意：wiki API需要使用node_id，而不是obj_token
        # 如果传入的是obj_token，wiki API可能会失败，这是正常的，不应该影响其他API的测试
        if is_wiki_node:
            try:
                log.debug(f"测试wiki API权限: wiki/v2/nodes/{document_token[:30]}...")
                wiki_result = self.get_wiki_node_content(document_token)
                if wiki_result.get("code") == 0:
                    detected["content"].append("wiki_content")
                    detected["meta"].append("wiki_meta")
                    log.info(f"✅ 检测到可用权限: wiki_content (content), wiki_meta (meta)")
                    # wiki API可用，但继续测试其他API（因为可能还需要获取文档的实际内容）
                else:
                    error_code = wiki_result.get("code")
                    log.debug(f"❌ wiki API权限不足: code={error_code}（可能因为使用的是obj_token而不是node_id）")
            except Exception as e:
                error_str = str(e)
                if "404" in error_str or "99991679" in error_str:
                    log.debug(f"❌ wiki API权限不足或404（可能因为使用的是obj_token而不是node_id，这是正常的）")
                else:
                    log.debug(f"⚠️  wiki API测试异常: {type(e).__name__}")
        
        # 测试文档内容API
        content_apis = [
            ("docs/v1/documents/{token}/content", "docs_content"),
            ("docx/v1/documents/{token}/content", "docx_content"),
        ]
        
        for api_endpoint, api_name in content_apis:
            try:
                endpoint = api_endpoint.format(token=document_token)
                # 使用临时请求方法，避免抛出异常
                url = f"{self._api_base_url}/{endpoint.lstrip('/')}"
                headers = {
                    "Authorization": f"Bearer {self._token_manager.get_token()}",
                    "Content-Type": "application/json",
                }
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.ok:
                    try:
                        result = response.json()
                        if result.get("code") == 0:
                            detected["content"].append(api_name)
                            log.info(f"✅ 检测到可用权限: {api_name} (content)")
                            continue
                    except ValueError:
                        pass
                
                # 检查错误码
                try:
                    error_body = response.json()
                    error_code = error_body.get("code")
                    if error_code == 99991679:
                        log.debug(f"❌ 权限不足: {api_name} (content)")
                    else:
                        log.debug(f"⚠️  API调用失败: {api_name} (content), code: {error_code}")
                except ValueError:
                    log.debug(f"⚠️  API调用失败: {api_name} (content), 状态码: {response.status_code}")
            except Exception as e:
                log.debug(f"⚠️  权限检测异常: {api_name} (content), 错误: {e}")
        
        # 测试文档元信息API
        meta_apis = [
            ("docs/v1/documents/{token}", "docs_meta"),
            ("docx/v1/documents/{token}", "docx_meta"),
        ]
        
        for api_endpoint, api_name in meta_apis:
            try:
                endpoint = api_endpoint.format(token=document_token)
                url = f"{self._api_base_url}/{endpoint.lstrip('/')}"
                headers = {
                    "Authorization": f"Bearer {self._token_manager.get_token()}",
                    "Content-Type": "application/json",
                }
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.ok:
                    try:
                        result = response.json()
                        if result.get("code") == 0:
                            detected["meta"].append(api_name)
                            log.info(f"✅ 检测到可用权限: {api_name} (meta)")
                            continue
                    except ValueError:
                        pass
                
                # 检查错误码
                try:
                    error_body = response.json()
                    error_code = error_body.get("code")
                    if error_code == 99991679:
                        log.debug(f"❌ 权限不足: {api_name} (meta)")
                    else:
                        log.debug(f"⚠️  API调用失败: {api_name} (meta), code: {error_code}")
                except ValueError:
                    log.debug(f"⚠️  API调用失败: {api_name} (meta), 状态码: {response.status_code}")
            except Exception as e:
                log.debug(f"⚠️  权限检测异常: {api_name} (meta), 错误: {e}")
        
        # 不再缓存检测结果，因为不同的token可能需要不同的API
        # self._detected_permissions = detected
        log.info(f"权限检测完成: content={detected['content']}, meta={detected['meta']}")
        return detected
    
    def _get_best_api_endpoint(self, document_token: str, api_type: str, is_wiki_node: bool = False) -> Optional[str]:
        """
        根据检测到的权限选择最佳的API端点。
        
        Args:
            document_token: 文档token
            api_type: API类型，"content"或"meta"
            is_wiki_node: 是否为知识库节点
            
        Returns:
            最佳API端点路径，如果都不可用则返回None
        """
        detected = self._detect_available_permissions(document_token, is_wiki_node=is_wiki_node)
        available_apis = detected.get(api_type, [])
        
        if not available_apis:
            return None
        
        # 优先使用第一个可用的API
        api_name = available_apis[0]
        
        # 根据API名称返回对应的端点
        endpoint_map = {
            "wiki_content": f"wiki/v2/nodes/{document_token}",
            "wiki_meta": f"wiki/v2/nodes/{document_token}",
            "docs_content": f"docs/v1/documents/{document_token}/content",
            "docx_content": f"docx/v1/documents/{document_token}/content",
            "docs_meta": f"docs/v1/documents/{document_token}",
            "docx_meta": f"docx/v1/documents/{document_token}",
        }
        
        return endpoint_map.get(api_name)

    def get_document_content(self, document_token: str, is_wiki_node: bool = False) -> Dict[str, Any]:
        """
        获取文档内容（根据权限自动选择API端点）。

        Args:
            document_token: 文档token（可能是node_id、node_token或obj_token）
            is_wiki_node: 是否为知识库节点（wiki node），如果是则优先使用wiki API

        Returns:
            文档内容
        """
        # 如果是知识库节点，优先尝试wiki API
        # 注意：wiki API需要使用node_id或node_token，而不是obj_token
        if is_wiki_node:
            try:
                log.info(f"📋 尝试使用wiki API获取知识库节点内容: {document_token[:30]}...")
                result = self.get_wiki_node_content(document_token)
                if result.get("code") == 0:
                    log.info(f"✅ 使用wiki API获取节点内容成功")
                    return result
                else:
                    # wiki API失败，记录错误码但不抛出异常，继续尝试其他API
                    error_code = result.get("code")
                    error_msg = result.get("msg", "")
                    log.warning(f"⚠️ wiki API返回错误: {error_msg} (code: {error_code})，尝试其他API...")
            except Exception as e:
                error_str = str(e)
                if "404" in error_str or "99991679" in error_str:
                    log.warning(f"⚠️ wiki API权限不足或404（可能因为使用的是obj_token而不是node_id）: {str(e)[:200]}，尝试其他API...")
                else:
                    log.warning(f"⚠️ wiki API获取失败: {str(e)[:200]}，尝试docs/docx API...")
        
        # 不再依赖权限检测（因为权限检测可能失败），直接尝试所有可能的API
        # 按优先级尝试所有可能的API（静默失败，不输出大量错误日志）
        # 注意：知识库中的docx文档需要使用 raw_content 端点，而不是 content 端点
        fallback_apis = [
            f"docx/v1/documents/{document_token}/raw_content",  # docx文档的原始内容API（知识库文档使用）
            f"docs/v1/documents/{document_token}/content",      # docs文档的内容API
            f"docx/v1/documents/{document_token}/content",      # docx文档的内容API（普通文档使用）
        ]
        
        last_error = None
        last_error_code = None
        for endpoint in fallback_apis:
            try:
                log.info(f"📋 尝试API端点: {endpoint}")
                result = self._request("GET", endpoint)
                if result.get("code") == 0:
                    log.info(f"✅ 使用API端点成功: {endpoint}")
                    return result
                else:
                    # 记录业务错误码
                    last_error_code = result.get("code")
                    error_msg = result.get("msg", "")
                    last_error = RuntimeError(f"API返回错误: {error_msg} (code: {last_error_code})")
                    log.warning(f"⚠️ API端点失败 ({endpoint}): code={last_error_code}, msg={error_msg}")
            except ConnectionError as e:
                # HTTP错误（如404）
                last_error = e
                error_str = str(e)
                if "404" in error_str:
                    last_error_code = 404
                    log.warning(f"⚠️ API端点返回404 ({endpoint}): {str(e)[:200]}")
                else:
                    log.warning(f"⚠️ API端点连接错误 ({endpoint}): {str(e)[:200]}")
            except Exception as e:
                last_error = e
                log.warning(f"⚠️ API端点异常 ({endpoint}): {type(e).__name__}: {str(e)[:200]}")
                continue
        
        # 如果所有API都失败，静默返回错误（不抛出异常，让调用方处理）
        # 这样不会产生大量错误日志
        if last_error_code == 404 or (last_error and "404" in str(last_error)):
            # 静默返回错误，不抛出异常
            log.debug(f"所有API都失败，返回404错误（文档不存在或权限不足）")
            return {
                "code": 404,
                "msg": "文档不存在或权限不足",
                "data": {}
            }
        elif last_error:
            # 其他错误也静默返回
            log.debug(f"所有API都失败，返回错误: {str(last_error)[:100]}")
            return {
                "code": -1,
                "msg": str(last_error)[:100],
                "data": {}
            }
        else:
            log.warning("无法获取文档内容：没有可用的API端点")
            return {
                "code": -1,
                "msg": "无法获取文档内容：没有可用的API端点",
                "data": {}
            }

    def get_document_meta(self, document_token: str) -> Dict[str, Any]:
        """
        获取文档元信息（根据权限自动选择API端点）。

        Args:
            document_token: 文档token

        Returns:
            文档元信息
        """
        # 先尝试使用检测到的最佳API
        endpoint = self._get_best_api_endpoint(document_token, "meta", is_wiki_node=False)
        
        if endpoint:
            try:
                return self._request("GET", endpoint)
            except Exception as e:
                log.warning(f"首选API失败 ({endpoint}): {e}，尝试其他API...")
        
        # Fallback: 按优先级尝试所有可能的API
        fallback_apis = [
            f"docs/v1/documents/{document_token}",
            f"docx/v1/documents/{document_token}",
        ]
        
        last_error = None
        last_error_code = None
        for endpoint in fallback_apis:
            try:
                result = self._request("GET", endpoint)
                if result.get("code") == 0:
                    log.info(f"✅ 使用API端点: {endpoint}")
                    return result
                else:
                    # 记录业务错误码
                    last_error_code = result.get("code")
                    last_error = RuntimeError(f"API返回错误: {result.get('msg')} (code: {last_error_code})")
                    log.debug(f"API端点失败 ({endpoint}): {last_error}")
            except ConnectionError as e:
                # HTTP错误（如404）
                last_error = e
                # 尝试从错误信息中提取状态码
                error_str = str(e)
                if "404" in error_str:
                    last_error_code = 404
                log.debug(f"API端点失败 ({endpoint}): {e}")
            except Exception as e:
                last_error = e
                log.debug(f"API端点失败 ({endpoint}): {e}")
                continue
        
        # 如果所有API都失败，提供更详细的错误信息
        if last_error_code == 404:
            raise RuntimeError(
                f"文档元信息API返回404错误，可能原因：\n"
                f"1. 文档token格式不正确（知识库中的文档可能需要使用wiki API）\n"
                f"2. 文档不存在或已被删除\n"
                f"3. 权限不足（需要docs:document.content:read或docx:document:readonly权限）\n"
                f"文档token: {document_token[:30]}...\n"
                f"最后一个错误: {last_error}"
            ) from last_error
        elif last_error:
            raise RuntimeError(f"所有文档元信息API都失败，最后一个错误: {last_error}") from last_error
        else:
            raise RuntimeError("无法获取文档元信息：没有可用的API端点")

    def search_documents(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """
        搜索文档。

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            文档列表
        """
        endpoint = "search/v2/data_source"
        payload = {
            "query": query,
            "data_source_ids": [],
            "limit": limit,
        }
        return self._request("POST", endpoint, json_data=payload)

