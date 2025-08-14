#!/usr/bin/env python3
"""
测试Playwright爬虫提供商
"""
import asyncio
import sys
from crawling_providers import PlaywrightCrawlProvider

async def test_playwright():
    """测试Playwright爬虫功能"""
    print("开始测试Playwright爬虫提供商...")
    
    # 配置
    config = {
        'headless': True,
        'timeout': 30000,
        'wait_for_load': True,
        'wait_time': 2000,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # 创建Playwright提供商
    provider = PlaywrightCrawlProvider(config)
    
    # 测试URL列表
    test_urls = [
        'https://httpbin.org/html',  # 简单HTML页面
        'https://httpbin.org/json',  # JSON响应
        'https://example.com',       # 基础网站
    ]
    
    for url in test_urls:
        print(f"\n测试URL: {url}")
        try:
            result = await provider.fetch_url(url)
            
            if result.success:
                print(f"✅ 成功: 状态码 {result.status_code}")
                print(f"   最终URL: {result.final_url}")
                print(f"   内容长度: {len(result.html)} 字符")
                if len(result.html) > 100:
                    print(f"   内容预览: {result.html[:100]}...")
                else:
                    print(f"   内容: {result.html}")
            else:
                print(f"❌ 失败: {result.error}")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(test_playwright())