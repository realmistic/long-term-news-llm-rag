import feedparser
import pandas as pd
import os
import time
import json
import requests
import urllib.request
import argparse
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Initialize the OpenAI client
client = OpenAI()

# Configuration
feed_url = 'https://pythoninvest.com/rss-feed-612566707351.xml'
output_file_path = 'data/news_feed_flattened.parquet'
MAX_RETRIES = 3
RETRY_DELAY = 5

# Set up headers to mimic a browser request
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def llm(prompt, model="gpt-4o-mini"):
    """Function to query the language model with retry mechanism."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.0,
                timeout=5*60,
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

def get_feed_content(feed_url):
    """Function to fetch RSS feed content with fallback mechanisms."""
    feed_content = None
    
    # Create a custom URL opener with headers for feedparser
    opener = urllib.request.build_opener()
    opener.addheaders = [(k, v) for k, v in headers.items()]
    feedparser.USER_AGENT = headers['User-Agent']
    
    # First try with requests
    try:
        response = requests.get(feed_url, headers=headers)
        response.raise_for_status()
        print("Feed content retrieved successfully")
        
        # Parse with feedparser using the raw content
        feed = feedparser.parse(response.text)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            if 'turbo_content' in entry:
                feed_content = entry['turbo_content']
            elif 'content' in entry:
                feed_content = entry['content'][0]['value']
            elif 'description' in entry:
                feed_content = entry['description']
            else:
                feed_content = response.text
    except Exception as e:
        print(f"Error with requests approach: {str(e)}")
    
    # Try direct feedparser approach as fallback
    if feed_content is None:
        try:
            print("Trying direct feedparser approach with custom headers...")
            urllib.request.install_opener(opener)
            feed = feedparser.parse(feed_url)
            
            if len(feed.entries) > 0:
                entry = feed.entries[0]
                if 'turbo_content' in entry:
                    feed_content = entry['turbo_content']
                elif 'content' in entry:
                    feed_content = entry['content'][0]['value']
                elif 'description' in entry:
                    feed_content = entry['description']
        except Exception as e:
            print(f"Error with direct feedparser: {str(e)}")
    
    return feed_content

def parse_feed_entries(feed_url, mode='all'):
    """Function to parse entries from the RSS feed and return a DataFrame."""
    # Create a custom URL opener with headers for feedparser
    opener = urllib.request.build_opener()
    opener.addheaders = [(k, v) for k, v in headers.items()]
    feedparser.USER_AGENT = headers['User-Agent']
    urllib.request.install_opener(opener)
    
    # First try with requests to get raw content
    try:
        response = requests.get(feed_url, headers=headers)
        response.raise_for_status()
        print("Feed content retrieved successfully")
        feed = feedparser.parse(response.text)
    except Exception as e:
        print(f"Error with requests approach: {str(e)}")
        print("Falling back to direct feedparser...")
        feed = feedparser.parse(feed_url)
    
    # Process all entries first to get their dates
    all_entries_data = []
    for entry in feed.entries:
        content = None
        if 'turbo_content' in entry:
            content = entry['turbo_content']
        elif 'content' in entry:
            content = entry['content'][0]['value']
        elif 'description' in entry:
            content = entry['description']
        
        if content:
            # Look for date patterns in content
            import re
            # Pattern 1: Individual news pattern
            date_pattern1 = r'End date for the articles: (\d{4}-\d{2}-\d{2})'
            # Pattern 2: Market news pattern
            date_pattern2 = r'before (\d{4}-\d{2}-\d{2})'
            
            match1 = re.search(date_pattern1, content)
            match2 = re.search(date_pattern2, content)
            
            end_date = None
            if match1:
                end_date = match1.group(1)
            elif match2:
                end_date = match2.group(1)
            
            if end_date:
                all_entries_data.append((entry, end_date))
                print(f"Found entry with date: {end_date}")
    
    # Sort entries by date in descending order (newest first)
    all_entries_data.sort(key=lambda x: x[1], reverse=True)
    print(f"Found {len(all_entries_data)} entries with dates")
    if all_entries_data:
        print(f"Date range: {all_entries_data[-1][1]} to {all_entries_data[0][1]}")
    
    # Get entries based on mode
    if mode == 'last' and all_entries_data:
        # Take the entry with the latest date
        entries = [all_entries_data[0][0]]
        print(f"Processing only the latest entry (date: {all_entries_data[0][1]})")
    elif mode == 'new' and all_entries_data:
        entries = [entry for entry, _ in all_entries_data]  # Process all for new mode, will filter later
        print(f"Number of entries to process for new mode: {len(entries)}")
    else:  # all mode
        entries = [entry for entry, _ in all_entries_data]
        print(f"Processing all {len(entries)} entries")
    
    all_content = []
    total_start_time = time.time()
    
    prompt_template = '''Expert Web Scraper.

HTML Content: {content}

Perform different types of text extraction:

1) Extract individual news text AS IT IS from given HTML.

HTML Content format:
INDIVIDUAL NEWS SUMMARY
Start date for the articles: <start_date>; End date for the articles: <end_date>
NEWS SUMMARY for (<ticker>, <count>), which changed on <growth>% last trading day:
<text>

You need to extract the actual values from the HTML content for each field marked with <>. Do not return placeholder values.
For example, if the HTML contains "Start date for the articles: 2023-07-17; End date for the articles: 2023-07-24", 
use these actual dates in your JSON output, not placeholders like <start_date> or <end_date>.

Required fields to extract:
- Date ranges (in YYYY-MM-DD format)
- Mentioned ticker (actual stock symbol)
- News count (numeric value)
- Growth percentage (numeric value)
- News text (actual news content)

Format:
{{
  "content": [
    {{
      "type": "individual",
      "start_date": "YYYY-MM-DD",  // Use actual date from content
      "end_date": "YYYY-MM-DD",    // Use actual date from content
      "ticker": "SYMBOL",          // Use actual ticker from content
      "count": 123,                // Use actual count from content
      "growth": 12.34,             // Use actual growth % from content
      "text": "actual news text"   // Use actual text from content
    }},
    // repeat for all news items found
  ]
}}

2) Extract market news 1 day or 1 week text AS IT IS from given HTML:
HTML Content format:
[<model_name> <period> summary] MARKET NEWS SUMMARY ('multiple_tickers', <news_count> ) -- i.e. <news_count> news summary for the last 24 hours before <end_date> UTC time:

Extract the actual values for:
- Model name (actual name used)
- Period (actual period mentioned)
- News count (actual numeric value)
- News summary (actual text content)

Output JSON format:
{{
  "content": [
    {{
      "type": "market_"+period,     // Concatenate with actual period value
      "end_date": "YYYY-MM-DD",    // Use actual date from content
      "start_date": "YYYY-MM-DD",  // Calculate 24h before end_date
      "ticker": "multiple_tickers",
      "count": 123,                // Use actual count from content
      "model": "actual_model_name",// Use actual model name from content
      "text": "actual summary"     // Use actual text from content
    }},
  ]
}}

Constraints:
1. Return valid JSON only
2. Use actual values from the content, not placeholders
3. Ensure dates are in YYYY-MM-DD format
4. Ensure numeric values (count, growth) are numbers, not strings
'''
    
    for entry in tqdm(entries, desc="Processing entries"):
        entry_start_time = time.time()
        
        # Extract content from entry
        turbo_content = None
        if 'turbo_content' in entry:
            turbo_content = entry['turbo_content']
        elif 'content' in entry:
            turbo_content = entry['content'][0]['value']
        elif 'description' in entry:
            turbo_content = entry['description']
        
        if not turbo_content:
            print(f"No content found for entry {entry.get('link', 'unknown link')}")
            continue
            
        print(f"\nProcessing entry with link: {entry.get('link', '')}")
        print(f"Content length: {len(turbo_content)}")
        
        entry_link = entry.get('link', '')
        
        prompt = prompt_template.format(content=turbo_content)
        
        extracted_content_start_time = time.time()
        extracted = llm(prompt=prompt)
        extracted_content_end_time = time.time()
        
        if extracted is None:
            continue
            
        try:
            json_str = extracted.choices[0].message.content
            json_str = json_str.replace("```json", "").replace("```", "")
            data = json.loads(json_str)
            
            if "content" in data:
                for item in data["content"]:
                    item["link"] = entry_link
                all_content.extend(data["content"])
        except Exception as e:
            print(f"Error processing entry: {e}")
            continue
        
        entry_end_time = time.time()
        print(f"Time for entry: {entry_end_time - entry_start_time:.2f}s, "
              f"LLM extraction time: {extracted_content_end_time - extracted_content_start_time:.2f}s")

    # Convert to DataFrame and process market data
    df = pd.DataFrame(all_content)
    
    # Convert growth to growth_last_day and divide by 100
    if 'growth' in df.columns:
        df['growth_last_day'] = df['growth'].apply(lambda x: x/100 if pd.notnull(x) else x)
        df = df.drop('growth', axis=1)
    
    total_end_time = time.time()
    print(f"Total time for parsing all entries: {total_end_time - total_start_time:.2f}s")
    
    return df

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process RSS feed data with different modes')
    parser.add_argument('--mode', type=str, choices=['last', 'new', 'all'], default='all',
                      help='Processing mode: last (only latest entry), new (append new entries), all (process all entries)')
    args = parser.parse_args()
    
    main_start_time = time.time()
    
    # Get new data with specified mode
    new_df = parse_feed_entries(feed_url, mode=args.mode)
    
    if args.mode == 'new' and os.path.exists(output_file_path):
        # Append new entries to existing data
        existing_df = pd.read_parquet(output_file_path)
        print(f"Found existing data with {len(existing_df)} entries")
        
        # Get the latest date in existing data
        latest_existing_date = existing_df['end_date'].max()
        print(f"Latest existing date: {latest_existing_date}")
        
        # Filter new data to keep only entries newer than the latest existing date
        new_df = new_df[new_df['end_date'] > latest_existing_date]
        print(f"Found {len(new_df)} new entries to append")
        
        # Combine existing and new data
        new_df = pd.concat([existing_df, new_df], ignore_index=True)
        print(f"Total entries after merge: {len(new_df)}")
    else:
        print(f"Processing {len(new_df)} entries")
    
    # Save to Parquet file with Brotli compression
    save_start_time = time.time()
    os.makedirs("data", exist_ok=True)
    new_df.to_parquet(output_file_path, compression="brotli")
    save_end_time = time.time()
    
    print(f"Data saved to {output_file_path}. Save time: {save_end_time - save_start_time:.2f}s")
    print(f"Final dataset contains {len(new_df)} entries")
    
    main_end_time = time.time()
    print(f"Total execution time: {main_end_time - main_start_time:.2f}s")

if __name__ == "__main__":
    main()
