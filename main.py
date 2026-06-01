import os
import sys
import datetime
import requests

# Load secrets
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
HISTORY_FILE = "posted_headlines.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_history(headline):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{headline}\n")

def fetch_daily_content():
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("articles", [])
    except Exception as e:
        print(f"[-] News Fetch Error: {e}")
        return []

def send_to_buffer():
    articles = fetch_daily_content()
    posted_already = load_history()
    
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
        headline = article.get("title", "Breaking News")
        description = article.get("description", "")
        
        # Skip if we already posted this headline
        if headline in posted_already:
            continue

        # Post text is now the full description without links
        post_text = f"{headline}\n\n{description}"
        
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

        # Logic for Images AND Videos
        image_url = article.get("urlToImage")
        video_url = article.get("videoUrl") # Hypothetical field if your news source has video

        assets = []
        if video_url:
            assets.append({"video": {"url": video_url}})
        elif image_url:
            assets.append({"image": {"url": image_url}})
        
        if assets:
            input_data["assets"] = assets

        try:
            payload = {"query": mutation, "variables": {"input": input_data}}
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if "errors" not in result and "message" not in result.get("data", {}).get("createPost", {}):
                print(f"[+] Post [{index}] successfully queued.")
                save_history(headline)
            else:
                print(f"[-] Buffer Error on post {index}")
        except Exception as e:
            print(f"[-] Connection Error: {e}")

if __name__ == "__main__":
    send_to_buffer()
