import os
import sys
import datetime
import requests
import json

# Load secrets from GitHub Actions environment
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([BUFFER_API_KEY, BUFFER_CHANNEL_ID, NEWS_API_KEY]):
    print("[-] Error: Missing required repository secrets.")
    sys.exit(1)

def fetch_daily_content():
    """Fetch 10 articles."""
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=10&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
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

    # Buffer GraphQL Endpoint (Must be api.buffer.com)
    url = "https://api.buffer.com"
    
    headers = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            dueAt
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    for index, article in enumerate(articles):
        headline = article.get("title", "Breaking News")
        link = article.get("url", "")
        post_text = f"{headline}\n\nRead more: {link}"
        
        # Calculate time: 2 hours difference per post
        scheduled_time = start_time + datetime.timedelta(hours=index * 2)
        due_at = scheduled_time.isoformat(timespec='milliseconds').replace("+00:00", "Z")

        # The clean input payload for GraphQL
        variables = {
            "input": {
                "channelId": BUFFER_CHANNEL_ID,
                "text": post_text,
                "schedulingType": "automatic",
                "mode": "customScheduled",
                "dueAt": due_at
            }
        }

        try:
            payload = {"query": mutation, "variables": variables}
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Check for GraphQL errors
            if "errors" in result:
                print(f"[-] Post {index} GraphQL Error: {result['errors']}")
            else:
                data = result.get("data", {}).get("createPost", {})
                if "message" in data:
                    print(f"[-] Post {index} Buffer Error: {data['message']}")
                else:
                    print(f"[+] Post {index} successfully queued for {due_at}")
                    
        except Exception as e:
            print(f"[-] Connection Error on post {index}: {e}")

if __name__ == "__main__":
    send_to_buffer()
