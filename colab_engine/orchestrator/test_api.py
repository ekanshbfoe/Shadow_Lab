# test_api.py — Local test suite for the ShadowLab orchestrator
# Run with: python test_api.py
# Prerequisites: mock_llama_server.py running on port 8081
#                orchestrator.py running on port 8000 with --mock flag
#
# Terminal 1: python mock_llama_server.py
# Terminal 2: python orchestrator.py --listen-host 127.0.0.1 --listen-port 8000 --backend-port 8081 --mock
# Terminal 3: python test_api.py

import requests
import json
import sys

BASE = "https://cardiac-browsing-extraordinary-immediate.trycloudflare.com"
PASSED = 0
FAILED = 0

def test(name, method, url, headers=None, json_body=None, expect_status=200, check_fn=None):
    global PASSED, FAILED
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        else:
            r = requests.post(url, headers=headers, json=json_body, timeout=90)
        
        if r.status_code != expect_status:
            print(f"  ❌ {name}: Expected {expect_status}, got {r.status_code}")
            print(f"     Body: {r.text[:200]}")
            FAILED += 1
            return
        
        if check_fn:
            result = check_fn(r)
            if result is not True:
                print(f"  ❌ {name}: {result}")
                FAILED += 1
                return
        
        print(f"  ✅ {name}")
        PASSED += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        FAILED += 1

# ============================================================
# TEST 1: Health Endpoint
# ============================================================
print("\n📋 Test Group 1: Health Endpoint")

test("GET /health returns 200",
    "GET", f"{BASE}/health",
    check_fn=lambda r: True if "status" in r.json() and r.json()["status"] == "ok" else f"Bad response: {r.text}")

test("GET /health has uptime_s",
    "GET", f"{BASE}/health",
    check_fn=lambda r: True if "uptime_s" in r.json() else "Missing uptime_s field")

# ============================================================
# TEST 2: Model Discovery (LobeChat)
# ============================================================
print("\n📋 Test Group 2: Model Discovery (LobeChat)")

test("GET /v1/models returns model list",
    "GET", f"{BASE}/v1/models",
    check_fn=lambda r: True if r.json()["object"] == "list" and len(r.json()["data"]) == 2 else f"Bad: {r.text}")

test("GET /models (no /v1 prefix) also works",
    "GET", f"{BASE}/models",
    check_fn=lambda r: True if r.json()["object"] == "list" else f"Bad: {r.text}")

test("Model IDs are correct",
    "GET", f"{BASE}/v1/models",
    check_fn=lambda r: True if set(m["id"] for m in r.json()["data"]) == {"deephat-v1-7b", "qwen2.5-vl-7b"} else "Wrong model IDs")

# ============================================================
# TEST 3: OpenAI Chat Completions (LobeChat route)
# ============================================================
print("\n📋 Test Group 3: OpenAI Chat Completions (LobeChat)")

test("POST /v1/chat/completions — basic",
    "POST", f"{BASE}/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json_body={"model": "deephat-v1-7b", "messages": [{"role": "user", "content": "test"}]},
    check_fn=lambda r: True if "choices" in r.json() else f"Missing choices: {r.text}")

test("Response has usage metadata",
    "POST", f"{BASE}/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json_body={"model": "deephat-v1-7b", "messages": [{"role": "user", "content": "test"}]},
    check_fn=lambda r: True if "usage" in r.json() else f"Missing usage: {r.text}")

# ============================================================
# TEST 4: Anthropic Messages (Claude Desktop route)
# ============================================================
print("\n📋 Test Group 4: Anthropic Messages (Claude Desktop)")

test("POST /v1/messages — basic (non-stream)",
    "POST", f"{BASE}/v1/messages",
    headers={"Content-Type": "application/json", "x-api-key": "sk-test"},
    json_body={"model": "deephat-v1-7b", "max_tokens": 100, "messages": [{"role": "user", "content": "test"}]},
    check_fn=lambda r: True if r.json().get("type") == "message" and r.json().get("id", "").startswith("msg_") else f"Bad Anthropic format: {r.text}")

test("Anthropic response has content array",
    "POST", f"{BASE}/v1/messages",
    headers={"Content-Type": "application/json", "x-api-key": "sk-test"},
    json_body={"model": "deephat-v1-7b", "max_tokens": 100, "messages": [{"role": "user", "content": "test"}]},
    check_fn=lambda r: True if isinstance(r.json().get("content"), list) and r.json()["content"][0]["type"] == "text" else f"Bad content: {r.text}")

test("Anthropic response has usage",
    "POST", f"{BASE}/v1/messages",
    headers={"Content-Type": "application/json", "x-api-key": "sk-test"},
    json_body={"model": "deephat-v1-7b", "max_tokens": 100, "messages": [{"role": "user", "content": "test"}]},
    check_fn=lambda r: True if "input_tokens" in r.json().get("usage", {}) else f"Bad usage: {r.text}")

# ============================================================
# TEST 5: Streaming (Anthropic SSE)
# ============================================================
print("\n📋 Test Group 5: Anthropic Streaming SSE")

try:
    r = requests.post(f"{BASE}/v1/messages",
        headers={"Content-Type": "application/json"},
        json={"model": "deephat-v1-7b", "max_tokens": 100, "stream": True, "messages": [{"role": "user", "content": "test"}]},
        stream=True, timeout=90)
    
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("event: "):
            events.append(line.split("event: ")[1])
    
    if "message_start" in events:
        print("  ✅ SSE: message_start event received")
        PASSED += 1
    else:
        print(f"  ❌ SSE: missing message_start. Got: {events}")
        FAILED += 1
    
    if "content_block_delta" in events:
        print("  ✅ SSE: content_block_delta events received")
        PASSED += 1
    else:
        print(f"  ❌ SSE: missing content_block_delta. Got: {events}")
        FAILED += 1
    
    if "message_stop" in events:
        print("  ✅ SSE: message_stop event received (clean termination)")
        PASSED += 1
    else:
        print(f"  ❌ SSE: missing message_stop. Got: {events}")
        FAILED += 1

except Exception as e:
    print(f"  ❌ SSE streaming test failed: {e}")
    FAILED += 3

# ============================================================
# TEST 6: Edge Cases
# ============================================================
print("\n📋 Test Group 6: Edge Cases")

test("Invalid JSON returns 400",
    "POST", f"{BASE}/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json_body=None,
    expect_status=400)

test("Anthropic system prompt translation",
    "POST", f"{BASE}/v1/messages",
    headers={"Content-Type": "application/json"},
    json_body={
        "model": "deephat-v1-7b", "max_tokens": 100,
        "system": "You are a security analyst.",
        "messages": [{"role": "user", "content": "test"}]
    },
    check_fn=lambda r: True if r.json().get("type") == "message" else f"Bad: {r.text}")

# ============================================================
# RESULTS
# ============================================================
print(f"\n{'='*50}")
print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
print(f"{'='*50}")

if FAILED > 0:
    sys.exit(1)
