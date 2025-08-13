# 网站发现系统 - Website Discovery System

基于大语言模型的智能网站发现和内容分析系统，采用"一次性分析"的极简架构设计。

## 核心特性

- **🔍 智能查询生成**: 基于需求描述和种子网站，一次性生成多样化的搜索查询（支持高级搜索语法）
- **🌐 多搜索引擎**: 支持 Bing、SerpAPI、Brave 等多个搜索提供商
- **🤖 多LLM支持**: 支持 OpenAI、Azure OpenAI、Ollama 等多种LLM提供商
- **📊 智能评分**: 基于相似度、关键词匹配、新鲜度、域名可信度等多维度评分
- **🕷️ 高效抓取**: 并发内容抓取，支持多种抓取提供商和反机器人检测
- **🔗 下钻分析**: 自动分析相关链接，扩展发现范围
- **📋 Excel导出**: 生成详细的分析报告，包含评分解释和元数据

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

复制环境变量模板并填写API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写相应的API密钥：

```env
# 搜索API（至少配置一个）
BING_SEARCH_API_KEY=your_bing_api_key
SERPAPI_KEY=your_serpapi_key
BRAVE_SEARCH_API_KEY=your_brave_api_key

# LLM API（根据config.yaml中的配置选择）
OPENAI_API_KEY=your_openai_api_key
# 或
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint

# 反机器人抓取服务（可选）
SCRAPINGBEE_API_KEY=your_scrapingbee_key
SCRAPFLY_API_KEY=your_scrapfly_key
BRIGHT_DATA_USERNAME=your_bright_data_username
BRIGHT_DATA_PASSWORD=your_bright_data_password
```

### 3. 基础使用

```bash
# 基础查询
python main.py --input "学习Python机器学习的最佳实践"

# 带种子网站
python main.py --input "React开发教程" --seeds "https://reactjs.org,https://create-react-app.dev"

# 自定义参数
python main.py --input "Vue.js最佳实践" --max-queries 40 --output results.xlsx
```

## 配置说明

### config.yaml 主要配置项

```yaml
providers:
  search:
    provider: bing  # 搜索提供商：bing | serpapi | brave
  llm:
    provider: openai  # LLM提供商：openai | azure | ollama
  embedding:
    provider: openai  # 嵌入模型提供商

crawling:
  provider: native  # 抓取提供商：native | scrapingbee | scrapfly | bright_data

logic:
  max_queries: 60  # 最大生成查询数
  max_depth: 2     # 最大下钻深度
  detail_threshold: 0.55  # 进入详情抓取的阈值
  score_threshold: 0.75   # 接受结果的评分阈值

scoring_weights:  # 评分权重
  sim: 0.4        # 语义相似度
  kw: 0.2         # 关键词匹配
  fresh: 0.15     # 内容新鲜度
  domain: 0.15    # 域名可信度
  structure: 0.1  # 内容结构化程度
```

## 系统架构

### 处理流程

1. **统一分析**: 将需求和种子网站信息输入LLM，一次性生成搜索查询集合
2. **并发搜索**: 并发执行多个搜索查询，获取初始结果
3. **摘要筛选**: 基于标题和摘要进行初步筛选
4. **详情抓取**: 并发抓取页面详细内容
5. **内容评分**: 多维度评分（相似度、关键词、新鲜度等）
6. **决策标记**: 根据阈值标记接受/拒绝/候选
7. **下钻处理**: 分析高分页面的相关链接
8. **Excel导出**: 生成结构化分析报告

### 核心组件

- `unified_query_chain.py`: 统一查询生成链
- `search_providers.py`: 多搜索引擎适配器
- `content_processor.py`: 内容抓取和评分
- `crawling_providers.py`: 多抓取提供商适配器（支持反机器人检测）
- `excel_exporter.py`: Excel报告导出
- `config_manager.py`: 配置管理
- `main.py`: CLI入口程序

## 使用示例

### 1. 学术研究

```bash
python main.py --input "深度学习在自然语言处理中的最新进展" \\
  --seeds "https://arxiv.org,https://paperswithcode.com" \\
  --max-queries 50
```

### 2. 技术调研

```bash
python main.py --input "微服务架构的最佳实践和常见问题" \\
  --seeds "https://microservices.io,https://martin fowler.com" \\
  --max-depth 3
```

### 3. 产品分析

```bash
python main.py --input "CRM系统功能对比和选择指南" \\
  --seeds "https://salesforce.com,https://hubspot.com" \\
  --output crm_analysis.xlsx
```

## 输出说明

系统会生成两类报告：

### 1. Excel详细报告（output.xlsx）

包含多个工作表：
- **分析结果**: 详细的网站分析结果，包含评分和决策
- **搜索查询**: 生成的所有搜索查询及其原因
- **任务概要**: 任务执行摘要和统计信息
- **统计分析**: 评分分布、语言分布等统计图表

### 2. CSV简化报告（output_simple.csv）

包含核心字段的简化版本，便于后续处理。

## 高级用法

### 自定义提供商切换

编辑 `config.yaml`：

```yaml
providers:
  search:
    provider: brave  # 切换到Brave搜索
  llm:
    provider: ollama  # 切换到本地Ollama
    ollama:
      chat_model: qwen2.5:7b

crawling:
  provider: scrapingbee  # 切换到ScrapingBee（支持反机器人）
  # 或使用其他提供商：scrapfly | bright_data | native
```

### 性能优化

```yaml
runtime:
  search_concurrency: 30    # 增加搜索并发
  crawl_concurrency: 100   # 增加抓取并发
  per_domain_rps: 2        # 增加域名请求频率
```

### 评分权重调整

针对不同场景调整评分权重：

```yaml
scoring_weights:
  sim: 0.6        # 更重视语义相似度
  kw: 0.3         # 更重视关键词匹配
  fresh: 0.05     # 降低新鲜度权重
  domain: 0.05    # 降低域名权重
  structure: 0.0  # 忽略结构化程度
```

## 故障排除

### 常见问题

1. **API密钥错误**
   ```
   ❌ OPENAI_API_KEY 环境变量未设置
   ```
   解决：检查 `.env` 文件中的API密钥配置

2. **搜索无结果**
   ```
   ❌ 搜索未返回任何结果
   ```
   解决：检查网络连接，尝试更换搜索提供商

3. **内容抓取失败**
   ```
   ❌ 内容抓取失败，无有效内容
   ```
   解决：检查目标网站是否可访问，尝试切换抓取提供商（如使用 ScrapingBee 或 Scrapfly）

4. **遇到反机器人检测**
   ```
   ❌ 检测到可能的反机器人机制
   ```
   解决：在 `config.yaml` 中将抓取提供商切换为 `scrapingbee`、`scrapfly` 或 `bright_data`

### 调试模式

使用 `--verbose` 参数获取详细执行信息：

```bash
python main.py --input "your query" --verbose
```

## 系统要求

- Python 3.10+
- Windows/Linux/macOS
- 8GB+ RAM（推荐16GB）
- 稳定的网络连接

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

---

**注意**: 使用本系统时请遵守相关网站的robots.txt和服务条款，合理控制请求频率。