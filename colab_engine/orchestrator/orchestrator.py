import argparse
import asyncio
import logging
import time
from aiohttp import web
import aiohttp_cors

import config
from model_manager import ModelManager
from api_translator import anthropic_to_openai, openai_to_anthropic, translate_sse_stream
from image_utils import validate_images

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model_manager = None
last_request_time = time.time()
backend_session = None

async def idle_checker():
    """Unloads model if idle for IDLE_TIMEOUT_S."""
    global last_request_time
    while True:
        await asyncio.sleep(5)
        if model_manager.current_model and (time.time() - last_request_time > config.IDLE_TIMEOUT_S):
            logger.info("Idle timeout reached. Unloading active model to save VRAM.")
            await model_manager.kill_current_model()

async def forward_to_llama_server(request, payload, stream=False):
    """Forwards request to llama-server."""
    global last_request_time, backend_session
    last_request_time = time.time()
    
    url = f"http://{model_manager.listen_host}:{model_manager.backend_port}{request.path}"
    
    if not backend_session:
        backend_session = aiohttp.ClientSession()
        
    try:
        if stream:
            async with backend_session.post(url, json=payload, headers={'Content-Type': 'application/json'}) as resp:
                response = web.StreamResponse(status=resp.status, headers=resp.headers)
                await response.prepare(request)
                async for chunk in resp.content.iter_any():
                    await response.write(chunk)
                return response
        else:
            async with backend_session.post(url, json=payload, headers={'Content-Type': 'application/json'}) as resp:
                text = await resp.text()
                return web.Response(status=resp.status, text=text, content_type=resp.content_type)
    except Exception as e:
        logger.error(f"Error forwarding request: {e}")
        return web.Response(status=502, text="Bad Gateway")

async def handle_openai_chat(request):
    """Handles OpenAI /v1/chat/completions."""
    try:
        payload = await request.json()
    except:
        return web.Response(status=400, text="Invalid JSON")
        
    model_req = payload.get("model", "deephat")
    
    # Process images if needed
    payload["messages"] = validate_images(payload.get("messages", []))
    
    await model_manager.ensure_model(model_req)
    return await forward_to_llama_server(request, payload, stream=payload.get("stream", False))

async def handle_anthropic_messages(request):
    """Handles Anthropic /v1/messages."""
    try:
        anthropic_payload = await request.json()
    except:
        return web.Response(status=400, text="Invalid JSON")
        
    openai_payload = anthropic_to_openai(anthropic_payload)
    openai_payload["messages"] = validate_images(openai_payload.get("messages", []))
    
    model_req = openai_payload.get("model", "deephat")
    await model_manager.ensure_model(model_req)
    
    global last_request_time, backend_session
    last_request_time = time.time()
    
    url = f"http://{model_manager.listen_host}:{model_manager.backend_port}/v1/chat/completions"
    
    if not backend_session:
        backend_session = aiohttp.ClientSession()
        
    is_stream = openai_payload.get("stream", False)
    
    try:
        if is_stream:
            resp = await backend_session.post(url, json=openai_payload)
            response = web.StreamResponse(status=resp.status, headers={'Content-Type': 'text/event-stream'})
            await response.prepare(request)
            async for sse_chunk in translate_sse_stream(resp.content, model_req):
                await response.write(sse_chunk.encode('utf-8'))
            return response
        else:
            async with backend_session.post(url, json=openai_payload) as resp:
                openai_resp = await resp.json()
                anthropic_resp = openai_to_anthropic(openai_resp, model_req)
                return web.json_response(anthropic_resp)
    except Exception as e:
        logger.error(f"Error forwarding request: {e}")
        return web.Response(status=502, text="Bad Gateway")

async def handle_models(request):
    return web.json_response({
        "object": "list",
        "data": [
            {"id": "deephat-v1-7b", "object": "model", "created": 1695600000, "owned_by": "local", "permission": []},
            {"id": "qwen2.5-vl-7b", "object": "model", "created": 1695600000, "owned_by": "local", "permission": []}
        ]
    })

async def handle_health(request):
    return web.json_response({"status": "ok", "active_model": model_manager.current_model})

def init_app(args):
    app = web.Application()
    
    app.router.add_post('/v1/chat/completions', handle_openai_chat)
    app.router.add_post('/v1/messages', handle_anthropic_messages)
    app.router.add_get('/v1/models', handle_models)
    app.router.add_get('/health', handle_health)
    
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    for route in list(app.router.routes()):
        cors.add(route)
        
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--listen-host', default='0.0.0.0')
    parser.add_argument('--listen-port', type=int, default=8080)
    parser.add_argument('--backend-port', type=int, default=8081)
    parser.add_argument('--llama-server', required=True)
    parser.add_argument('--model-dir', required=True)
    args = parser.parse_args()
    
    model_manager = ModelManager(
        llama_server_bin=args.llama_server,
        model_dir=args.model_dir,
        listen_host='127.0.0.1',
        backend_port=args.backend_port
    )
    
    app = init_app(args)
    
    loop = asyncio.get_event_loop()
    loop.create_task(idle_checker())
    
    web.run_app(app, host=args.listen_host, port=args.listen_port)
