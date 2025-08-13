"""
网站发现系统 - 主要业务逻辑流程控制
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from config_manager import ConfigManager
from unified_query_chain import create_unified_query_chain, QueryResult
from search_providers import create_search_provider, ConcurrentSearchManager
from content_processor import ContentCrawler, ContentScorer, ProcessedContent
from crawling_providers import EnhancedCrawlManager
from excel_exporter import ExcelExporter


class WebsiteDiscoveryEngine:
    """网站发现引擎"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_manager = ConfigManager(config_path)
        
        # 初始化组件
        self.llm = self.config_manager.get_llm()
        self.embeddings = self.config_manager.get_embeddings()
        self.search_provider = create_search_provider(self.config_manager.get_search_config())
        
        self.query_chain = create_unified_query_chain(self.llm, self.config_manager.config)
        
        # 配置参数
        self.runtime_config = self.config_manager.get_runtime_config()
        self.logic_config = self.config_manager.get_logic_config()
        self.scoring_weights = self.config_manager.get_scoring_weights()
        self.export_config = self.config_manager.get_export_config()
        
        # 初始化处理组件
        self.search_manager = ConcurrentSearchManager(
            self.search_provider,
            self.runtime_config.get('search_concurrency', 20)
        )
        
        # 初始化爬虫管理器
        try:
            self.crawl_manager = EnhancedCrawlManager(self.config_manager.config)
        except Exception as e:
            print(f"初始化外部爬虫失败，使用原生爬虫: {e}")
            self.crawl_manager = None
        
        self.crawler = ContentCrawler(
            concurrency=self.runtime_config.get('crawl_concurrency', 50),
            timeout=self.runtime_config.get('request_timeout_sec', 20),
            per_domain_rps=self.runtime_config.get('per_domain_rps', 1.0),
            crawl_manager=self.crawl_manager
        )
        
        self.scorer = ContentScorer(self.embeddings, self.scoring_weights)
        self.exporter = ExcelExporter(self.export_config)
    
    async def discover_websites(self, 
                              demand_text: str, 
                              seed_urls: Optional[List[str]] = None,
                              max_depth: int = None) -> Dict[str, Any]:
        """执行完整的网站发现流程"""
        
        start_time = time.time()
        seed_urls = seed_urls or []
        max_depth = max_depth or self.logic_config.get('max_depth', 2)
        
        print(f"🚀 开始网站发现任务")
        print(f"📝 用户需求: {demand_text}")
        print(f"🌐 种子网站数量: {len(seed_urls)}")
        print(f"📊 最大深度: {max_depth}")
        print()
        
        try:
            # 第1步：统一分析 - 生成搜索查询
            print("🔍 第1步：生成搜索查询...")
            query_result = await self.query_chain.ainvoke({
                "demand_text": demand_text,
                "seed_urls": seed_urls
            })
            
            queries = query_result["queries"]
            coverage_tags = query_result["coverage_tags"]
            print(f"✅ 生成了 {len(queries)} 个搜索查询")
            print(f"📋 覆盖标签: {', '.join(coverage_tags)}")
            print()
            
            if not queries:
                print("❌ 未能生成有效的搜索查询")
                return self._create_empty_result(demand_text, seed_urls, start_time)
            
            # 第2步：并发搜索
            print("🔍 第2步：执行并发搜索...")
            query_strings = [q.query for q in queries]
            search_results = await self.search_manager.search_queries(query_strings, 10)
            print(f"✅ 搜索到 {len(search_results)} 个初始结果")
            print()
            
            if not search_results:
                print("❌ 搜索未返回任何结果")
                return self._create_empty_result(demand_text, seed_urls, start_time)
            
            # 第3步：摘要筛选（基于相似度决定是否抓取详情）
            print("📋 第3步：摘要筛选...")
            filtered_results = await self._filter_by_summary(
                search_results, demand_text, query_strings
            )
            print(f"✅ 筛选后保留 {len(filtered_results)} 个结果进行详情抓取")
            print()
            
            # 第4步：详情抓取
            print("🕷️ 第4步：抓取详情内容...")
            processed_contents = await self.crawler.crawl_urls(filtered_results)
            successful_contents = [c for c in processed_contents if c.content]
            print(f"✅ 成功抓取 {len(successful_contents)} 个页面内容")
            print()
            
            if not successful_contents:
                print("❌ 内容抓取失败，无有效内容")
                return self._create_empty_result(demand_text, seed_urls, start_time)
            
            # 第5步：内容评分
            print("📊 第5步：内容评分...")
            keywords = self._extract_keywords_from_queries(queries)
            scored_contents = await self.scorer.score_contents(
                successful_contents, demand_text, keywords
            )
            print(f"✅ 完成 {len(scored_contents)} 个内容的评分")
            print()
            
            # 第6步：决策标记
            print("✅ 第6步：应用决策阈值...")
            final_contents = self._apply_decision_threshold(scored_contents)
            accepted_count = len([c for c in final_contents if c.decision == 'accepted'])
            print(f"✅ 接受 {accepted_count} 个高质量结果")
            print()
            
            # 第7步：下钻处理（如果需要且深度允许）
            if max_depth > 1:
                print("🔗 第7步：下钻相关链接...")
                final_contents = await self._process_drill_down(
                    final_contents, demand_text, keywords, max_depth
                )
                print(f"✅ 下钻后总计 {len(final_contents)} 个结果")
                print()
            
            # 第8步：导出Excel
            print("📊 第8步：导出Excel报告...")
            execution_time = time.time() - start_time
            
            task_metadata = {
                'execution_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'config_path': self.config_manager.config_path,
                'total_time_seconds': round(execution_time, 2),
                'search_provider': self.config_manager.get_search_config()['provider'],
                'llm_provider': self.config_manager.config['providers']['llm']['provider']
            }
            
            excel_path = self.exporter.export_results(
                final_contents, queries, demand_text, coverage_tags, task_metadata
            )
            
            # 生成简化CSV报告
            csv_path = self.exporter.create_simple_report(final_contents)
            
            print(f"✅ 任务完成！耗时 {execution_time:.2f} 秒")
            print(f"📄 详细报告: {excel_path}")
            print(f"📄 简化报告: {csv_path}")
            
            return {
                'success': True,
                'demand_text': demand_text,
                'seed_urls': seed_urls,
                'queries_generated': len(queries),
                'search_results': len(search_results),
                'successful_crawls': len(successful_contents),
                'accepted_results': accepted_count,
                'total_results': len(final_contents),
                'execution_time': execution_time,
                'excel_path': excel_path,
                'csv_path': csv_path,
                'coverage_tags': coverage_tags,
                'contents': final_contents,
                'queries': queries,
                'task_metadata': task_metadata
            }
            
        except Exception as e:
            print(f"❌ 任务执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'demand_text': demand_text,
                'seed_urls': seed_urls,
                'execution_time': time.time() - start_time
            }
    
    async def _filter_by_summary(self, search_results, demand_text: str, queries: List[str]):
        """基于摘要进行筛选"""
        threshold = self.logic_config.get('detail_threshold', 0.55)
        
        # 简单的文本相似度筛选（基于关键词出现）
        keywords = []
        for query in queries:
            # 提取查询中的关键词（去除操作符）
            clean_query = query.lower()
            for op in ['site:', 'intitle:', 'inurl:', 'filetype:', 'and', 'or', '"', '(', ')', '-']:
                clean_query = clean_query.replace(op, ' ')
            keywords.extend(clean_query.split())
        
        keywords = list(set([kw.strip() for kw in keywords if len(kw.strip()) > 2]))
        
        filtered_results = []
        for result in search_results:
            # 计算摘要中关键词出现比例
            snippet_lower = (result.title + " " + result.snippet).lower()
            matched_keywords = sum(1 for kw in keywords if kw in snippet_lower)
            keyword_ratio = matched_keywords / len(keywords) if keywords else 0
            
            if keyword_ratio >= threshold or matched_keywords >= 3:  # 至少匹配3个关键词
                filtered_results.append(result)
        
        return filtered_results
    
    def _extract_keywords_from_queries(self, queries: List[QueryResult]) -> List[str]:
        """从查询中提取关键词"""
        keywords = []
        for query in queries:
            clean_query = query.query.lower()
            # 移除搜索操作符
            for op in ['site:', 'intitle:', 'inurl:', 'filetype:', 'and', 'or', '"', '(', ')', '-']:
                clean_query = clean_query.replace(op, ' ')
            
            words = [word.strip() for word in clean_query.split() if len(word.strip()) > 2]
            keywords.extend(words)
        
        return list(set(keywords))
    
    def _apply_decision_threshold(self, contents: List[ProcessedContent]) -> List[ProcessedContent]:
        """应用决策阈值"""
        threshold = self.logic_config.get('score_threshold', 0.75)
        
        for content in contents:
            if content.final_score >= threshold:
                content.decision = 'accepted'
                content.explanation = f'高分内容 (评分: {content.final_score:.4f})'
            elif content.final_score >= 0.5:
                content.decision = 'candidate'
                content.explanation = f'候选内容 (评分: {content.final_score:.4f})'
            else:
                content.decision = 'rejected'
                content.explanation = f'低分内容 (评分: {content.final_score:.4f})'
        
        return contents
    
    async def _process_drill_down(self, contents: List[ProcessedContent], 
                                demand_text: str, keywords: List[str], 
                                max_depth: int) -> List[ProcessedContent]:
        """处理下钻链接"""
        if max_depth <= 1:
            return contents
        
        # 选择高分内容进行下钻
        high_score_contents = [c for c in contents if c.final_score > 0.6]
        
        drill_down_urls = []
        max_links = self.logic_config.get('max_links_per_page', 30)
        
        for content in high_score_contents[:5]:  # 限制下钻数量
            relevant_links = []
            for link in content.extracted_links[:max_links]:
                # 简单的相关性判断
                link_lower = link.lower()
                if any(kw in link_lower for kw in keywords[:10]):  # 使用前10个关键词
                    relevant_links.append(link)
            
            drill_down_urls.extend(relevant_links[:5])  # 每页最多5个链接
        
        if not drill_down_urls:
            return contents
        
        print(f"🔗 下钻处理 {len(drill_down_urls)} 个相关链接...")
        
        # 将下钻URL转换为搜索结果格式
        from search_providers import SearchResult
        drill_search_results = []
        for i, url in enumerate(drill_down_urls):
            drill_search_results.append(SearchResult(
                title="",
                url=url,
                snippet="",
                source_query="drill_down",
                rank=i + 1
            ))
        
        # 抓取下钻内容
        drill_contents = await self.crawler.crawl_urls(drill_search_results)
        successful_drill = [c for c in drill_contents if c.content]
        
        if successful_drill:
            # 设置深度标记
            for content in successful_drill:
                content.depth = 1
                content.parent_url = "drill_down"
            
            # 评分
            scored_drill = await self.scorer.score_contents(
                successful_drill, demand_text, keywords
            )
            
            # 应用决策
            final_drill = self._apply_decision_threshold(scored_drill)
            
            # 合并结果
            contents.extend(final_drill)
        
        return contents
    
    def _create_empty_result(self, demand_text: str, seed_urls: List[str], start_time: float) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'success': False,
            'demand_text': demand_text,
            'seed_urls': seed_urls,
            'queries_generated': 0,
            'search_results': 0,
            'successful_crawls': 0,
            'accepted_results': 0,
            'total_results': 0,
            'execution_time': time.time() - start_time,
            'error': 'No results found'
        }