"""Configuration for ShadowLab Orchestrator."""

MODELS = {
    "deephat": {
        "name": "DeepHat-V1-7B",
        "file": "DeepHat-V1-7B.Q4_K_M.gguf",
        "mmproj": None,
        "aliases": ["deephat-v1-7b", "deephat", "security"],
        "extra_flags": [],
    },
    "qwen-vl": {
        "name": "Qwen2.5-VL-7B",
        "file": "qwen2.5-vl-7b-instruct-q4_k_m.gguf",
        "mmproj": "mmproj-f16.gguf",
        "aliases": ["qwen-vl", "qwen2.5-vl", "vision", "qwen"],
        "extra_flags": [],
    },
}

COMMON_FLAGS = [
    "-ngl", "99",
    "-c", "8192",
    "-b", "512",
    "-ub", "512",
    "-fa",                    # Flash Attention
    "-ctk", "q4_0",           # KV cache key quantization
    "-ctv", "q4_0",           # KV cache value quantization
    "-np", "1",               # Single slot
    "--metrics",              # Expose /metrics for monitoring
]

IDLE_TIMEOUT_S = 30
HEALTH_POLL_INTERVAL_S = 0.5
HEALTH_POLL_MAX_RETRIES = 60   # 30 seconds max wait for model load
SWAP_DRAIN_TIMEOUT_S = 60      # Max wait for in-flight requests
VRAM_RELEASE_VERIFY_TIMEOUT_S = 10
VRAM_RELEASE_THRESHOLD_MB = 800
MAX_IMAGE_DIMENSION = 1344
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_REQUEST = 2
