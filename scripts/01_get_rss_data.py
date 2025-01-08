import feedparser
import json
import os
import requests
import urllib.request
import time

def parse_rss_to_json(feed_url, output_file_path, max_retries=3, retry_delay=5):
    # Set up headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # Create a custom URL opener with headers for feedparser
    opener = urllib.request.build_opener()
    opener.addheaders = [(k, v) for k, v in headers.items()]
    feedparser.USER_AGENT = headers['User-Agent']

    feed_content = None
    
    # First try with requests to get raw content
    for attempt in range(max_retries):
        try:
            response = requests.get(feed_url, headers=headers)
            response.raise_for_status()
            print("Feed content retrieved successfully")
            print("Content length:", len(response.text))
            
            # Parse with feedparser using the raw content
            feed = feedparser.parse(response.text)
            feed_content = feed
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                print(f"Error: {str(e)}")
                time.sleep(retry_delay)
            else:
                print("Trying direct feedparser approach as fallback...")
                try:
                    # Install our custom opener
                    urllib.request.install_opener(opener)
                    feed = feedparser.parse(feed_url)
                    feed_content = feed
                except Exception as e:
                    print(f"Error with direct feedparser: {str(e)}")
                    raise Exception("Failed to fetch RSS feed after all attempts")

    if feed_content is None:
        raise Exception("No feed content available to process")

    # Structure the feed data into JSON format
    rss_feed = {
        "meta": {
            "title": feed_content.feed.get('title', ''),
            "link": feed_content.feed.get('link', ''),
            "description": feed_content.feed.get('description', ''),
            "language": feed_content.feed.get('language', '')
        },
        "items": []
    }

    # Loop through each item in the feed and add it to the JSON
    for entry in feed_content.entries:
        item = {
            "title": entry.get('title', ''),
            "link": entry.get('link', ''),
            "pubDate": entry.get('published', ''),
            "author": entry.get('author', None),
            "category": entry.get('category', None),
            "description": entry.get('description', ''),
            "content": entry.get('turbo_content', entry.get('content', [{'value': ''}])[0].get('value') if 'content' in entry else ''),
            "enclosure": {
                "url": entry.get('enclosures', [{}])[0].get('href', ''),
                "type": entry.get('enclosures', [{}])[0].get('type', '')
            } if entry.get('enclosures') else None
        }
        rss_feed["items"].append(item)

    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Save the JSON string to a file
    with open(output_file_path, 'w') as json_file:
        json.dump(rss_feed, json_file, indent=4)

    print(f"RSS feed data saved to {output_file_path}")
    print(f"Number of items processed: {len(rss_feed['items'])}")

if __name__ == "__main__":
    # RSS feed URL and output file path
    feed_url = 'https://pythoninvest.com/rss-feed-612566707351.xml'  # Fin news RSS
    output_file_path = 'data/input_news_feed.json'
    
    # Parse and save the RSS feed to a JSON file
    parse_rss_to_json(feed_url, output_file_path)
