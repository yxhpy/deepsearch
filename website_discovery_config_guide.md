# 网站发现系统配置指南（Search API + LLM/Embedding 可插拔）

目的
- 为“需求→关键词→搜索→摘要筛选→详情评分→下钻→Excel导出”的程序提供统一配置与多提供商切换方式。
- 本指南仅含配置与使用说明（含示例 YAML 与 .env）。

1) 快速开始（建议）
- 运行环境：Windows，Python 3.10+
- 依赖（建议）：langchain, httpx/aiohttp, pandas, openpyxl, faiss-cpu 或 chromadb, tiktoken, pydantic, python-dotenv, playwright(可选)
- 目录建议：
  - 根目录放置 config.yaml 与 .env

2) 核心配置（config.yaml 示例）
providers:
  search:
    provider: bing   # 可选: bing | serpapi | brave
    bing:
      market: zh-CN
      freshness: ""   # 可选: Day/Week/Month
      safeSearch: Moderate
    serpapi:
      engine: google   # 也可用 bing, duckduckgo 等
      location: ""     # 可选
      num: 10
    brave:
      country: CN
      safesearch: moderate
  llm:
    provider: openai  # 可选: openai | azure | ollama
    openai:
      chat_model: gpt-4o-mini
    azure:
      chat_deployment: gpt-4o-mini
    ollama:
      chat_model: qwen2.5:7b
  embedding:
    provider: openai  # 可选: openai | azure | ollama
    openai:
      embed_model: text-embedding-3-large
    azure:
      embed_deployment: text-embedding-3-large
    ollama:
      embed_model: nomic-embed-text
runtime:
  search_concurrency: 20
  crawl_concurrency: 50
  per_domain_rps: 1
  request_timeout_sec: 20
logic:
  max_depth: 2
  max_links_per_page: 30
  detail_threshold: 0.55   # 摘要判定是否进详情
  score_threshold: 0.75    # 满足需求阈值
scoring_weights:
  sim: 0.4
  kw: 0.2
  fresh: 0.15
  domain: 0.15
  structure: 0.1
export:
  excel_path: output.xlsx
  fields: [url,title,snippet,source_query,sim,kw,fresh,domain,structure,score,decision,explanation,http_status,depth,parent,domain_name,lang,render,content_len,hash]

3) 环境变量（.env 示例）
# 搜索
BING_SEARCH_API_KEY=
BING_SEARCH_ENDPOINT=https://api.bing.microsoft.com/v7.0/search
SERPAPI_KEY=
BRAVE_SEARCH_API_KEY=
# LLM/Embedding - OpenAI
OPENAI_API_KEY=
OPENAI_BASE_URL=   # 可留空
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-02-15-preview
# 本地 OLLAMA（可选）
OLLAМА_HOST=http://localhost:11434

提示：未使用的提供商变量可留空；程序按 providers.*.provider 选择。

4) 搜索提供商配置要点
- Bing（Azure Cognitive Services）
  - 必填：BING_SEARCH_API_KEY；endpoint 默认 v7.0。
  - 可选：market、freshness、safeSearch；支持高级搜索语法（site:, intitle:, inurl:, filetype:, AND/OR/()/-）。
- SerpAPI
  - 必填：SERPAPI_KEY；engine 常用 google/bing/duckduckgo。
  - 适合需反爬更强场景；注意速率与费用。
- Brave
  - 必填：BRAVE_SEARCH_API_KEY；参数简洁、响应快；对隐私友好。

5) LLM/Embedding 提供方
- OpenAI
  - OPENAI_API_KEY 必填；chat_model 建议 gpt-4o-mini；embedding 用 text-embedding-3-large。
- Azure OpenAI
  - 需在 Azure 门户创建部署；提供 ENDPOINT/API_VERSION/KEY，配置部署名。
- 本地（Ollama）
  - OLLAMA_HOST 指向本地/远端；chat_model 如 qwen2.5:7b，embedding 用 nomic-embed-text。
  - 成本低，首次拉取模型需时间与磁盘。

6) 并发与限流建议
- search_concurrency=20、crawl_concurrency=50、per_domain_rps=1（遵守 robots 与 TOS）。
- 对 429/5xx 使用指数退避；超时 20s；失败最大重试 3 次（实现层）。

7) 阈值与权重建议
- detail_threshold=0.55（摘要相似度/关键词覆盖判定进详情）。
- score_threshold=0.75（整体判定满足）。
- 默认权重：sim0.4/kw0.2/fresh0.15/domain0.15/structure0.1，可按场景微调。

8) Excel 字段建议
- url,title,snippet,source_query,sim,kw,fresh,domain,structure,score,decision,explanation,http_status,depth,parent,domain_name,lang,render,content_len,hash。

9) 合规与安全
- 遵守 robots.txt 与站点速率限制；合理设置 User-Agent；尊重版权与 API TOS。
- 密钥仅放 .env/环境变量，不写入日志/仓库。

10) FAQ
- 切换提供商：仅改 config.yaml 的 provider，并在 .env 填写对应密钥。
- 仅用本地模型：llm/embedding provider 设为 ollama；未使用的密钥留空。
- 费用控制：减少 query 数量/禁用 JS 渲染/降低并发；分阶段执行（先摘要再详情）。

附：PowerShell 使用示例（示意）
- 设置环境变量：
  $env:OPENAI_API_KEY="your-key"
- 以当前目录 .env 自动加载的方式运行脚本（示意）：
  python .\main.py --config .\config.yaml --input "你的需求" --seeds "https://example.com"