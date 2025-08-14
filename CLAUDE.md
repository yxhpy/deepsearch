


/# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Setup and Installation
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env file with API keys before running
```

### Running the System
```bash
# Basic usage
python main.py --input "your search requirement"

# With seed websites
python main.py --input "requirement" --seeds "https://site1.com,https://site2.com"

# Custom parameters
python main.py --input "requirement" --max-queries 40 --max-depth 3 --output results.xlsx

# Verbose mode for debugging
python main.py --input "requirement" --verbose
```

### Testing and Validation
```bash
# Run system health check
python test_system.py

# Quick example using Windows batch
run_example.bat
```

## Core Architecture

### Processing Pipeline
The system follows an 8-step "one-shot analysis" pipeline:
1. **Unified Analysis** - LLM generates diverse search queries from requirements + seed sites
2. **Concurrent Search** - Parallel execution across multiple search providers
3. **Summary Filtering** - Filter based on title/snippet relevance
4. **Content Crawling** - Concurrent page content extraction
5. **Multi-dimensional Scoring** - Score on similarity, keywords, freshness, domain trust, structure
6. **Decision Marking** - Apply thresholds to accept/reject/candidate results
7. **Drill-down Processing** - Analyze high-score page links recursively
8. **Excel Export** - Generate structured analysis reports

### Key Components

**unified_query_chain.py** - `UnifiedQueryGenChain`
- Core "one-shot analysis" component that takes requirements + optional seed URLs
- Generates diverse search queries with advanced operators (site:, intitle:, etc.)
- Uses lightweight web scraping (title + first-screen content) for seed URL analysis
- Returns structured query list with intent tags and reasoning

**config_manager.py** - `ConfigManager`  
- Handles config.yaml loading and provider initialization
- Supports multiple LLM providers (OpenAI, Azure OpenAI, Ollama)
- Manages search providers (Bing, SerpAPI, Brave) and embedding models

**search_providers.py** - Search provider abstractions
- `BaseSearchProvider` with implementations for Bing, SerpAPI, Brave
- `ConcurrentSearchManager` handles parallel query execution with rate limiting
- Each provider has specific API parameter mapping

**content_processor.py** - Content analysis pipeline  
- `ContentCrawler` - Concurrent web scraping with domain-level rate limiting and anti-bot mechanisms
- `ContentScorer` - Multi-dimensional scoring system with configurable weights
- Handles similarity calculation, keyword matching, freshness, domain trust, structure analysis

**crawling_providers.py** - Enhanced crawling with anti-bot support
- `BaseCrawlProvider` with implementations for native, ScrapingBee, Scrapfly, Bright Data
- `EnhancedCrawlManager` with automatic fallback from external providers to native crawler
- Factory pattern for easy provider switching and configuration-based selection

**website_discovery.py** - `WebsiteDiscoveryEngine`
- Main orchestrator that coordinates the 8-step pipeline
- Manages component initialization and configuration overrides
- Handles error recovery and result aggregation

### Configuration System

**config.yaml structure:**
- `providers` - LLM, embedding, and search provider configurations
- `runtime` - Concurrency, timeout, and rate limiting settings  
- `crawling` - Crawling provider configuration (native/scrapingbee/scrapfly/bright_data)
- `logic` - Query limits, depth, thresholds, allowed operators
- `scoring_weights` - Multi-dimensional scoring weights (sim/kw/fresh/domain/structure)
- `export` - Output path and field configurations

**Environment variables:**
- Search APIs: `BING_SEARCH_API_KEY`, `SERPAPI_KEY`, `BRAVE_SEARCH_API_KEY`, `SERPER_API_KEY`
- LLM APIs: `OPENAI_API_KEY` or Azure equivalents
- Optional: `OLLAMA_HOST` for local models
- Anti-bot services: `SCRAPINGBEE_API_KEY`, `SCRAPFLY_API_KEY`, `BRIGHT_DATA_USERNAME`, `BRIGHT_DATA_PASSWORD`

### Scoring System
Five-dimensional scoring with configurable weights:
- **Similarity (0.4)** - Semantic similarity via embeddings
- **Keywords (0.2)** - Keyword match ratio
- **Freshness (0.15)** - Based on URL date patterns  
- **Domain (0.15)** - Trust score for domain (.edu/.gov higher)
- **Structure (0.1)** - Content organization (headers, lists, code blocks)

### Error Handling Patterns
- Search failures: Exponential backoff with max 3 retries
- Rate limiting: Per-domain RPS enforcement with adaptive delays
- Content extraction: Graceful degradation for failed crawls with anti-bot detection
- Provider switching: Automatic fallback between search providers and crawling providers
- Anti-bot measures: Random user agents, referer rotation, captcha detection, request timing randomization

## Development Notes

### LangChain Integration Issues
The system uses LangChain Chains but avoids field name conflicts. If you see `NameError: Field name "input_keys" shadows a BaseModel attribute`, the Chain class needs to override the property methods rather than declare as class attributes.

### Adding New Providers
Search providers implement `BaseSearchProvider.search()` method. Each needs specific parameter mapping for their API format. See existing implementations for patterns.

Crawling providers implement `BaseCrawlProvider.fetch_url()` method. The system supports native crawling with enhanced anti-bot capabilities, or external services like ScrapingBee, Scrapfly, and Bright Data for advanced anti-bot bypassing.

### Performance Tuning
Key parameters in config.yaml:
- `runtime.search_concurrency` - Search request parallelism (default: 20)
- `runtime.crawl_concurrency` - Content extraction parallelism (default: 50)  
- `runtime.per_domain_rps` - Domain-level rate limiting (default: 1.0)
- `logic.detail_threshold` - Summary filtering threshold (default: 0.55)
- `logic.score_threshold` - Final acceptance threshold (default: 0.75)
- `crawling.provider` - Crawling provider selection (native/scrapingbee/scrapfly/bright_data)

### Output Analysis
Excel reports contain multiple worksheets:
- Analysis results with full scoring breakdown
- Query generation details with intent tags
- Task summary and statistics
- Score/language/status distributions
CSV reports provide simplified key fields for further processing.