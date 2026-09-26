#!/bin/bash

# Simple script to test the Cloudflare Tunnel endpoints hitting Ollama
# Usage: ./test_endpoints.sh https://your-tunnel.trycloudflare.com

TUNNEL_URL=$1

if [ -z "$TUNNEL_URL" ]; then
    echo "Usage: ./test_endpoints.sh https://your-tunnel.trycloudflare.com"
    exit 1
fi

echo "========================================="
echo "Testing Ollama through Cloudflare Tunnel"
echo "URL: $TUNNEL_URL"
echo "========================================="

echo -e "\n1. Testing Health (/api/version)"
curl -s $TUNNEL_URL/api/version

echo -e "\n\n2. Testing Model List (/v1/models)"
curl -s $TUNNEL_URL/v1/models | grep "deephat"

echo -e "\n\n3. Testing OpenAI Chat Completions (/v1/chat/completions)"
curl -s $TUNNEL_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deephat",
    "messages": [{"role": "user", "content": "What is SQL injection?"}],
    "max_tokens": 50
  }'

echo -e "\n\n4. Testing Anthropic Messages (/v1/messages)"
curl -s $TUNNEL_URL/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: ollama" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "deephat",
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "What is XSS?"}]
  }'

echo -e "\n\n========================================="
echo "Done."
