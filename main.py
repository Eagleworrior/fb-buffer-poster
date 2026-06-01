import os
import sys
import datetime
import requests
import time

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([BUFFER_API_KEY, BUFFER_CHANNEL_ID, NEWS_API_KEY]):
    print("[-] Operational Error: Missing required repository secrets.")
    sys.exit(1)

def fetch_daily_content():
    """Retrieve exactly 10 distinct stories."""
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=10&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("articles", [])
    except Exception as e:
        print(f"[-] Data Retrieval Error: {e}")
        return []

def distribute_to_buffer():
    articles = fetch_daily_content()
    if not articles:
        print("[-] Aborting run: No functional source articles found.")
        return

    print(f"[+] Loaded {len(articles)} items. Sending to Buffer via REST API...")
    
    # Calculate timestamps (Buffer API expects UNIX epoch timestamps)
    # Start 2 hours from now
    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    for index, article in enumerate(articles):
        headline = article.get("title", "Breaking News Update")
        source_link = article.get("url", "")
        post_text = f"{headline}\n\nRead more: {source_link}"
        
        # Calculate time: 2 hours difference per post
        scheduled_time = start_time + datetime.timedelta(hours=index * 2)
        unix_timestamp = int(scheduled_time.timestamp())

        # Buffer v1 REST API endpoint
        url = "https://api.bufferapp.com/1/updates/create.json"
        
        headers = {"Authorization": f"Bearer {BUFFER_API_KEY}"}
        
        data = {
            "profile_ids[]": BUFFER_CHANNEL_ID,
            "text": post_text,
            "scheduled_at": unix_timestamp
        }

        try:
            res = requests.post(url, headers=headers, data=data)
            
            if res.status_code == 200:
                print(f"[+] Post [{index}] successfully queued for: {scheduled_time}")
            else:
                print(f"[-] Buffer rejected post [{index}] (HTTP {res.status_code}): {res.text}")
                
            # Brief pause to stay within API rate limits
            time.sleep(1)
            
        except Exception as e:
            print(f"[-] Connection failure on post [{index}]: {e}")

if __name__ == "__main__":
    distribute_to_buffer()
