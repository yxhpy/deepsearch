"""
搜索提供商 - 支持Bing、SerpAPI、Brave、Serper
"""
import asyncio
import aiohttp
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source_query: str
    rank: int = 0


class BaseSearchProvider(ABC):
    """搜索提供商基类"""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行搜索"""
        pass


class BingSearchProvider(BaseSearchProvider):
    """Bing搜索提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv("BING_SEARCH_API_KEY")
        self.endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
        self.market = config.get("market", "zh-CN")
        self.freshness = config.get("freshness", "")
        self.safe_search = config.get("safeSearch", "Moderate")
        
        if not self.api_key:
            raise ValueError("BING_SEARCH_API_KEY 环境变量未设置")
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行Bing搜索"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        params = {
            "q": query,
            "count": min(max_results, 50),
            "mkt": self.market,
            "safeSearch": self.safe_search,
            "responseFilter": "Webpages"
        }
        
        if self.freshness:
            params["freshness"] = self.freshness
        
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.endpoint, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_bing_results(data, query)
                    else:
                        print(f"Bing搜索失败 {response.status}: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Bing搜索异常: {e}")
            return []
    
    def _parse_bing_results(self, data: Dict[str, Any], query: str) -> List[SearchResult]:
        """解析Bing搜索结果"""
        results = []
        webpages = data.get("webPages", {}).get("value", [])
        
        for i, item in enumerate(webpages):
            result = SearchResult(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                source_query=query,
                rank=i + 1
            )
            results.append(result)
        
        return results


class SerpAPIProvider(BaseSearchProvider):
    """SerpAPI搜索提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv("SERPAPI_KEY")
        self.engine = config.get("engine", "google")
        self.location = config.get("location", "")
        self.num = config.get("num", 10)
        
        if not self.api_key:
            raise ValueError("SERPAPI_KEY 环境变量未设置")
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行SerpAPI搜索"""
        params = {
            "api_key": self.api_key,
            "engine": self.engine,
            "q": query,
            "num": min(max_results, self.num)
        }
        
        if self.location:
            params["location"] = self.location
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://serpapi.com/search", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_serpapi_results(data, query)
                    else:
                        print(f"SerpAPI搜索失败 {response.status}: {await response.text()}")
                        return []
        except Exception as e:
            print(f"SerpAPI搜索异常: {e}")
            return []
    
    def _parse_serpapi_results(self, data: Dict[str, Any], query: str) -> List[SearchResult]:
        """解析SerpAPI搜索结果"""
        results = []
        organic_results = data.get("organic_results", [])
        
        for i, item in enumerate(organic_results):
            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source_query=query,
                rank=i + 1
            )
            results.append(result)
        
        return results


class BraveSearchProvider(BaseSearchProvider):
    """Brave搜索提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        self.country = config.get("country", "CN")
        self.safesearch = config.get("safesearch", "moderate")
        
        if not self.api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY 环境变量未设置")
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行Brave搜索"""
        headers = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json"
        }
        
        params = {
            "q": query,
            "count": min(max_results, 20),
            "country": self.country,
            "safesearch": self.safesearch
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.search.brave.com/res/v1/web/search", 
                                     headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_brave_results(data, query)
                    else:
                        print(f"Brave搜索失败 {response.status}: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Brave搜索异常: {e}")
            return []
    
    def _parse_brave_results(self, data: Dict[str, Any], query: str) -> List[SearchResult]:
        """解析Brave搜索结果"""
        results = []
        web_results = data.get("web", {}).get("results", [])
        
        for i, item in enumerate(web_results):
            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                source_query=query,
                rank=i + 1
            )
            results.append(result)
        
        return results


class SerperProvider(BaseSearchProvider):
    """Serper.dev搜索提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv("SERPER_API_KEY")
        self.gl = config.get("gl", "cn")  # 地理位置
        self.hl = config.get("hl", "zh")  # 语言
        self.num = config.get("num", 10)  # 结果数量
        
        if not self.api_key:
            raise ValueError("SERPER_API_KEY 环境变量未设置")
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行Serper搜索"""
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "q": query,
            "gl": self.gl,
            "hl": self.hl,
            "num": min(max_results, self.num)
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post("https://google.serper.dev/search", 
                                      headers=headers, json=data) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        return self._parse_serper_results(result_data, query)
                    else:
                        print(f"Serper搜索失败 {response.status}: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Serper搜索异常: {e}")
            return []
    
    def _parse_serper_results(self, data: Dict[str, Any], query: str) -> List[SearchResult]:
        """解析Serper搜索结果"""
        results = []
        organic = data.get("organic", [])
        
        for i, item in enumerate(organic):
            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source_query=query,
                rank=i + 1
            )
            results.append(result)
        
        return results


def create_search_provider(config: Dict[str, Any]) -> BaseSearchProvider:
    """创建搜索提供商"""
    provider_name = config["provider"]
    
    if provider_name == "bing":
        return BingSearchProvider(config["bing"])
    elif provider_name == "serpapi":
        return SerpAPIProvider(config["serpapi"])
    elif provider_name == "brave":
        return BraveSearchProvider(config["brave"])
    elif provider_name == "serper":
        return SerperProvider(config["serper"])
    else:
        raise ValueError(f"不支持的搜索提供商: {provider_name}")


class ConcurrentSearchManager:
    """并发搜索管理器"""
    
    def __init__(self, provider: BaseSearchProvider, concurrency: int = 20):
        self.provider = provider
        self.semaphore = asyncio.Semaphore(concurrency)
    
    async def search_queries(self, queries: List[str], max_results_per_query: int = 10) -> List[SearchResult]:
        """并发执行多个查询"""
        tasks = []
        for query in queries:
            task = self._search_with_semaphore(query, max_results_per_query)
            tasks.append(task)
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_results = []
        for results in results_list:
            if isinstance(results, list):
                all_results.extend(results)
        
        return all_results
    
    async def _search_with_semaphore(self, query: str, max_results: int) -> List[SearchResult]:
        """带信号量的搜索"""
        async with self.semaphore:
            await asyncio.sleep(0.1)  # 简单的速率限制
            return await self.provider.search(query, max_results)