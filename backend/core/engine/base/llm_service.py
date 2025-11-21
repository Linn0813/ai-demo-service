# encoding: utf-8
"""
LLM模型调用服务（共享）
"""
from typing import Optional

import requests

from core.engine.base.config import LLM_CONFIG
from core.logger import log


class LLMService:
    """LLM模型调用服务 - 测试用例生成和知识库问答共用"""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        self.base_url = base_url or LLM_CONFIG["llm_base_url"]
        self.model = model or LLM_CONFIG["default_model"]
        self.temperature = temperature or LLM_CONFIG["temperature"]
        self.max_tokens = max_tokens or LLM_CONFIG["max_tokens"]
        self.timeout = LLM_CONFIG["timeout"]

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
                # 检查服务是否可用
                if not self._check_service_available():
                    raise ConnectionError(f"无法连接到LLM服务: {self.base_url}")

                # 构建请求
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

                log.debug(f"正在调用模型: {self.model}...")
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()

                result = response.json()
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

    def _check_service_available(self) -> bool:
        """检查LLM服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

