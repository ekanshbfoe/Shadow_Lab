# ShadowLab: Ollama Engine

This directory contains the modernized architecture for ShadowLab's cloud inference backend, powered by Ollama.

## Why Ollama?
We migrated away from our custom Python proxy stack to Ollama because it provides:
- Native Anthropic Messages API support (`/v1/messages`)
- Native OpenAI Chat Completions API support (`/v1/chat/completions`)
- Built-in VRAM management and model swapping
- Tool calling natively supported for Claude Code
- Far fewer moving parts (no race conditions)

## Setup Instructions

### 1. Colab Deployment
1. Upload `shadowlab_colab.ipynb` to Google Colab.
2. Ensure your runtime is **T4 GPU**.
3. Run the cells sequentially. The first cell will automatically download the DeepHat model to your Google Drive if it's not already there.
4. Copy the Cloudflare Tunnel URL from the output of Cell 5.

### 2. Testing
From your local terminal, run the test script to verify the tunnel:
```bash
bash test_endpoints.sh https://your-tunnel-url.trycloudflare.com
```

### 3. Client Configuration
- **LobeChat:** Set the OpenAI Base URL to `https://your-tunnel-url.trycloudflare.com/v1` and the API Key to anything (e.g., `ollama`).
- **Claude Desktop / Claude Code:** Set the Anthropic Base URL to `https://your-tunnel-url.trycloudflare.com` (do not append `/v1`) and the API Key to `ollama`.

## Architecture Details
- **VRAM Optimizations:** We force `OLLAMA_KV_CACHE_TYPE="q8_0"` to compress the KV cache by ~40%, allowing 8k context windows to fit on a 16GB T4.
- **Concurrency Control:** `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1` ensure memory is strictly budgeted for a single model responding to a single request at a time.
- **Auto-Eviction:** When LobeChat requests `qwen2.5vl:7b`, Ollama automatically unloads `deephat` from VRAM to make space, and vice-versa.
