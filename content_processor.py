"""
内容处理器 - 负责网页抓取、内容分析和评分
"""
import asyncio
import aiohttp
import re
import random
import time
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from langchain.embeddings.base import Embeddings
from search_providers import SearchResult
import hashlib
from datetime import datetime


@dataclass
class ProcessedContent:
    """处理后的内容"""
    url: str
    title: str
    snippet: str
    content: str
    source_query: str
    rank: int
    
    # 评分相关
    similarity_score: float = 0.0
    keyword_score: float = 0.0
    freshness_score: float = 0.0
    domain_score: float = 0.0
    structure_score: float = 0.0
    final_score: float = 0.0
    
    # 元数据
    http_status: int = 0
    depth: int = 0
    parent_url: str = ""
    domain_name: str = ""
    language: str = ""
    is_rendered: bool = False
    content_length: int = 0
    content_hash: str = ""
    
    # 决策信息
    decision: str = "pending"  # accepted, rejected, pending
    explanation: str = ""
    
    # 提取的链接
    extracted_links: List[str] = field(default_factory=list)


class ContentCrawler:
    """内容爬虫"""
    
    def __init__(self, concurrency: int = 50, timeout: int = 20, per_domain_rps: float = 1.0, 
                 crawl_manager=None):
        self.concurrency = concurrency
        self.timeout = timeout
        self.per_domain_rps = per_domain_rps
        self.semaphore = asyncio.Semaphore(concurrency)
        self.domain_last_request = {}  # 域名速率限制
        self.crawl_manager = crawl_manager  # 外部爬虫提供商
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
    async def crawl_urls(self, search_results: List[SearchResult]) -> List[ProcessedContent]:
        """批量抓取URL内容"""
        tasks = []
        for result in search_results:
            task = self._crawl_with_semaphore(result)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_contents = []
        for result in results:
            if isinstance(result, ProcessedContent):
                processed_contents.append(result)
        
        return processed_contents
    
    async def _crawl_with_semaphore(self, search_result: SearchResult) -> Optional[ProcessedContent]:
        """带信号量的抓取"""
        async with self.semaphore:
            await self._rate_limit_for_domain(search_result.url)
            return await self._crawl_single_url(search_result)
    
    async def _rate_limit_for_domain(self, url: str):
        """域名级别的速率限制"""
        domain = urlparse(url).netloc
        current_time = datetime.now().timestamp()
        
        if domain in self.domain_last_request:
            elapsed = current_time - self.domain_last_request[domain]
            required_interval = 1.0 / self.per_domain_rps
            if elapsed < required_interval:
                await asyncio.sleep(required_interval - elapsed)
        
        self.domain_last_request[domain] = datetime.now().timestamp()
    
    async def _crawl_single_url(self, search_result: SearchResult, max_retries: int = 3) -> Optional[ProcessedContent]:
        """抓取单个URL，带重试和反反爬虫机制"""
        # 如果有外部爬虫管理器，优先使用
        if self.crawl_manager:
            try:
                html_content = await self.crawl_manager.crawl_url(search_result.url)
                if html_content:
                    processed = self._parse_html_content(
                        html_content, 
                        search_result,
                        200,  # 外部提供商成功时状态码
                        final_url=search_result.url
                    )
                    return processed
                else:
                    print(f"外部爬虫失败，回退到原生爬虫: {search_result.url}")
            except Exception as e:
                print(f"外部爬虫错误，回退到原生爬虫: {search_result.url} - {e}")
        
        # 原生爬虫逻辑
        for attempt in range(max_retries):
            try:
                # 随机User-Agent和请求头
                headers = self._get_random_headers(search_result.url)
                
                # 随机延迟 (0.5-2.0秒)
                if attempt > 0:
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300,
                    use_dns_cache=True,
                )
                
                async with aiohttp.ClientSession(
                    timeout=timeout, 
                    connector=connector,
                    cookie_jar=aiohttp.CookieJar()
                ) as session:
                    async with session.get(
                        search_result.url, 
                        headers=headers, 
                        allow_redirects=True,
                        ssl=False  # 忽略SSL错误
                    ) as response:
                        
                        # 处理常见的反爬虫状态码
                        if response.status == 429:  # 限流
                            print(f"限流检测 {search_result.url}, 等待重试...")
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                        elif response.status == 403:  # 拒绝访问
                            print(f"访问被拒绝 {search_result.url}, 尝试不同策略...")
                            continue
                        elif response.status >= 400:
                            if attempt == max_retries - 1:
                                print(f"HTTP错误 {response.status}: {search_result.url}")
                                return None
                            continue
                        
                        content_type = response.headers.get('content-type', '').lower()
                        
                        # 只处理HTML内容
                        if 'html' not in content_type:
                            return None
                        
                        html_content = await response.text()
                        
                        # 检查是否是验证码页面或反爬虫页面
                        if self._is_anti_bot_page(html_content):
                            print(f"检测到反爬虫页面 {search_result.url}, 跳过")
                            return None
                        
                        # 解析内容
                        processed = self._parse_html_content(
                            html_content, 
                            search_result,
                            response.status,
                            final_url=str(response.url)
                        )
                        
                        return processed
                        
            except asyncio.TimeoutError:
                print(f"超时 {search_result.url} (尝试 {attempt + 1}/{max_retries})")
                continue
            except aiohttp.ClientError as e:
                print(f"网络错误 {search_result.url}: {e} (尝试 {attempt + 1}/{max_retries})")
                continue
            except Exception as e:
                print(f"抓取失败 {search_result.url}: {e} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None
                continue
        
        return None
    
    def _get_random_headers(self, url: str) -> Dict[str, str]:
        """生成随机请求头"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': random.choice([
                'zh-CN,zh;q=0.9,en;q=0.8',
                'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        # 添加Referer (模拟从搜索引擎来)
        referers = [
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://www.baidu.com/',
            f'https://www.google.com/search?q={domain}'
        ]
        headers['Referer'] = random.choice(referers)
        
        # 随机添加一些可选头部
        if random.random() < 0.3:
            headers['DNT'] = '1'
        if random.random() < 0.5:
            headers['Sec-GPC'] = '1'
        
        return headers
    
    def _is_anti_bot_page(self, html_content: str) -> bool:
        """检测是否是反爬虫页面"""
        html_lower = html_content.lower()
        
        # 常见反爬虫关键词
        anti_bot_keywords = [
            'captcha', 'recaptcha', 'hcaptcha',
            'cloudflare', 'please wait', 'checking your browser',
            'access denied', 'blocked', 'robot', 'bot detection',
            'verify you are human', '验证码', '机器人', '访问被拒绝',
            'just a moment', 'ddos protection', 'security check'
        ]
        
        for keyword in anti_bot_keywords:
            if keyword in html_lower:
                return True
        
        # 检查页面长度 - 反爬虫页面通常很短
        if len(html_content.strip()) < 500:
            return True
        
        return False
    
    def _parse_html_content(self, html: str, search_result: SearchResult, status_code: int, final_url: str) -> ProcessedContent:
        """解析HTML内容"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 移除脚本和样式
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # 提取标题
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else search_result.title
        
        # 提取主要内容
        content = self._extract_main_content(soup)
        
        # 提取链接
        links = self._extract_links(soup, final_url)
        
        # 计算内容哈希
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # 检测语言
        language = self._detect_language(content[:1000])
        
        # 提取域名
        domain_name = urlparse(final_url).netloc
        
        return ProcessedContent(
            url=final_url,
            title=title,
            snippet=search_result.snippet,
            content=content,
            source_query=search_result.source_query,
            rank=search_result.rank,
            http_status=status_code,
            domain_name=domain_name,
            language=language,
            content_length=len(content),
            content_hash=content_hash,
            extracted_links=links
        )
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """提取主要内容"""
        # 尝试找到主要内容区域
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.content', '.main-content', '.post-content',
            '#content', '#main', '#post'
        ]
        
        main_content = None
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body') or soup
        
        # 提取纯文本
        text = main_content.get_text(separator='\n')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        content = ' '.join(chunk for chunk in chunks if chunk)
        
        return content
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取页面链接"""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if href and not href.startswith('#'):
                absolute_url = urljoin(base_url, href)
                if self._is_valid_url(absolute_url):
                    links.append(absolute_url)
        
        return list(set(links))  # 去重
    
    def _is_valid_url(self, url: str) -> bool:
        """检查URL是否有效"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except:
            return False
    
    def _detect_language(self, text: str) -> str:
        """简单的语言检测"""
        chinese_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        if chinese_count > len(text) * 0.1:
            return 'zh'
        return 'en'


class ContentScorer:
    """内容评分器"""
    
    def __init__(self, embeddings: Embeddings, weights: Dict[str, float]):
        self.embeddings = embeddings
        self.weights = weights
        
        # 可信域名列表（示例）
        self.trusted_domains = {
            'github.com', 'stackoverflow.com', 'docs.microsoft.com',
            'developer.mozilla.org', 'python.org', 'nodejs.org',
            'reactjs.org', 'vuejs.org', 'angular.io',
            'medium.com', 'dev.to', 'hackernoon.com'
        }
    
    async def score_contents(self, contents: List[ProcessedContent], demand_text: str, 
                           keywords: List[str]) -> List[ProcessedContent]:
        """批量评分内容"""
        if not contents:
            return contents
        
        # 获取需求的嵌入向量
        demand_embedding = await self.embeddings.aembed_query(demand_text)
        
        # 获取内容的嵌入向量（分批处理，阿里云百炼限制批次大小<=10）
        content_texts = [c.content[:2000] for c in contents]  # 限制长度
        content_embeddings = []
        batch_size = 10  # 阿里云百炼的批次限制
        
        for i in range(0, len(content_texts), batch_size):
            batch = content_texts[i:i + batch_size]
            batch_embeddings = await self.embeddings.aembed_documents(batch)
            content_embeddings.extend(batch_embeddings)
        
        # 计算每个内容的评分
        for i, content in enumerate(contents):
            content.similarity_score = self._calculate_similarity(
                demand_embedding, content_embeddings[i]
            )
            content.keyword_score = self._calculate_keyword_score(
                content.content, keywords
            )
            content.freshness_score = self._calculate_freshness_score(content.url)
            content.domain_score = self._calculate_domain_score(content.domain_name)
            content.structure_score = self._calculate_structure_score(content.content)
            
            # 计算最终分数
            content.final_score = (
                content.similarity_score * self.weights.get('sim', 0.4) +
                content.keyword_score * self.weights.get('kw', 0.2) +
                content.freshness_score * self.weights.get('fresh', 0.15) +
                content.domain_score * self.weights.get('domain', 0.15) +
                content.structure_score * self.weights.get('structure', 0.1)
            )
        
        return contents
    
    def _calculate_similarity(self, demand_embedding: List[float], 
                            content_embedding: List[float]) -> float:
        """计算相似度分数"""
        try:
            import numpy as np
            demand_vec = np.array(demand_embedding)
            content_vec = np.array(content_embedding)
            
            # 计算余弦相似度
            dot_product = np.dot(demand_vec, content_vec)
            norm_demand = np.linalg.norm(demand_vec)
            norm_content = np.linalg.norm(content_vec)
            
            if norm_demand == 0 or norm_content == 0:
                return 0.0
            
            similarity = dot_product / (norm_demand * norm_content)
            return max(0.0, min(1.0, similarity))
        except:
            return 0.0
    
    def _calculate_keyword_score(self, content: str, keywords: List[str]) -> float:
        """计算关键词匹配分数"""
        if not keywords:
            return 0.0
        
        content_lower = content.lower()
        matched_keywords = sum(1 for kw in keywords if kw.lower() in content_lower)
        return matched_keywords / len(keywords)
    
    def _calculate_freshness_score(self, url: str) -> float:
        """计算新鲜度分数（基于URL中的日期模式）"""
        current_year = datetime.now().year
        
        # 查找URL中的年份
        year_pattern = r'/20(\d{2})/'
        match = re.search(year_pattern, url)
        if match:
            year = 2000 + int(match.group(1))
            years_old = current_year - year
            return max(0.0, 1.0 - years_old * 0.1)  # 每年减少0.1分
        
        return 0.5  # 默认中等新鲜度
    
    def _calculate_domain_score(self, domain: str) -> float:
        """计算域名可信度分数"""
        if domain in self.trusted_domains:
            return 1.0
        
        # 基于域名后缀的简单评分
        if domain.endswith('.edu') or domain.endswith('.gov'):
            return 0.9
        elif domain.endswith('.org'):
            return 0.8
        elif domain.endswith('.com') or domain.endswith('.net'):
            return 0.6
        else:
            return 0.4
    
    def _calculate_structure_score(self, content: str) -> float:
        """计算内容结构化程度分数"""
        score = 0.0
        
        # 检查是否有标题结构
        if any(pattern in content for pattern in ['#', '##', '###']):
            score += 0.3
        
        # 检查是否有列表
        if any(pattern in content for pattern in ['1.', '2.', '•', '-']):
            score += 0.3
        
        # 检查内容长度适中
        if 500 <= len(content) <= 5000:
            score += 0.2
        
        # 检查是否有代码块
        if any(pattern in content for pattern in ['```', '`', 'function', 'class']):
            score += 0.2
        
        return min(1.0, score)