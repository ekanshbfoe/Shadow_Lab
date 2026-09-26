import requests

url = "https://changed-invited-organizing-mission.trycloudflare.com"

print("3. Testing OpenAI Chat Completions")
r = requests.post(
    f"{url}/v1/chat/completions", 
    json={"model": "deephat", "messages": [{"role": "user", "content": "What is SQL injection?"}], "max_tokens": 50}
)
print(r.status_code, r.text)

print("\n4. Testing Anthropic Messages")
r = requests.post(
    f"{url}/v1/messages", 
    headers={"x-api-key": "ollama", "anthropic-version": "2023-06-01"},
    json={"model": "deephat", "max_tokens": 50, "messages": [{"role": "user", "content": "What is XSS?"}]}
)
print(r.status_code, r.text)
