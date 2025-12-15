# encoding: utf-8
"""
网络搜索服务，用于补充知识库信息。
支持多种搜索引擎API。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests
from shared.logger import log


class WebSearchService:
    """网络搜索服务，用于搜索网络信息补充知识库。"""

    def __init__(
        self,
        provider: str = "duckduckgo",  # 默认使用DuckDuckGo（免费）
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        初始化网络搜索服务。

        Args:
            provider: 搜索引擎提供商（"duckduckgo", "google", "bing"）
            api_key: API密钥（如果需要）
            api_url: API地址（如果需要）
        """
        self.provider = provider
        self.api_key = api_key
        self.api_url = api_url or self._get_default_api_url()

    def _get_default_api_url(self) -> str:
        """获取默认API地址"""
        if self.provider == "duckduckgo":
            return "https://api.duckduckgo.com/"
        elif self.provider == "google":
            return "https://www.googleapis.com/customsearch/v1"
        elif self.provider == "bing":
            return "https://api.bing.microsoft.com/v7.0/search"
        else:
            return "https://api.duckduckgo.com/"

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        搜索网络信息。

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            搜索结果列表，每个结果包含title、url、snippet等
        """
        try:
            if self.provider == "duckduckgo":
                return self._search_duckduckgo(query, max_results)
            elif self.provider == "google":
                return self._search_google(query, max_results)
            elif self.provider == "bing":
                return self._search_bing(query, max_results)
            else:
                log.warning(f"不支持的搜索引擎: {self.provider}，使用DuckDuckGo")
                return self._search_duckduckgo(query, max_results)
        except Exception as e:
            log.error(f"网络搜索失败: {e}")
            return []

    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """使用DuckDuckGo搜索（免费，无需API Key）"""
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # 提取Abstract（摘要）
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", ""),
                    "source": "duckduckgo_abstract",
                })
            
            # 提取RelatedTopics（相关主题）
            related_topics = data.get("RelatedTopics", [])
            for topic in related_topics[:max_results - len(results)]:
                if isinstance(topic, dict):
                    text = topic.get("Text", "")
                    url = topic.get("FirstURL", "")
                    if text and url:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0] if " - " in text else text[:50],
                            "url": url,
                            "snippet": text,
                            "source": "duckduckgo_related",
                        })
            
            log.info(f"✅ DuckDuckGo搜索成功，找到 {len(results)} 个结果")
            return results[:max_results]
            
        except Exception as e:
            log.warning(f"DuckDuckGo搜索失败: {e}，尝试使用SerpAPI")
            # 如果DuckDuckGo失败，尝试使用SerpAPI（如果配置了）
            if self.api_key:
                return self._search_serpapi(query, max_results)
            return []

    def _search_serpapi(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """使用SerpAPI搜索（需要API Key）"""
        try:
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "num": max_results,
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            organic_results = data.get("organic_results", [])
            
            for result in organic_results[:max_results]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "source": "serpapi",
                })
            
            log.info(f"✅ SerpAPI搜索成功，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            log.error(f"SerpAPI搜索失败: {e}")
            return []

    def _search_google(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """使用Google Custom Search API"""
        if not self.api_key:
            log.warning("Google搜索需要API Key，跳过")
            return []
        
        try:
            url = self.api_url
            params = {
                "key": self.api_key,
                "cx": self.api_url.split("cx=")[-1] if "cx=" in self.api_url else "",
                "q": query,
                "num": max_results,
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            items = data.get("items", [])
            
            for item in items[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "google",
                })
            
            log.info(f"✅ Google搜索成功，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            log.error(f"Google搜索失败: {e}")
            return []

    def _search_bing(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """使用Bing Search API"""
        if not self.api_key:
            log.warning("Bing搜索需要API Key，跳过")
            return []
        
        try:
            url = self.api_url
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
            }
            params = {
                "q": query,
                "count": max_results,
                "offset": 0,
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            web_pages = data.get("webPages", {}).get("value", [])
            
            for page in web_pages[:max_results]:
                results.append({
                    "title": page.get("name", ""),
                    "url": page.get("url", ""),
                    "snippet": page.get("snippet", ""),
                    "source": "bing",
                })
            
            log.info(f"✅ Bing搜索成功，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            log.error(f"Bing搜索失败: {e}")
            return []

