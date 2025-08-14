"""
爬虫提供商 - 支持多种反爬虫绕过服务
"""
import aiohttp
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from search_providers import SearchResult
from content_processor import ProcessedContent
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


@dataclass
class CrawlResult:
    """爬取结果"""
    url: str
    html: str
    status_code: int
    final_url: str
    success: bool
    error: Optional[str] = None


class BaseCrawlProvider(ABC):
    """爬虫提供商基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """获取URL内容"""
        pass


class NativeCrawlProvider(BaseCrawlProvider):
    """原生爬虫 (使用改进后的反爬虫机制)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        from content_processor import ContentCrawler
        self.crawler = ContentCrawler(
            concurrency=config.get('crawl_concurrency', 50),
            timeout=config.get('request_timeout_sec', 20),
            per_domain_rps=config.get('per_domain_rps', 1.0)
        )
    
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """使用原生爬虫获取内容"""
        search_result = SearchResult(
            url=url,
            title="",
            snippet="",
            source_query="",
            rank=1
        )
        
        processed = await self.crawler._crawl_single_url(search_result)
        if processed and processed.http_status == 200:
            return CrawlResult(
                url=url,
                html="",  # 原生爬虫不返回原始HTML
                status_code=processed.http_status,
                final_url=processed.url,
                success=True
            )
        else:
            return CrawlResult(
                url=url,
                html="",
                status_code=0,
                final_url=url,
                success=False,
                error="原生爬虫抓取失败"
            )


class ScrapingBeeCrawlProvider(BaseCrawlProvider):
    """ScrapingBee爬虫提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('SCRAPINGBEE_API_KEY')
        self.base_url = "https://app.scrapingbee.com/api/v1/"
    
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """使用ScrapingBee获取内容"""
        if not self.api_key:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error="缺少SCRAPINGBEE_API_KEY"
            )
        
        params = {
            'api_key': self.api_key,
            'url': url,
            'render_js': str(self.config.get('render_js', True)).lower(),
            'premium_proxy': str(self.config.get('premium_proxy', False)).lower(),
            'country_code': self.config.get('country_code', 'CN')
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    html = await response.text()
                    
                    return CrawlResult(
                        url=url,
                        html=html,
                        status_code=response.status,
                        final_url=url,  # ScrapingBee不返回final_url
                        success=response.status == 200
                    )
        except Exception as e:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error=f"ScrapingBee错误: {e}"
            )


class ScrapflyCrawlProvider(BaseCrawlProvider):
    """Scrapfly爬虫提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('SCRAPFLY_API_KEY')
        self.base_url = "https://api.scrapfly.io/scrape"
    
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """使用Scrapfly获取内容"""
        if not self.api_key:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error="缺少SCRAPFLY_API_KEY"
            )
        
        params = {
            'key': self.api_key,
            'url': url,
            'render_js': str(self.config.get('render_js', True)).lower(),
            'proxy_pool': self.config.get('proxy_pool', 'datacenter'),
            'country': self.config.get('country', 'CN')
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get('result', {})
                        
                        return CrawlResult(
                            url=url,
                            html=result.get('content', ''),
                            status_code=result.get('status_code', response.status),
                            final_url=result.get('url', url),
                            success=True
                        )
                    else:
                        return CrawlResult(
                            url=url, html="", status_code=response.status, final_url=url,
                            success=False, error=f"Scrapfly HTTP {response.status}"
                        )
        except Exception as e:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error=f"Scrapfly错误: {e}"
            )


class BrightDataCrawlProvider(BaseCrawlProvider):
    """Bright Data爬虫提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.username = config.get('BRIGHT_DATA_USERNAME')
        self.password = config.get('BRIGHT_DATA_PASSWORD')
        self.zone = config.get('zone', 'residential')
        self.country = config.get('country', 'CN')
    
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """使用Bright Data代理获取内容"""
        if not self.username or not self.password:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error="缺少Bright Data凭证"
            )
        
        # 构建代理配置
        proxy_url = f"http://{self.username}-session-{asyncio.current_task().get_name()}-country-{self.country.lower()}:{self.password}@zproxy.lum-superproxy.io:22225"
        
        try:
            connector = aiohttp.TCPConnector()
            timeout = aiohttp.ClientTimeout(total=30)
            
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            if headers:
                request_headers.update(headers)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=True
            ) as session:
                async with session.get(
                    url,
                    headers=request_headers,
                    proxy=proxy_url,
                    allow_redirects=True
                ) as response:
                    html = await response.text()
                    
                    return CrawlResult(
                        url=url,
                        html=html,
                        status_code=response.status,
                        final_url=str(response.url),
                        success=response.status == 200
                    )
                    
        except Exception as e:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error=f"Bright Data错误: {e}"
            )


class PlaywrightCrawlProvider(BaseCrawlProvider):
    """Playwright爬虫提供商 - 用于兜底处理复杂页面"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.timeout = config.get('timeout', 30000)  # 30秒超时
        self.headless = config.get('headless', True)
        self.wait_for_load = config.get('wait_for_load', True)
        self.wait_time = config.get('wait_time', 2000)  # 等待2秒让页面加载
        self.user_agent = config.get('user_agent', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> CrawlResult:
        """使用Playwright获取内容"""
        try:
            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                try:
                    # 创建带用户代理的浏览器上下文
                    context = await browser.new_context(user_agent=self.user_agent)
                    
                    # 创建页面
                    page = await context.new_page()
                    
                    # 设置额外headers
                    if headers:
                        await page.set_extra_http_headers(headers)
                    
                    # 设置视口大小
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                    
                    # 导航到页面
                    response = await page.goto(
                        url, 
                        timeout=self.timeout,
                        wait_until='domcontentloaded'
                    )
                    
                    # 等待页面加载
                    if self.wait_for_load:
                        await asyncio.sleep(self.wait_time / 1000)
                    
                    # 获取页面内容
                    html = await page.content()
                    final_url = page.url
                    status_code = response.status if response else 200
                    
                    return CrawlResult(
                        url=url,
                        html=html,
                        status_code=status_code,
                        final_url=final_url,
                        success=status_code < 400
                    )
                    
                finally:
                    await browser.close()
                    
        except PlaywrightTimeoutError:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error="Playwright超时"
            )
        except Exception as e:
            return CrawlResult(
                url=url, html="", status_code=0, final_url=url,
                success=False, error=f"Playwright错误: {e}"
            )


class CrawlProviderFactory:
    """爬虫提供商工厂"""
    
    @staticmethod
    def create_provider(provider_type: str, config: Dict[str, Any]) -> BaseCrawlProvider:
        """创建爬虫提供商实例"""
        if provider_type == 'native':
            return NativeCrawlProvider(config)
        elif provider_type == 'scrapingbee':
            return ScrapingBeeCrawlProvider(config)
        elif provider_type == 'scrapfly':
            return ScrapflyCrawlProvider(config)
        elif provider_type == 'bright_data':
            return BrightDataCrawlProvider(config)
        elif provider_type == 'playwright':
            return PlaywrightCrawlProvider(config)
        else:
            raise ValueError(f"不支持的爬虫提供商: {provider_type}")


class EnhancedCrawlManager:
    """增强的爬虫管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        crawl_config = config.get('crawling', {})
        provider_type = crawl_config.get('provider', 'native')
        
        # 合并配置
        provider_config = {**config.get('runtime', {}), **crawl_config.get(provider_type, {})}
        
        # 添加环境变量
        import os
        provider_config.update({
            'SCRAPINGBEE_API_KEY': os.getenv('SCRAPINGBEE_API_KEY'),
            'SCRAPFLY_API_KEY': os.getenv('SCRAPFLY_API_KEY'),
            'BRIGHT_DATA_USERNAME': os.getenv('BRIGHT_DATA_USERNAME'),
            'BRIGHT_DATA_PASSWORD': os.getenv('BRIGHT_DATA_PASSWORD')
        })
        
        self.provider = CrawlProviderFactory.create_provider(provider_type, provider_config)
        print(f"使用爬虫提供商: {provider_type}")
    
    async def crawl_url(self, url: str) -> Optional[str]:
        """爬取单个URL并返回HTML内容"""
        result = await self.provider.fetch_url(url)
        
        if result.success:
            print(f"成功抓取: {url} (状态: {result.status_code})")
            return result.html
        else:
            print(f"抓取失败: {url} - {result.error}")
            return None