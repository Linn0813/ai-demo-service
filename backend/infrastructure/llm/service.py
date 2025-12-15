# encoding: utf-8
"""
LLM模型调用服务（共享）
"""
from typing import Optional

import requests

from shared.config import LLM_CONFIG
from shared.logger import log


class LLMService:
    """LLM模型调用服务 - 测试用例生成和知识库问答共用"""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 api_key: Optional[str] = None, provider: Optional[str] = None,
                 azure_deployment: Optional[str] = None, azure_api_version: Optional[str] = None):
        self.provider = provider or LLM_CONFIG.get("provider", "ollama")
        self.base_url = base_url or LLM_CONFIG["llm_base_url"]
        self.model = model or LLM_CONFIG["default_model"]
        self.temperature = temperature or LLM_CONFIG["temperature"]
        self.max_tokens = max_tokens or LLM_CONFIG["max_tokens"]
        self.timeout = LLM_CONFIG["timeout"]
        self.api_key = api_key or LLM_CONFIG.get("api_key", "")
        self.azure_deployment = azure_deployment or LLM_CONFIG.get("azure_deployment", "")
        self.azure_api_version = azure_api_version or LLM_CONFIG.get("azure_api_version", "2024-12-01-preview")

    def generate(self, prompt: str, max_retries: int = 2) -> str:
        """
        调用LLM生成内容（带重试机制）

        Args:
            prompt: 输入的提示词
            max_retries: 最大重试次数

        Returns:
            LLM生成的文本内容

        Raises:
            ConnectionError: 无法连接到LLM服务
            TimeoutError: 请求超时
            RuntimeError: LLM服务请求失败
        """
        last_error: Exception = ConnectionError("未知错误")
        for attempt in range(max_retries + 1):
            try:
                # 检查服务是否可用（仅对 Ollama 进行检查）
                if self.provider == "ollama" and not self._check_service_available():
                    raise ConnectionError(f"无法连接到LLM服务: {self.base_url}")

                # 根据 provider 类型构建不同的请求
                if self.provider == "openai":
                    url, payload, headers = self._build_openai_request(prompt)
                else:  # ollama
                    url, payload, headers = self._build_ollama_request(prompt)

                log.debug(f"正在调用模型: {self.model} (provider: {self.provider})...")
                
                # 调试日志：记录请求信息（不记录完整的 API key）
                if self.provider == "openai":
                    log.info(f"🔵 Azure OpenAI API 调用:")
                    log.info(f"  URL: {url}")
                    log.info(f"  Model: {self.model}")
                    log.info(f"  Deployment: {self.azure_deployment or self.model}")
                    log.info(f"  Headers: {list(headers.keys())}")
                    log.info(f"  API Key 前10字符: {self.api_key[:10] + '...' if self.api_key else 'None'}")
                    log.info(f"  Payload keys: {list(payload.keys())}")
                    log.info(f"  Prompt length: {len(prompt)} 字符")
                
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                result = response.json()
                
                # 根据 provider 类型解析响应
                if self.provider == "openai":
                    return self._parse_openai_response(result)
                else:  # ollama
                    return result.get("response", "")

            except requests.exceptions.ConnectionError as e:
                error_detail = str(e)
                last_error = ConnectionError(
                    f"无法连接到LLM服务 {self.base_url}，请确保服务正在运行。"
                    f"错误详情: {error_detail}"
                )
                if attempt < max_retries:
                    log.warning(f"连接失败（尝试 {attempt + 1}/{max_retries + 1}）: {error_detail}")
                    continue
                raise last_error
            except requests.exceptions.Timeout as e:
                error_detail = str(e)
                last_error = TimeoutError(
                    f"请求超时（{self.timeout}秒），模型: {self.model}。"
                    f"可能是文档过长或模型响应较慢，请尝试减少文档长度或增加超时时间。"
                    f"错误详情: {error_detail}"
                )
                if attempt < max_retries:
                    log.warning(f"请求超时（尝试 {attempt + 1}/{max_retries + 1}）: {error_detail}")
                    continue
                raise last_error
            except requests.exceptions.HTTPError as e:
                error_detail = str(e)
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                
                # 如果是 401 错误，提供更详细的错误信息
                if status_code == 401:
                    response_text = ""
                    response_json = None
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            response_text = e.response.text[:500]  # 取前500字符
                            try:
                                response_json = e.response.json()
                            except:
                                pass
                        except:
                            pass
                    
                    # 记录详细的错误信息
                    log.error(f"❌ Azure OpenAI 认证失败 (401):")
                    log.error(f"  URL: {url}")
                    log.error(f"  Deployment: {self.azure_deployment or self.model}")
                    log.error(f"  API Key 前20字符: {self.api_key[:20] + '...' if self.api_key else 'None'}")
                    log.error(f"  响应状态码: {status_code}")
                    log.error(f"  响应内容: {response_text}")
                    if response_json:
                        log.error(f"  响应JSON: {response_json}")
                    
                    last_error = RuntimeError(
                        f"LLM服务认证失败（401 Unauthorized），模型: {self.model}，部署: {self.azure_deployment or self.model}。"
                        f"请检查：1) API key 是否正确；2) 部署名称是否正确；3) API key 是否有访问该部署的权限。"
                        f"响应详情: {response_text}"
                    )
                else:
                    last_error = RuntimeError(
                        f"LLM服务HTTP错误（状态码: {status_code}），模型: {self.model}。"
                        f"错误详情: {error_detail}"
                    )
                
                if attempt < max_retries:
                    log.warning(f"HTTP错误（尝试 {attempt + 1}/{max_retries + 1}）: {error_detail}")
                    continue
                raise last_error
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                last_error = RuntimeError(
                    f"LLM服务请求失败，模型: {self.model}，URL: {self.base_url}。"
                    f"错误详情: {error_detail}"
                )
                if attempt < max_retries:
                    log.warning(f"请求失败（尝试 {attempt + 1}/{max_retries + 1}）: {error_detail}")
                    continue
                raise last_error

        # 理论上不应该到达这里（所有重试都会抛出异常或返回）
        # 但为了满足类型检查，添加断言
        assert False, "所有重试都失败，应该已经抛出异常"
        raise last_error  # type: ignore

    def _build_ollama_request(self, prompt: str):
        """构建 Ollama API 请求"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        headers = {}
        return url, payload, headers

    def _build_openai_request(self, prompt: str):
        """构建 OpenAI 兼容 API 请求"""
        # 检测是否是 Azure OpenAI Service
        is_azure = "cognitiveservices.azure.com" in self.base_url or "openai.azure.com" in self.base_url
        
        if is_azure:
            # Azure OpenAI Service 端点格式：
            # 标准格式：https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version={version}
            # 旧格式：https://{resource}.cognitiveservices.azure.com/openai/deployments/{deployment}/chat/completions?api-version={version}
            # 新格式（v1 API）：https://{resource}.openai.azure.com/openai/v1/chat/completions?api-version={version}
            
            # 如果 base_url 已经包含完整路径，直接使用
            if "/openai/deployments/" in self.base_url or "/openai/v1/" in self.base_url:
                url = self.base_url
                if "api-version" not in url:
                    url = f"{url}?api-version={self.azure_api_version}"
            else:
                # 构建 Azure OpenAI Service 端点
                # 使用配置的 deployment name，如果没有则使用模型名称
                deployment = self.azure_deployment or self.model
                base = self.base_url.rstrip('/')
                
                # 使用原始的 base_url（不进行转换）
                # 根据实际测试，cognitiveservices.azure.com 格式是正确的
                # 使用传统的 deployments 端点格式
                url = f"{base}/openai/deployments/{deployment}/chat/completions?api-version={self.azure_api_version}"
        else:
            # 标准 OpenAI 兼容 API 通常使用 /v1/chat/completions 端点
            # 如果 base_url 已经包含 /v1，则直接使用，否则添加 /v1
            if self.base_url.endswith("/v1"):
                url = f"{self.base_url}/chat/completions"
            elif "/v1" in self.base_url:
                url = f"{self.base_url}/chat/completions"
            else:
                url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        
        # Azure OpenAI Service 需要在 model 字段中使用 deployment 名称
        if is_azure:
            model_for_request = self.azure_deployment or self.model
        else:
            model_for_request = self.model
        
        payload = {
            "model": model_for_request,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        }
        
        # gpt-5.2-chat 模型的特殊处理
        is_gpt52 = is_azure and ("gpt-5.2" in model_for_request.lower() or "gpt-5" in model_for_request.lower())
        
        if is_gpt52:
            # gpt-5.2-chat 使用 max_completion_tokens 而不是 max_tokens
            payload["max_completion_tokens"] = self.max_tokens
            # gpt-5.2-chat 只支持 temperature=1（默认值），不支持其他值
            # 不设置 temperature，使用默认值
        else:
            payload["temperature"] = self.temperature
            payload["max_tokens"] = self.max_tokens
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # 添加 API key 认证
        if self.api_key:
            if is_azure:
                # Azure OpenAI Service 使用 api-key 头（Azure 特有格式）
                headers["api-key"] = self.api_key
            else:
                # 标准 OpenAI API 使用 Authorization Bearer 头
                headers["Authorization"] = f"Bearer {self.api_key}"
        
        return url, payload, headers

    def _parse_openai_response(self, result: dict) -> str:
        """解析 OpenAI 兼容 API 响应"""
        # OpenAI 格式: {"choices": [{"message": {"content": "..."}}]}
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
            elif "text" in choice:
                return choice["text"]
        
        # 兼容其他可能的响应格式
        if "content" in result:
            return result["content"]
        if "text" in result:
            return result["text"]
        if "response" in result:
            return result["response"]
        
        # 如果无法解析，返回整个响应的字符串表示
        log.warning(f"无法解析 OpenAI 响应格式: {result}")
        return str(result)

    def _check_service_available(self) -> bool:
        """检查LLM服务是否可用（仅用于 Ollama）"""
        if self.provider != "ollama":
            return True  # OpenAI 兼容 API 不需要预先检查
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

