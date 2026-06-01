import os
import sys
import datetime
import requests

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([BUFFER_API_KEY, BUFFER_CHANNEL_ID, NEWS_API_KEY]):
    print("[-] Operational Error: Missing required repository secrets.")
    sys.exit(1)

def fetch_daily_content():
    """Retrieve exactly 10 distinct stories containing text and imagery."""
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

    print(f"[+] Loaded {len(articles)} items. Preparing sequential timeline injection...")
    
    # Establish baseline schedule starting point (2 hours from execution time)
    base_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    for index, article in enumerate(articles):
        headline = article.get("title", "Breaking News Update")
        source_link = article.get("url", "")
        picture_url = article.get("urlToImage")
        
        post_text = f"{headline}\n\nRead more: {source_link}"
        
        # Calculate dynamic 2-hour interval spacing per array item loop
        target_time = base_time + datetime.timedelta(hours=index * 2)
        due_at_timestamp = target_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        query = """
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

        input_variables = {
            "channelId": BUFFER_CHANNEL_ID,
            "text": post_text,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at_timestamp
        }

        if picture_url and picture_url.startswith("http"):
            input_variables["assets"] = [{
                "image": {
                    "url": picture_url
                }
            }]

        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            payload = {"query": query, "variables": {"input": input_variables}}
            res = requests.post("https://api.buffer.com", headers=headers, json=payload)
            res.raise_for_status()
            
            res_data = res.json()
            
            errors = res_data.get("errors")
            data_content = res_data.get("data") or {}
            
            create_post_result = data_content.get("createPost") if isinstance(data_content, dict) else None
            mutation_error = create_post_result.get("message") if isinstance(create_post_result, dict) else None

            if errors:
                print(f"[-] Buffer API Error on item {index}: {errors}")
            elif mutation_error:
                print(f"[-] Buffer Queue Rejection on item {index}: {mutation_error}")
            elif create_post_result and "post" in create_post_result:
                scheduled_info = create_post_result["post"]
                print(f"[+] Post [{index}] successfully queued for timeline: {scheduled_info.get('dueAt')}")
            else:
                print(f"[-] Unexpected response format on item {index}: {res_data}")

        except Exception as conn_err:
            print(f"[-] Critical connection dropout on item {index}: {conn_err}")

if __name__ == "__main__":
    distribute_to_buffer()
