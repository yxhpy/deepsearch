"""
统一分析链 - 一次性生成搜索关键词
"""
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain.chains.base import Chain
from langchain.schema import BaseMessage, HumanMessage
from langchain.chat_models.base import BaseChatModel
import asyncio
import aiohttp
from bs4 import BeautifulSoup


class QueryResult(BaseModel):
    """单个查询结果"""
    query: str = Field(description="生成的搜索查询")
    reason: str = Field(description="生成此查询的原因")
    intent_tag: str = Field(description="意图标签")
    operators_used: List[str] = Field(description="使用的高级搜索操作符")


class SeedSummary(BaseModel):
    """种子网站摘要"""
    url: str
    title: str
    domain: str
    lang: str
    snippet: str


class UnifiedQueryGenChain(Chain):
    """统一查询生成链"""
    
    llm: BaseChatModel
    max_queries: int = 60
    allowed_operators: List[str] = ["site", "intitle", "inurl", "filetype", "AND", "OR", "-"]
    language_priority: str = "zh"
    
    @property
    def input_keys(self) -> List[str]:
        return ["demand_text", "seed_urls"]
    
    @property
    def output_keys(self) -> List[str]:
        return ["queries", "coverage_tags"]
    
    @property
    def _chain_type(self) -> str:
        return "unified_query_gen"
    
    def build_prompt(self, demand_text: str, seed_summaries_text: str) -> str:
        """构建完整提示词"""
        operators_str = ", ".join(self.allowed_operators)
        
        prompt = f"""你是一个专业的搜索查询生成专家。根据用户需求和可选的参考网站信息，生成覆盖广度与深度的搜索查询集合。

**任务目标：**
- 根据需求描述和参考网站信息，生成多样化的搜索查询
- 每个查询都应该包含合适的高级搜索语法
- 确保查询覆盖不同的信息维度和获取意图

**约束条件：**
1. 每条查询尽量包含高级语法：{operators_str}
2. 生成多样化查询类型：入门教程、最佳实践、比较评测、官方文档、社区讨论、实战案例、PDF资源等
3. 对参考域名生成定向查询（如 site:example.com intitle:docs "keyword"）
4. 语言优先级：{self.language_priority}
5. 查询数量上限：{self.max_queries}

**输出格式：**
返回JSON格式，包含queries数组和coverage_tags数组，示例：
{{
  "queries": [
    {{
      "query": "具体的搜索查询",
      "reason": "生成此查询的原因", 
      "intent_tag": "意图标签",
      "operators_used": ["使用的操作符列表"]
    }}
  ],
  "coverage_tags": ["覆盖的主题标签列表"]
}}

现在请根据以下信息生成搜索查询：

**用户需求：**
{demand_text}

**参考网站摘要：**
{seed_summaries_text}

请生成JSON格式的搜索查询集合："""
        
        return prompt

    async def _get_seed_summaries(self, seed_urls: List[str]) -> List[SeedSummary]:
        """获取种子网站的轻量摘要"""
        if not seed_urls:
            return []
        
        summaries = []
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = []
            for url in seed_urls:
                tasks.append(self._fetch_seed_summary(session, url))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, SeedSummary):
                    summaries.append(result)
        
        return summaries
    
    async def _fetch_seed_summary(self, session: aiohttp.ClientSession, url: str) -> Optional[SeedSummary]:
        """抓取单个网站的摘要信息"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return None
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 提取标题
                title_tag = soup.find('title')
                title = title_tag.get_text().strip() if title_tag else ""
                
                # 提取首屏文本（前1-2KB）
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                snippet = text[:2000] if text else ""
                
                # 提取域名
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                
                # 检测语言（简单方法）
                lang = "zh" if any('\u4e00' <= c <= '\u9fff' for c in text[:500]) else "en"
                
                return SeedSummary(
                    url=url,
                    title=title,
                    domain=domain,
                    lang=lang,
                    snippet=snippet
                )
                
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """同步调用（实际使用异步）"""
        return asyncio.run(self._acall(inputs))
    
    async def _acall(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """异步调用"""
        demand_text = inputs["demand_text"]
        seed_urls = inputs.get("seed_urls", [])
        
        # 获取种子网站摘要
        seed_summaries = await self._get_seed_summaries(seed_urls)
        
        # 构建摘要文本
        seed_summaries_text = ""
        if seed_summaries:
            seed_summaries_text = "\n".join([
                f"- {summary.domain}: {summary.title}\n  摘要: {summary.snippet[:200]}..."
                for summary in seed_summaries
            ])
        else:
            seed_summaries_text = "无参考网站"
        
        # 构建提示词
        prompt = self.build_prompt(demand_text, seed_summaries_text)
        
        # 调用LLM
        messages = [HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        
        # 解析响应
        try:
            # 处理可能被代码块包装的JSON响应
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]  # 移除 ```json
            if content.endswith("```"):
                content = content[:-3]  # 移除 ```
            content = content.strip()
            
            # 分离JSON部分和额外文本
            lines = content.split('\n')
            json_lines = []
            found_end = False
            brace_count = 0
            
            for line in lines:
                if not found_end:
                    json_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and '{' in ''.join(json_lines):
                        found_end = True
                        break
            
            json_content = '\n'.join(json_lines)
            
            result = json.loads(json_content)
            queries = [QueryResult(**q) for q in result.get("queries", [])]
            coverage_tags = result.get("coverage_tags", [])
            
            return {
                "queries": queries,
                "coverage_tags": coverage_tags,
                "seed_summaries": seed_summaries
            }
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Response: {response.content}")
            return {"queries": [], "coverage_tags": [], "seed_summaries": seed_summaries}


# 工厂函数
def create_unified_query_chain(llm: BaseChatModel, config: Dict[str, Any]) -> UnifiedQueryGenChain:
    """创建统一查询生成链"""
    logic_config = config.get("logic", {})
    
    return UnifiedQueryGenChain(
        llm=llm,
        max_queries=logic_config.get("max_queries", 60),
        allowed_operators=logic_config.get("allowed_operators", ["site", "intitle", "inurl", "filetype", "AND", "OR", "-"]),
        language_priority=logic_config.get("language_priority", "zh")
    )