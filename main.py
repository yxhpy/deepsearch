"""
网站发现系统 - CLI入口
"""
import argparse
import asyncio
import sys
import os
from typing import List, Optional
from website_discovery import WebsiteDiscoveryEngine

# 设置编码
if sys.platform == 'win32':
    # Windows 下设置控制台编码
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


def parse_seed_urls(seeds_str: str) -> List[str]:
    """解析种子URL字符串"""
    if not seeds_str:
        return []
    
    urls = [url.strip() for url in seeds_str.split(',')]
    return [url for url in urls if url]


def validate_config_file(config_path: str) -> bool:
    """验证配置文件是否存在"""
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    return True


def validate_env_file() -> bool:
    """检查环境变量文件"""
    if not os.path.exists('.env'):
        print("⚠️  未找到 .env 文件，请确保API密钥已通过其他方式设置")
        print("💡 建议复制 .env.example 为 .env 并填写相应的API密钥")
        return True  # 不强制要求.env文件存在
    return True


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='网站发现系统 - 基于需求描述自动发现和分析相关网站',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 基础用法
  python main.py --input "学习Python机器学习的最佳实践"
  
  # 带种子网站
  python main.py --input "React开发教程" --seeds "https://reactjs.org,https://create-react-app.dev"
  
  # 自定义配置
  python main.py --config myconfig.yaml --input "Vue.js最佳实践" --max-queries 40 --output results.xlsx

注意事项:
  1. 确保已安装所有依赖: pip install -r requirements.txt
  2. 配置API密钥在 .env 文件中
  3. 根据需要修改 config.yaml 中的提供商设置
        '''
    )
    
    # 必需参数
    parser.add_argument(
        '--input', 
        required=True,
        help='需求描述文本（必需）'
    )
    
    # 可选参数
    parser.add_argument(
        '--config', 
        default='config.yaml',
        help='配置文件路径（默认: config.yaml）'
    )
    
    parser.add_argument(
        '--seeds',
        help='种子网站URL列表，用逗号分隔（可选）'
    )
    
    parser.add_argument(
        '--max-queries',
        type=int,
        help='最大查询数量（覆盖配置文件设置）'
    )
    
    parser.add_argument(
        '--max-depth',
        type=int,
        help='最大下钻深度（覆盖配置文件设置）'
    )
    
    parser.add_argument(
        '--output',
        help='输出Excel文件路径（覆盖配置文件设置）'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细信息'
    )
    
    args = parser.parse_args()
    
    # 验证配置文件
    if not validate_config_file(args.config):
        sys.exit(1)
    
    # 检查环境文件
    validate_env_file()
    
    # 解析种子URLs
    seed_urls = parse_seed_urls(args.seeds) if args.seeds else []
    
    try:
        # 打印启动信息
        print("=" * 60)
        print("🌐 网站发现系统 - Website Discovery System")
        print("=" * 60)
        print(f"📝 需求描述: {args.input}")
        print(f"⚙️  配置文件: {args.config}")
        if seed_urls:
            print(f"🌐 种子网站: {len(seed_urls)} 个")
            if args.verbose:
                for url in seed_urls:
                    print(f"  - {url}")
        print(f"🔍 详细模式: {'开启' if args.verbose else '关闭'}")
        print("=" * 60)
        print()
        
        # 创建发现引擎
        engine = WebsiteDiscoveryEngine(config_path=args.config)
        
        # 应用命令行参数覆盖
        if args.max_queries:
            engine.logic_config['max_queries'] = args.max_queries
            print(f"🔧 覆盖最大查询数: {args.max_queries}")
        
        if args.max_depth:
            engine.logic_config['max_depth'] = args.max_depth
            print(f"🔧 覆盖最大深度: {args.max_depth}")
        
        if args.output:
            engine.export_config['excel_path'] = args.output
            print(f"🔧 覆盖输出路径: {args.output}")
        
        if args.max_queries or args.max_depth or args.output:
            print()
        
        # 执行网站发现
        result = await engine.discover_websites(
            demand_text=args.input,
            seed_urls=seed_urls,
            max_depth=args.max_depth
        )
        
        # 输出结果摘要
        print()
        print("=" * 60)
        print("📊 执行摘要")
        print("=" * 60)
        
        if result['success']:
            print(f"✅ 任务状态: 成功")
            print(f"⏱️  执行时间: {result['execution_time']:.2f} 秒")
            print(f"🔍 生成查询: {result['queries_generated']} 个")
            print(f"🌐 搜索结果: {result['search_results']} 个")
            print(f"🕷️ 成功抓取: {result['successful_crawls']} 个")
            print(f"✅ 接受结果: {result['accepted_results']} 个")
            print(f"📋 总计结果: {result['total_results']} 个")
            
            if 'coverage_tags' in result and result['coverage_tags']:
                print(f"🏷️  覆盖标签: {', '.join(result['coverage_tags'])}")
            
            if 'excel_path' in result:
                print(f"📄 详细报告: {result['excel_path']}")
            
            if 'csv_path' in result:
                print(f"📄 简化报告: {result['csv_path']}")
            
            # 详细信息输出
            if args.verbose and 'contents' in result:
                print()
                print("🔍 高分结果预览:")
                high_score_contents = [c for c in result['contents'] if c.final_score > 0.7]
                for i, content in enumerate(high_score_contents[:5], 1):
                    print(f"  {i}. [{content.final_score:.3f}] {content.title}")
                    print(f"     {content.url}")
                    print(f"     决策: {content.decision}")
                    print()
        
        else:
            print(f"❌ 任务状态: 失败")
            print(f"⏱️  执行时间: {result['execution_time']:.2f} 秒")
            if 'error' in result:
                print(f"❌ 错误信息: {result['error']}")
        
        print("=" * 60)
        
        # 根据结果设置退出码
        sys.exit(0 if result['success'] else 1)
        
    except KeyboardInterrupt:
        print("\n❌ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 系统异常: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_sync():
    """同步运行入口（用于打包）"""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())