import feedparser
import pandas as pd
import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Configuration
feed_url = 'https://pythoninvest.com/rss-feed-612566707351.xml'
output_file_path = 'data/news_feed_flattened.parquet'
MAX_RETRIES = 3
RETRY_DELAY = 5

def llm(prompt, model="gpt-4o-mini"):
    """Function to query the language model with retry mechanism."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            return response
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Attempt {attempt + 1} failed. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Error: {e}")
                return None

def parse_feed_entries(feed_url):
    """Function to parse all entries from the RSS feed and return a DataFrame."""
    feed = feedparser.parse(feed_url)
    all_content = []
    
    # Initialize timing
    total_start_time = time.time()
    
    # Loop through entries with tqdm progress bar
    for entry in tqdm(feed['entries'], desc="Processing entries"):
        entry_start_time = time.time()
        
        # Extract basic details
        turbo_content = entry.get('turbo_content', '')
        entry_link = entry.get('link', '')  # Get the entry link
        
        # Prepare prompt
        prompt_template = '''Expert Web Scraper.

HTML Content: {content}

Perform different types of text extraction:

1) Extract individual news text AS IT IS from given HTML.

HTML Content format:
INDIVIDUAL NEWS SUMMARY
Start date for the articles: <start_date>; End date for the articles: <end_date>
NEWS SUMMARY for (<ticker>, <count>), which changed on <growth>% last trading day:
<text>

You need to extract all fields in <> :
- Date ranges
- mentioned ticker 
- news count
- growth percentage
- news for the ticker

Format:
{{
  "content": [
    {{
      "type": "individual",
      "start_date": <start date for articles>,
      "end_date": <end date for articles>,
      "ticker": <ticker symbol from news>,
      "count": <articles count from news>,
      "growth": <growth %>,
      "text": <news for the ticker from html>
    }},
    // repeat for all news
  ]
}}

2) Extract market news 1 day or 1 week text AS IT IS from given HTML:
HTML Content format:
[<model_name> <period> summary] MARKET NEWS SUMMARY ('multiple_tickers', <news_count> ) -- i.e. <news_count> news summary for the last 24 hours before <end_date> UTC time:

Extract text AS IT IS from given HTML:
- <model_name>
- <period>
- <news_count>
- <news_summary>

Output JSON format:
{{
  "content": [
    {{
      "type": "market_"+<period>,
      "end_date": <end_date>,
      "start_date": <24 hours before end_date>,
      "ticker": "multiple_tickers",
      "count": <news_count>,
      "model": <model_name>,
      "text": <news_summary>
    }}
  ]
}}

Constraints:
Return JSON only.
'''
        
        prompt = prompt_template.format(content=turbo_content)
        
        # Call LLM for extraction and record timing
        extracted_content_start_time = time.time()
        extracted = llm(prompt=prompt)
        extracted_content_end_time = time.time()
        
        if extracted is None:
            continue
            
        try:
            # Convert the LLM response to JSON
            json_str = extracted.choices[0].message.content
            # Clean up any potential JSON formatting
            json_str = json_str.replace("```json", "").replace("```", "")
            data = json.loads(json_str)
            
            # Add the link to each content item
            if "content" in data:
                for item in data["content"]:
                    item["link"] = entry_link  # Add the link to each content item
                all_content.extend(data["content"])
        except Exception as e:
            print(f"Error processing entry: {e}")
            continue
        
        entry_end_time = time.time()
        
        # Display individual timing
        print(f"Time for entry: {entry_end_time - entry_start_time:.2f}s, "
              f"LLM extraction time: {extracted_content_end_time - extracted_content_start_time:.2f}s")

    # Convert all content to DataFrame
    df = pd.DataFrame(all_content)
    
    # Display total processing time
    total_end_time = time.time()
    print(f"Total time for parsing all entries: {total_end_time - total_start_time:.2f}s")
    
    return df

def main():
    # Timing for the entire main function
    main_start_time = time.time()
    
    df = parse_feed_entries(feed_url)
    
    # Ensure consistent data types before saving
    if 'growth' in df.columns:
        # Convert growth to string type, ensuring any None values become empty strings
        df['growth'] = df['growth'].astype(str).replace('None', '')
    
    # Convert list columns to string representation
    list_columns = ['topics', 'key_points', 'companies_mentioned', 'regions_mentioned']
    for col in list_columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x) if x is not None else '')
    
    # Save to Parquet file with Brotli compression
    save_start_time = time.time()
    os.makedirs("data", exist_ok=True)
    df.to_parquet(output_file_path, compression="brotli")
    save_end_time = time.time()
    
    print(f"Data saved to {output_file_path}. Save time: {save_end_time - save_start_time:.2f}s")
    
    main_end_time = time.time()
    print(f"Total execution time: {main_end_time - main_start_time:.2f}s")

if __name__ == "__main__":
    main()
