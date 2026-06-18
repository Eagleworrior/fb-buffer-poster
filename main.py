import os
import sys
import datetime
import requests
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load secrets
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([BUFFER_API_KEY, BUFFER_CHANNEL_ID, NEWS_API_KEY]):
    print("[-] Missing required environment variables.")
    sys.exit(1)

# Configure Session
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def send_to_buffer():
    # Fetch 10 items
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=10&apiKey={NEWS_API_KEY}"
    try:
        response = session.get(url)
        articles = response.json().get("articles", [])
    except Exception as e:
        print(f"[-] News Fetch Error: {e}")
        return

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """

    # First post schedules exactly 1 hour after the script runs
    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    # 1. CRITICAL SKIP LIST: Too dangerous to mask. If found, drop the article completely.
    CRITICAL_SKIP_WORDS = ["suicide", "self-harm", "autopsy"]

    # 2. SANITIZATION DICTIONARY: Automatically swaps unsafe words for safe ones
    REPLACEMENT_MAP = {
        "death": "passing",
        "died": "passed away",
        "killed": "lost",
        "murder": "tragic incident",
        "murdered": "fatally harmed",
        "fatal": "serious",
        "shooting": "critical incident",
        "stabbing": "altercation",
        "homicide": "investigation",
        "corpse": "remains"
    }

    posted_count = 0  # Tracks successfully processed articles to keep schedule clean

    for index, article in enumerate(articles):
        title = article.get("title", "Breaking News")
        snippet = article.get("content") or article.get("description") or ""
        
        # Check for critical skip words first
        full_text_check = f"{title} {snippet}".lower()
        if any(word in full_text_check for word in CRITICAL_SKIP_WORDS):
            print(f"[⏩] Hard-skipping critical article to protect page standing: {title}")
            continue

        # 3. DYNAMIC TEXT REWRITE ENGINE
        # Loop through dictionary and use case-insensitive word-boundary replacement
        for unsafe_word, safe_word in REPLACEMENT_MAP.items():
            pattern = re.compile(r'\b' + re.escape(unsafe_word) + r'\b', re.IGNORECASE)
            title = pattern.sub(safe_word, title)
            snippet = pattern.sub(safe_word, snippet)

        # Clean & truncate text to stop on the last comma
        if "[+" in snippet:
            snippet = snippet.split("[+")[0].strip()
        
        if snippet.endswith("..."):
            snippet = snippet[:-3].strip()
            
        if "," in snippet:
            snippet = snippet.rsplit(",", 1)[0].strip() + ","

        # Append exact target hashtag string
        hashtags = "K #follower#follower#fypシ゚viralシ#operationallessons#dashcamfootage#PoliceProcedures#foryoupageシ#FBI#dashcam#fbi#Georgia"
        post_text = f"{title}\n\n{snippet}\n\n{hashtags}"
        
        # Subsequent safe posts schedule in clean 1-hour increments using posted_count
        scheduled_time = start_time + datetime.timedelta(hours=posted_count)
        due_at = scheduled_time.isoformat(timespec='milliseconds').replace("+00:00", "Z")

        input_data = {
            "channelId": BUFFER_CHANNEL_ID,
            "text": post_text,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at,
            "metadata": {"facebook": {"type": "post"}}
        }

        # Dynamic media handling
        assets = []
        if article.get("urlToVideo"):
            assets.append({"video": {"url": article.get("urlToVideo")}})
        elif article.get("urlToImage"):
            assets.append({"image": {"url": article.get("urlToImage")}})

        if assets:
            input_data["assets"] = assets

        payload = {"query": mutation, "variables": {"input": input_data}}
        headers = {"Authorization": f"Bearer {BUFFER_API_KEY}", "Content-Type": "application/json"}
        
        response = session.post("https://api.buffer.com", headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"[+] Post {index} sanitized and queued for {due_at}.")
            posted_count += 1  # Increment only on successful queue addition
        else:
            print(f"[-] Error on post {index}: {response.text}")
        
        # Stagger to prevent rate limit (60s delay)
        if index < len(articles) - 1:
            time.sleep(60)

if __name__ == "__main__":
    send_to_buffer()
