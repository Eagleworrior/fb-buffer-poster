import os
import sys
import datetime
import requests
import time
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

    # List of sensitive trigger words that cause Meta's API to flag your content
    META_TRIGGER_WORDS = [
        "suicide", "died", "death", "killed", "murder", "fatal", 
        "shooting", "corpse", "stabbing", "homicide", "autopsy"
    ]

    posted_count = 0  # Tracks successfully processed articles to keep schedule clean

    for index, article in enumerate(articles):
        title = article.get("title", "Breaking News")
        snippet = article.get("content") or article.get("description") or ""
        
        # 1. CONTENT FILTER CHECK
        full_text_check = f"{title} {snippet}".lower()
        if any(word in full_text_check for word in META_TRIGGER_WORDS):
            print(f"[⏩] Skipping article to protect Page Quality: {title}")
            continue  # Skips this loop entirely and moves to the next article

        # 2. CLEAN & TRUNCATE TEXT TO STOP ON THE LAST COMMA
        # Strip out the News API "[+XXXX chars]" truncated footer if it exists
        if "[+" in snippet:
            snippet = snippet.split("[+")[0].strip()
        
        # Strip trailing text ellipses to locate real punctuation commas
        if snippet.endswith("..."):
            snippet = snippet[:-3].strip()
            
        # Strictly stop right at the last comma if one is found
        if "," in snippet:
            snippet = snippet.rsplit(",", 1)[0].strip() + ","

        # 3. APPEND THE EXACT TARGET HASHTAG STRING
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

        # 4. DYNAMIC MEDIA HANDLING (IMAGE OR VIDEO ASSETS)
        assets = []
        if article.get("urlToVideo"):  # Built-in check if you scale or feed raw video links
            assets.append({"video": {"url": article.get("urlToVideo")}})
        elif article.get("urlToImage"):
            assets.append({"image": {"url": article.get("urlToImage")}})

        if assets:
            input_data["assets"] = assets

        payload = {"query": mutation, "variables": {"input": input_data}}
        headers = {"Authorization": f"Bearer {BUFFER_API_KEY}", "Content-Type": "application/json"}
        
        response = session.post("https://api.buffer.com", headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"[+] Post {index} queued for {due_at}.")
            posted_count += 1  # Increment only on successful/attempted queue addition
        else:
            print(f"[-] Error on post {index}: {response.text}")
        
        # Stagger to prevent rate limit (60s delay)
        if index < len(articles) - 1:
            time.sleep(60)

if __name__ == "__main__":
    send_to_buffer()
