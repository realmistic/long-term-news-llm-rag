import feedparser
import json
import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")


def extract_turbo_content(raw_xml):
    """Extracts turbo:content from the raw XML"""
    try:
        # Parse the raw XML to find the turbo:content tag
        root = ET.fromstring(f"<root>{raw_xml}</root>")  # Wrapping in <root> for safe parsing
        # Find the turbo:content tag (namespace aware)
        turbo_content = root.find('.//{http://turbo.yandex.ru}content')
        if turbo_content is not None:
            # Return the content as a string (without wrapping tags)
            return ET.tostring(turbo_content, encoding='unicode', method='html')
        return None
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None


def parse_rss_to_json(feed_url, output_file_path):
    # Parse the RSS feed
    feed = feedparser.parse(feed_url)

    # Structure the feed data into JSON format
    rss_feed = {
        "meta": {
            "title": feed.feed.title,
            "link": feed.feed.link,
            "description": feed.feed.description,
            "language": feed.feed.language
        },
        "items": []
    }

    # Loop through each item in the feed and add it to the JSON
    for entry in feed.entries:
        # Extract turbo content if available
        turbo_content = extract_turbo_content(entry)
 
        item = {
            "title": entry.title,
            "link": entry.link,
            "pubDate": entry.published,
            "author": entry.author if "author" in entry else None,
            "category": entry.get("category", None),
            "description": entry.description,
            "content": turbo_content,  # Here we add the content field from turbo:content
            "enclosure": {
                "url": entry.enclosures[0].href,
                "type": entry.enclosures[0].type
            } if entry.enclosures else None
        }
        rss_feed["items"].append(item)

    # Convert the structured feed data to JSON string
    rss_feed_json = json.dumps(rss_feed, indent=4)

    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Save the JSON string to a file
    with open(output_file_path, 'w') as json_file:
        json_file.write(rss_feed_json)

    print(f"RSS feed data saved to {output_file_path}")

if __name__ == "__main__":
    # RSS feed URL and output file path
    feed_url = 'https://pythoninvest.com/rss-feed-612566707351.xml'  # Fin news RSS
    output_file_path = 'data/input_news_feed.json'
    
    # Parse and save the RSS feed to a JSON file
    parse_rss_to_json(feed_url, output_file_path)
