"""
系统测试脚本 - 验证各组件功能
"""
import asyncio
import os
from config_manager import ConfigManager
from unified_query_chain import create_unified_query_chain


async def test_config_loading():
    """测试配置加载"""
    print("🔧 测试配置加载...")
    try:
        config_manager = ConfigManager("config.yaml")
        print(f"✅ 配置文件加载成功")
        
        # 测试搜索配置
        search_config = config_manager.get_search_config()
        print(f"📊 搜索提供商: {search_config['provider']}")
        
        # 测试逻辑配置
        logic_config = config_manager.get_logic_config()
        print(f"🔍 最大查询数: {logic_config.get('max_queries', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


async def test_llm_connection():
    """测试LLM连接"""
    print("\n🤖 测试LLM连接...")
    try:
        config_manager = ConfigManager("config.yaml")
        llm = config_manager.get_llm()
        
        # 简单测试
        from langchain.schema import HumanMessage
        response = await llm.ainvoke([HumanMessage(content="Hello, please respond with 'Test successful'")])
        print(f"✅ LLM响应: {response.content[:100]}")
        return True
        
    except Exception as e:
        print(f"❌ LLM连接失败: {e}")
        print(f"💡 请检查API密钥配置和网络连接")
        return False


async def test_query_generation():
    """测试查询生成"""
    print("\n🔍 测试查询生成...")
    try:
        config_manager = ConfigManager("config.yaml")
        llm = config_manager.get_llm()
        query_chain = create_unified_query_chain(llm, config_manager.config)
        
        # 测试查询生成
        result = await query_chain.ainvoke({
            "demand_text": "Python机器学习入门教程",
            "seed_urls": []
        })
        
        queries = result["queries"]
        coverage_tags = result["coverage_tags"]
        
        print(f"✅ 生成查询数量: {len(queries)}")
        print(f"📋 覆盖标签: {', '.join(coverage_tags)}")
        
        if queries:
            print(f"📝 示例查询: {queries[0].query}")
            
        return len(queries) > 0
        
    except Exception as e:
        print(f"❌ 查询生成失败: {e}")
        return False


async def test_search_provider():
    """测试搜索提供商"""
    print("\n🌐 测试搜索提供商...")
    try:
        config_manager = ConfigManager("config.yaml")
        from search_providers import create_search_provider
        
        search_provider = create_search_provider(config_manager.get_search_config())
        
        # 测试简单搜索
        results = await search_provider.search("Python tutorial", max_results=3)
        
        print(f"✅ 搜索结果数量: {len(results)}")
        if results:
            print(f"📝 示例结果: {results[0].title}")
            
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")
        print(f"💡 请检查搜索API密钥配置")
        return False


async def test_full_mini_pipeline():
    """测试完整的迷你流水线"""
    print("\n🚀 测试完整迷你流水线...")
    try:
        from website_discovery import WebsiteDiscoveryEngine
        
        # 创建临时配置，减少资源使用
        engine = WebsiteDiscoveryEngine("config.yaml")
        
        # 覆盖配置以减少测试时间
        engine.logic_config['max_queries'] = 5
        engine.logic_config['max_depth'] = 1
        engine.runtime_config['search_concurrency'] = 3
        engine.runtime_config['crawl_concurrency'] = 5
        
        # 执行测试
        result = await engine.discover_websites(
            demand_text="Python基础教程",
            seed_urls=[],
            max_depth=1
        )
        
        if result['success']:
            print(f"✅ 流水线测试成功")
            print(f"📊 生成查询: {result['queries_generated']}")
            print(f"🌐 搜索结果: {result['search_results']}")
            print(f"🕷️ 成功抓取: {result['successful_crawls']}")
            print(f"✅ 接受结果: {result['accepted_results']}")
            return True
        else:
            print(f"❌ 流水线测试失败: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 流水线测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🧪 网站发现系统 - 系统测试")
    print("=" * 50)
    
    # 检查环境变量
    print("🔐 检查环境变量...")
    env_vars = ['OPENAI_API_KEY', 'BING_SEARCH_API_KEY', 'SERPAPI_KEY', 'BRAVE_SEARCH_API_KEY']
    found_keys = []
    for var in env_vars:
        if os.getenv(var):
            found_keys.append(var)
    
    if found_keys:
        print(f"✅ 找到API密钥: {', '.join(found_keys)}")
    else:
        print(f"⚠️  未找到任何API密钥，某些测试可能失败")
    
    # 运行测试
    tests = [
        ("配置加载", test_config_loading),
        ("LLM连接", test_llm_connection),
        ("查询生成", test_query_generation),
        ("搜索提供商", test_search_provider),
        ("完整流水线", test_full_mini_pipeline)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断测试")
            break
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果摘要
    print("\n" + "=" * 50)
    print("📊 测试结果摘要")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📈 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统运行正常。")
    elif passed > 0:
        print("⚠️  部分测试失败，请检查配置和网络连接。")
    else:
        print("❌ 所有测试失败，请检查系统配置。")
    
    print("\n💡 如需运行完整测试，请使用:")
    print("   python main.py --input \"测试查询\" --max-queries 10")


if __name__ == "__main__":
    asyncio.run(main())