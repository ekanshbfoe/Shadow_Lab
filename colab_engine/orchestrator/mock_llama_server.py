# mock_llama_server.py — run on localhost:8081
from aiohttp import web
import json, time

async def handle_completions(request):
    data = await request.json()
    is_stream = data.get("stream", False)
    if is_stream:
        response = web.StreamResponse(headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
        })
        await response.prepare(request)
        # Send 3 token chunks
        for i, word in enumerate(["Hello", " from", " mock!"]):
            chunk = {"id": "mock-1", "choices": [{"index": 0, "delta": {"content": word}, "finish_reason": None}]}
            await response.write(f"data: {json.dumps(chunk)}\n\n".encode())
        # Final chunk with finish_reason
        final = {"id": "mock-1", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
        await response.write(f"data: {json.dumps(final)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
        return response
    else:
        return web.json_response({
            "id": "mock-1", "object": "chat.completion", "created": int(time.time()),
            "model": data.get("model", "mock"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Mock response."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        })

async def handle_health(request):
    return web.json_response({"status": "ok"})

app = web.Application()
app.router.add_post('/v1/chat/completions', handle_completions)
app.router.add_get('/health', handle_health)
web.run_app(app, host='127.0.0.1', port=8081)
