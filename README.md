# Long-Term News LLM RAG
Analyze long-term trends from weekly news publications.

## Replicate

### Virtual Environment Check
Before setting up, check if you're already in a virtual environment:
```bash
# Check if you're in a virtual environment
pipenv --venv

# If you see a warning about nested environments or an existing path, deactivate:
deactivate

# Now proceed with installation
```

### Installation
To replicate the environment and support Jupyter notebooks, follow these steps:

```bash
# Install pipenv
pip install pipenv

# Enter the virtual environment
pipenv shell

# Install all dependencies from Pipfile
pipenv install
```

## Environment Setup

1. Create a `.env` file in the project root with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

2. To run a notebook:
```bash
pipenv shell
pipenv run jupyter notebook    
```

## Scripts

The project includes several scripts for data extraction and processing:

### 1. RSS Feed Data Collection (`scripts/01_get_rss_data.py`)
- Fetches initial RSS feed data
- Stores raw feed data in JSON format for further processing
- Preserves metadata like title, link, description, and language
- Handles enclosures and optional fields gracefully

### 2. Content Data Extraction (`scripts/02_get_content_data_flattened.py`)
- Processes RSS feed entries using gpt-4o-mini model
- Implements retry mechanism (3 attempts with 5-second delays) for robust API calls
- Tracks processing time for performance monitoring
- Extracts two types of content:
  1. Individual News:
     - Start and end dates
     - Ticker symbol
     - News count
     - Growth percentage
     - News text
  2. Market News (1-day and 1-week summaries):
     - Model name
     - Time period
     - News count
     - Market summary text
- Adds source link to each entry
- Saves data in a flattened Parquet format with Brotli compression for optimal storage efficiency

The script supports three processing modes:
```bash
# Process only the latest entry (newest, since RSS feed is in reverse chronological order)
python scripts/02_get_content_data_flattened.py --mode last

# Add new entries to existing data (incremental updates)
python scripts/02_get_content_data_flattened.py --mode new

# Process all entries (default behavior)
python scripts/02_get_content_data_flattened.py --mode all
```

Note: The RSS feed entries are in reverse chronological order (newest first), so the 'last' mode processes the most recent entry.

### 3. Market Statistics Addition (`scripts/03_add_market_stats.py`)
- Downloads historical market data for individual tickers using yfinance
- Calculates various market metrics:
  * Weekly returns for individual stocks
  * Market daily returns
  * Market weekly returns
  * Growth above market
- Handles both individual stocks and market-wide entries
- Saves enhanced dataset with market metrics in Parquet format

To add market statistics:
```bash
python scripts/03_add_market_stats.py
```

### 4. News Analysis (`scripts/04_answer_one_question.py`)
- Implements RAG (Retrieval-Augmented Generation) for analyzing news and market trends
- Supports both ticker-specific and market-wide analysis
- Features:
  * Custom question support for targeted analysis
  * Comprehensive source documentation
  * Performance metrics integration
  * Market comparison analysis
- Prerequisites:
  * Python packages: langchain, openai, python-dotenv, pandas, faiss-cpu
  * OPENAI_API_KEY environment variable
  * Input file: data/news_feed_with_market_stats.parquet

Usage examples:
```bash
# Ask about specific company (automatically detects ticker)
python scripts/04_answer_one_question.py "What are the latest developments for NVDA?"
python scripts/04_answer_one_question.py "How has Tesla performed in terms of revenue and growth?"

# Ask about specific aspects
python scripts/04_answer_one_question.py "What are NVDA's AI developments and market performance?"
python scripts/04_answer_one_question.py "Tell me about Tesla's manufacturing challenges"

# Hide source documents
python scripts/04_answer_one_question.py "What are NVDA's recent developments?" --show_sources=false
```

Parameters:
- `question`: Required. The question to analyze (e.g., "What are the latest developments for NVDA?")
- `--show_sources`: Optional. Show source documents, defaults to True

The script automatically:
- Detects if the question is about a specific ticker
- Shows chronological analysis with period headers [YYYY-MM-DD..YYYY-MM-DD, +/-X.X% vs market]
- Includes performance metrics and context for each period

## Typical workflow

1. Fetch RSS feed data (optional, as step 2 can fetch directly from the feed)
   ```bash
   python scripts/01_get_rss_data.py
   ```

2. Extract content with desired mode (last/new/all)
   ```bash
   python scripts/02_get_content_data_flattened.py --mode last   # or new/all
   ```

3. Add market statistics
   ```bash
   python scripts/03_add_market_stats.py
   ```

This pipeline transforms raw RSS feed data into a rich dataset with market metrics.

## Experimental Notebooks

The project includes several experimental Jupyter notebooks that demonstrate different approaches to data processing and analysis:

### 1. Local Page Scraping (`notebooks/01_scrape_one_page_locally.ipynb`)
- Demonstrates basic web scraping using local language models through Ollama
- Processes news pages locally without requiring remote API calls
- Note: This approach was not adopted for production due to limitations in extracting structured JSON data, even with larger local models

### 2. GPT-4 Page Scraping (`notebooks/02_scrape_one_page_gpt4o.ipynb`)
- Implements advanced web scraping using GPT-4
- Successfully extracts structured information from news articles
- Serves as the prototype for the production script (02_get_content_data_flattened.py)

### 3. MinSearch Implementation (`notebooks/03_minsearch_from_content.ipynb`)
- Implements a basic search system using minsearch for text-based filtering
- Features include field boosting (text, ticker, growth) and link-based filtering
- Provides simple search functionality across news type, dates, tickers, and content
- Note: This basic implementation was later enhanced in notebook 04

### 4. RAG System (`notebooks/04_RAG_from_content.ipynb`)
- Implements a comprehensive RAG system using LangChain and FAISS for efficient vector-based retrieval
- Features advanced search prioritizing high-performance metrics:
  * Automatic ticker detection from questions
  * Chronological analysis with period headers [YYYY-MM-DD..YYYY-MM-DD, +/-X.X% vs market]
  * Performance metrics and market comparisons
  * Semantic search through FAISS embeddings
- Provides natural language interface:
  * Ask about specific companies (e.g., "What are NVDA's AI developments?")
  * Query particular aspects (e.g., "How has Tesla's manufacturing evolved?")
  * Control source visibility with show_sources parameter
- Represents the final production-ready implementation with the same functionality as the script

### Data Processing Flow
The project processes data through several stages:

1. Raw RSS Data Collection
- Source: Weekly financial news feed (approximately 55 weeks as of Jan-2025)
- RSS Feed URL: [https://pythoninvest.com/rss-feed-612566707351.xml](https://pythoninvest.com/rss-feed-612566707351.xml)
- Web Interface: [https://pythoninvest.com/#weekly-fin-news-feed](https://pythoninvest.com/#weekly-fin-news-feed)
- Output: `data/input_news_feed.json` (from script 01_get_rss_data.py)

2. News Content Extraction
- Input: Raw RSS data
- Processing: Extracts structured information using GPT-4o-mini
- Output: `data/news_feed_flattened.parquet`
- Content: Individual stock news and market summaries

3. Market Statistics Integration
- Input: Processed news data
- Processing: Adds market performance metrics using yfinance
- Final Output: `data/news_feed_with_market_stats.parquet`
- Additional Data: Weekly returns, market comparisons, growth metrics

## Output Data Structure
The final dataset (`data/news_feed_with_market_stats.parquet`) uses Parquet format with Brotli compression and contains:

1. Individual News Entries:
```python
{
    "type": "individual",
    "start_date": "date",
    "end_date": "date",
    "ticker": "symbol",
    "count": number,
    "growth": percentage,
    "text": "news content",
    "link": "source_url",
    "weekly_return": number,
    "market_weekly_return": number,
    "growth_above_market": number
}
```

2. Market News Entries:
```python
{
    "type": "market_[period]",  # period can be "1day" or "1week"
    "end_date": "date",
    "start_date": "date",
    "ticker": "multiple_tickers",
    "count": number,
    "model": "model_name",
    "text": "market summary",
    "link": "source_url",
    "market_weekly_return": number
}
