# 网站发现系统 - 极简架构与“一次性分析”方案

目的
- 将“需求描述 + 参考网站链接”一次性交给大模型分析，直接产出可执行的搜索关键词（含高级语法），减少流程分段，提升易用性。
- 在保持后续链路（并发搜索 → 摘要判定进详情 → 详情评分 → 下钻 → Excel导出）不变的前提下，简化前置环节。

适用场景
- 你不想区分“需求拆解”和“种子网站关键词提取”的两段式处理，希望一步完成“搜索关键词生成”。

1) 极简流程总览
1. 输入：需求文本 + 可选参考网站 URL 列表
2. LLM 统一分析：读取需求与参考网站的“轻量内容”（见下），一次性生成多组搜索关键词（含 site:/intitle:/inurl:/filetype:/OR/AND/()- 等高级语法）
3. 异步搜索：并发提交查询到选定的搜索提供商（Bing/SerpAPI/Brave）
4. 摘要筛选：基于标题/摘要与需求的相似度与关键词覆盖，决定是否进详情
5. 详情抓取 + 评分：抓取正文，按“相似度/关键词覆盖/新鲜度/域名信任/结构化程度”混合打分
6. 下钻：对正文里潜在相关链接进行分析（深度≤D），重复第5步，直到无新增候选
7. Excel 导出：输出结构化结果（含评分解释与可追溯元数据）

2) 统一分析链（LangChain）设计
为保证“一次性分析”仍然有效，建议对参考网站做“轻量抓取”，仅取：
- 标题（<title>）
- 首屏正文摘要（例如前 1-2KB 纯文本，去脚本与样式）
- 页面语言与域名
这样既能给 LLM 足够上下文，又避免高成本。

输入
- demand_text: string（必填）
- seed_urls: string[]（可选）
- seed_url_summaries: { url, title, domain, lang, snippet }[]（系统自动生成，给到 LLM）
- config: { max_queries, allowed_operators, language_priority }

输出（建议 JSON Lines 或结构化列表）
- queries: [{ query: string, reason: string, intent_tag: string, operators_used: string[] }]
- coverage_tags: string[]（例如："入门教程"、"最佳实践"、"API认证"、"实战案例"）

提示词模板（示意）
- 目标：根据“需求描述 + 若干参考网页的标题与摘要”，产出覆盖广度与深度的搜索查询集合。
- 约束：
  - 每条查询尽量包含高级语法（site:, intitle:, inurl:, filetype:, OR/AND/()/-）
  - 生成多样化查询（入门/教程/最佳实践/比较/评测/PDF/官方文档/社区/案例）
  - 对参考域名生成若干定向查询（如 site:example.com intitle:docs “keyword”）
  - 语言优先级：{language_priority}
  - 数量上限：{max_queries}
- 输出：JSON 数组，每项含 {query, reason, intent_tag, operators_used}

3) 配置映射（沿用你现有的配置指南）
- 搜索与 LLM/Embedding 提供商：保持与《website_discovery_config_guide.md》一致，通过 config.yaml 切换。
- 新增/重点参数：
  - logic.max_queries：一次性生成的查询上限（如 60）
  - logic.allowed_operators：允许的高级语法列表（如 ["site","intitle","inurl","filetype","AND","OR","-"]）
  - logic.language_priority：优先语言（zh/en）
- 并发、阈值、评分权重、Excel 字段：与原指南一致，无需修改。

4) 运行与行为（示意）
- 在实际实现中，统一分析链处理逻辑为：
  1) 对 seed_urls 执行轻量抓取（仅标题+首屏摘要），失败不阻塞主流程
  2) 将 demand_text + seed_url_summaries 一并输入到一个 LangChain Chain 中
  3) Chain 输出去重后的查询集（含高级语法与多样性标签）
  4) 对 queries 并发搜索，进入后续筛选/评分/下钻/导出

PowerShell 运行示例（伪命令，仅示范 CLI 形态）：
  python .\main.py --config .\config.yaml --input "你的需求" --seeds "https://example.com,https://another.com" --max-queries 60

5) 质量与成本注意事项
- 大模型上下文长度：将 seed_url_summaries 控制在简短摘要，避免超长 prompt 导致费用与时延上升
- 多样性控制：在提示词中明确覆盖“入门/教程/最佳实践/案例/官方文档/社区/PDF”等意图标签
- 费用控制：
  - 限制 max_queries（建议 40~80）
  - 优先摘要筛选，减少详情抓取比例
  - 对强 JS 站点才启用渲染；渲染比例≤20%

6) 失败与降级策略（与原指南一致）
- 搜索/抓取失败：指数退避+域名节流，最大重试 3 次
- 429/403：降速与临时黑名单
- 超时：优先静态抓取，必要时再渲染

7) Excel 字段与审计（与原指南一致）
- Excel 字段建议：url,title,snippet,source_query,sim,kw,fresh,domain,structure,score,decision,explanation,http_status,depth,parent,domain_name,lang,render,content_len,hash
- 审计日志保留：任务参数、查询集合、外部调用摘要、评分解释与来源链路

8) 何时需要回到两段式？
- 若某些场景下“一次性分析”覆盖不足（如大量行业术语、跨域多主题），可切换为两段式：
  - 先生成“通用查询集”，再对种子站点执行定向扩充（但可通过两个 Chain 串联而非大量自定义代码）

9) 与现有《配置指南》的关系
- 本文只更改“关键词生成”的策略为“一次性分析”链，其他配置（多搜索提供商、OpenAI/Azure/Ollama 切换、并发与阈值、Excel 字段等）全部沿用现有指南。
- 你只需在实现时将 Chain 切换为“UnifiedQueryGenChain”（名称可自定义）。

10) 下一步建议
- 若你需要，我可以：
  - 在当前目录初始化最小可运行的 MVP（含 UnifiedQueryGenChain）
  - 产出 config.yaml 与 .env.example 模板
  - 提供关键 Prompt 与 Chain 伪代码/函数签名