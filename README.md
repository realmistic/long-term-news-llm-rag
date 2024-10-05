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

# Data

RSS feed with news (mostly weekly, some weeks are missing)—around 46 weeks or 1 year of data:

- RSS Feed URL: [https://pythoninvest.com/rss-feed-612566707351.xml](https://pythoninvest.com/rss-feed-612566707351.xml)
- This represents the weekly financial news feed section of the website: [https://pythoninvest.com/#weekly-fin-news-feed](https://pythoninvest.com/#weekly-fin-news-feed)
