# Long-Term News LLM RAG
Analyze long-term trends from weekly news publications.

## Replicate
To replicate the environment and support Jupyter notebooks, follow these steps:

```bash
# Install pipenv
pip install pipenv

# Enter the virtual environment
pipenv shell

# Install ipykernel to support Jupyter notebooks
pipenv install ipykernel

# Also, install this to support Jupyter notebooks
pipenv install notebook jupyterlab 
```

To run a notebook:
```bash
pipenv shell
pipenv run jupyter notebook    
```

## Scripts

The project includes several scripts for data extraction and processing:

### 1. RSS Feed Data Collection (`scripts/01_get_rss_data.py`)
- Fetches initial RSS feed data
- Stores raw feed data for further processing

### 2. Content Data Extraction (`scripts/02_get_content_data_flattened.py`)
- Processes RSS feed entries using GPT-4-mini
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
- Saves data in a flattened Parquet format

To run the content extraction:
```bash
python scripts/02_get_content_data_flattened.py
```

## Data

### Input Data
RSS feed with news (mostly weekly, some weeks are missing)—around 46 weeks or 1 year of data:

- RSS Feed URL: [https://pythoninvest.com/rss-feed-612566707351.xml](https://pythoninvest.com/rss-feed-612566707351.xml)
- This represents the weekly financial news feed section of the website: [https://pythoninvest.com/#weekly-fin-news-feed](https://pythoninvest.com/#weekly-fin-news-feed)

### Output Data
The processed data is saved in Parquet format with the following structure:

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

The data is saved to `data/news_feed_flattened.parquet` using Brotli compression for efficient storage.
