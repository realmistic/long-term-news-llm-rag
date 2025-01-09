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

## Search Functionality

The project implements text search capabilities using `minsearch`, allowing efficient search across all data fields:

### Searchable Fields
- `type`: News entry type (individual/market)
- `start_date` & `end_date`: Time period of the news
- `ticker`: Company/stock ticker symbols
- `count`: Number of news items
- `growth`: Growth percentage
- `text`: Main news content
- `model`: Model name for market summaries

### Search Features
- Full-text search across all fields
- Field boosting (prioritizes matches in important fields):
  * text (3x boost)
  * type and ticker (2x boost)
  * growth and model (1.5x boost)
  * other fields (1x boost)
- Link-based filtering for source tracking

Example usage in notebooks:
```python
# Basic search
results = search_news("technology growth")

# Search with link filtering
results = search_news("market analysis", link="specific_url")

# Custom field boosting
custom_boost = {
    "ticker": 3,
    "text": 2,
    "type": 1
}
results = search_news("AAPL earnings", boost_dict=custom_boost)
```

## Data

### Input Data
RSS feed with news (mostly weekly, some weeks are missing)—around 55 weeks or 1 year of data (as of Jan-2025):

- RSS Feed URL: [https://pythoninvest.com/rss-feed-612566707351.xml](https://pythoninvest.com/rss-feed-612566707351.xml)
- This represents the weekly financial news feed section of the website: [https://pythoninvest.com/#weekly-fin-news-feed](https://pythoninvest.com/#weekly-fin-news-feed)

### Output Data
The processed data is saved in Parquet format with Brotli compression for efficient storage and fast read performance. The data structure is as follows:

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
    "link": "source_url"
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
    "link": "source_url"
}
```

The data is saved to `data/news_feed_flattened.parquet`. The Brotli compression algorithm is used for its superior compression ratio while maintaining good decompression speed, making it ideal for this type of textual data.
