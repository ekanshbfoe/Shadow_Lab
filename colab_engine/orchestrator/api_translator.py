import json

def anthropic_to_openai(anthropic_req: dict) -> dict:
    """Convert Anthropic Messages API request to OpenAI Chat Completions."""
    messages = []
    
    if "system" in anthropic_req:
        system_text = anthropic_req["system"]
        if isinstance(system_text, list):
            system_text = "\n".join(b["text"] for b in system_text if b["type"] == "text")
        messages.append({"role": "system", "content": system_text})
    
    for msg in anthropic_req.get("messages", []):
        role = msg["role"]
        content = msg["content"]
        
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            for block in content:
                if block["type"] == "text":
                    parts.append({"type": "text", "text": block["text"]})
                elif block["type"] == "image":
                    source = block["source"]
                    if source["type"] == "base64":
                        data_url = f"data:{source['media_type']};base64,{source['data']}"
                        parts.append({"type": "image_url", "image_url": {"url": data_url}})
                    elif source["type"] == "url":
                        parts.append({"type": "image_url", "image_url": {"url": source["url"]}})
            if all(p["type"] == "text" for p in parts):
                messages.append({"role": role, "content": "\n".join(p["text"] for p in parts)})
            else:
                messages.append({"role": role, "content": parts})
    
    return {
        "model": anthropic_req.get("model", "deephat"),
        "messages": messages,
        "max_tokens": anthropic_req.get("max_tokens", 4096),
        "temperature": anthropic_req.get("temperature", 0.7),
        "stream": anthropic_req.get("stream", False),
        "top_p": anthropic_req.get("top_p", 0.9),
    }

def openai_to_anthropic(openai_resp: dict, model_name: str) -> dict:
    """Convert OpenAI Chat Completions response to Anthropic Messages format."""
    choice = openai_resp.get("choices", [{}])[0]
    return {
        "id": f"msg_{openai_resp.get('id', 'unknown')}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": [{"type": "text", "text": choice.get("message", {}).get("content", "")}],
        "stop_reason": _map_finish_reason(choice.get("finish_reason", "stop")),
        "usage": {
            "input_tokens": openai_resp.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": openai_resp.get("usage", {}).get("completion_tokens", 0),
        },
    }

def _map_finish_reason(openai_reason: str) -> str:
    return {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }.get(openai_reason, "end_turn")

async def translate_sse_stream(response_stream, model_name: str):
    """Translates OpenAI SSE to Anthropic SSE."""
    msg_id = "msg_stream"
    
    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': model_name, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
    
    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    
    done = False
    async for chunk in response_stream:
        if done:
            break
        if not chunk:
            continue
        try:
            chunk_str = chunk.decode('utf-8')
            for line in chunk_str.splitlines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        done = True
                        break
                    data = json.loads(data_str)
                    
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': delta['content']}})}\n\n"
                        
                        finish_reason = choices[0].get("finish_reason")
                        if finish_reason:
                            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                            
                    if "usage" in data and data["usage"]:
                        usage = data["usage"]
                        yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': _map_finish_reason(choices[0].get('finish_reason', 'stop') if choices else 'stop')}, 'usage': {'output_tokens': usage.get('completion_tokens', 0)}})}\n\n"
                        
        except Exception:
            pass
            
    yield "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
