import os
import sys
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load secrets
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([BUFFER_API_KEY, BUFFER_CHANNEL_ID, NEWS_API_KEY]):
    print("[-] Error: Missing required secrets.")
    sys.exit(1)

# Configure Session with Smart Retries
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1, 
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def fetch_daily_content():
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json().get("articles", [])
    except Exception as e:
        print(f"[-] News Fetch Error: {e}")
        return []

def send_to_buffer():
    articles = fetch_daily_content()
    if not articles:
        print("[-] No content found.")
        return

    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """

    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    for index, article in enumerate(articles):
        title = article.get("title", "Breaking News")
        snippet = article.get("content") or article.get("description") or ""
        
        # Updated Text Format: Title + Snippet + Your Blogger Link
        post_text = f"{title}\n\n{snippet}\n\nRead more: https://appsupdatess.blogspot.com"
        
        image_url = article.get("urlToImage")
        
        scheduled_time = start_time + datetime.timedelta(hours=index * 2)
        due_at = scheduled_time.isoformat(timespec='milliseconds').replace("+00:00", "Z")

        input_data = {
            "channelId": BUFFER_CHANNEL_ID,
            "text": post_text,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at,
            "metadata": {"facebook": {"type": "post"}}
        }

        if image_url:
            input_data["assets"] = [{"image": {"url": image_url}}]

        # Send via session (only retries if 429/5xx occurs)
        payload = {"query": mutation, "variables": {"input": input_data}}
        response = session.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"[+] Post {index} queued successfully.")
        else:
            print(f"[-] Error on post {index}: {response.text}")

if __name__ == "__main__":
    send_to_buffer()
