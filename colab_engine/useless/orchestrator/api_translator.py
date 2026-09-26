import json

def anthropic_to_openai(anthropic_req: dict) -> dict:
    """Convert Anthropic Messages API request to OpenAI Chat Completions."""
    messages = []
    
    if "system" in anthropic_req:
        system_text = anthropic_req["system"]
        if isinstance(system_text, list):
            # Only extract 'text' fields, silently ignoring cache_control, etc.
            system_text = "".join(b.get("text", "") for b in system_text if b.get("type") == "text")
        messages.append({"role": "system", "content": system_text})
    
    for msg in anthropic_req.get("messages", []):
        role = msg["role"]
        content = msg["content"]
        
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            tool_calls = []
            
            for block in content:
                if block.get("type") == "text":
                    parts.append({"type": "text", "text": block.get("text", "")})
                elif block.get("type") == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        data_url = f"data:{source.get('media_type', 'image/jpeg')};base64,{source.get('data', '')}"
                        parts.append({"type": "image_url", "image_url": {"url": data_url}})
                    elif source.get("type") == "url":
                        parts.append({"type": "image_url", "image_url": {"url": source.get("url", "")}})
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif block.get("type") == "tool_result":
                    # Flush pending user text before tool_result message
                    if parts:
                        if all(p["type"] == "text" for p in parts):
                            messages.append({"role": role, "content": "".join(p["text"] for p in parts)})
                        else:
                            messages.append({"role": role, "content": parts})
                        parts = []
                        
                    res_content = block.get("content", "")
                    if isinstance(res_content, list):
                        res_content = "".join(b.get("text", "") for b in res_content if b.get("type") == "text")
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": res_content
                    })
            
            if parts or tool_calls:
                msg_dict = {"role": role}
                if parts:
                    if all(p["type"] == "text" for p in parts):
                        msg_dict["content"] = "".join(p["text"] for p in parts)
                    else:
                        msg_dict["content"] = parts
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                    
                if "content" not in msg_dict:
                    msg_dict["content"] = ""
                    
                messages.append(msg_dict)
    
    openai_req = {
        "model": anthropic_req.get("model", "deephat"),
        "messages": messages,
        "max_tokens": anthropic_req.get("max_tokens", 4096),
        "stream": anthropic_req.get("stream", False),
    }
    
    # Only forward optional params if provided by client
    if "temperature" in anthropic_req:
        openai_req["temperature"] = anthropic_req["temperature"]
    if "top_p" in anthropic_req:
        openai_req["top_p"] = anthropic_req["top_p"]
    if "top_k" in anthropic_req:
        openai_req["top_k"] = anthropic_req["top_k"]
    if "stop_sequences" in anthropic_req:
        openai_req["stop"] = anthropic_req["stop_sequences"]
        
    if "tools" in anthropic_req:
        openai_req["tools"] = []
        for tool in anthropic_req["tools"]:
            openai_req["tools"].append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            })
            
    if "tool_choice" in anthropic_req:
        tc = anthropic_req["tool_choice"]
        if tc.get("type") == "tool":
            openai_req["tool_choice"] = {"type": "function", "function": {"name": tc.get("name")}}
        elif tc.get("type") == "auto":
            openai_req["tool_choice"] = "auto"
        elif tc.get("type") == "any":
            openai_req["tool_choice"] = "required"
        
    return openai_req

def openai_to_anthropic(openai_resp: dict, model_name: str) -> dict:
    """Convert OpenAI Chat Completions response to Anthropic Messages format."""
    choice = openai_resp.get("choices", [{}])[0]
    
    content_blocks = []
    text_content = choice.get("message", {}).get("content")
    if text_content:
        content_blocks.append({"type": "text", "text": text_content})
        
    for tc in choice.get("message", {}).get("tool_calls", []):
        try:
            args = json.loads(tc["function"]["arguments"])
        except:
            args = tc["function"]["arguments"] # fallback to raw string if bad JSON
        content_blocks.append({
            "type": "tool_use",
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": args if isinstance(args, dict) else {}
        })
        
    stop_reason = _map_finish_reason(choice.get("finish_reason", "stop"))
    if any(b["type"] == "tool_use" for b in content_blocks):
        stop_reason = "tool_use"

    import uuid
    msg_id = openai_resp.get("id")
    if not msg_id or msg_id == "unknown":
        msg_id = uuid.uuid4().hex
        
    return {
        "id": f"msg_{msg_id}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": content_blocks,
        "stop_reason": stop_reason,
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
    import uuid
    msg_id = f"msg_{uuid.uuid4().hex}"
    
    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': model_name, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
    yield f"event: ping\ndata: {json.dumps({'type': 'ping'})}\n\n"
    
    done = False
    index = 0
    in_text_block = False
    in_tool_block = False
    
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
                        
                        # Handle text
                        if "content" in delta and delta["content"] is not None:
                            if not in_text_block:
                                if in_tool_block:
                                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': index})}\n\n"
                                    index += 1
                                    in_tool_block = False
                                yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': index, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
                                in_text_block = True
                            
                            yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': index, 'delta': {'type': 'text_delta', 'text': delta['content']}})}\n\n"
                            
                        # Handle tool calls
                        if "tool_calls" in delta and delta["tool_calls"]:
                            tc = delta["tool_calls"][0]
                            # Tool call start
                            if "id" in tc and "function" in tc and "name" in tc["function"]:
                                if in_text_block or in_tool_block:
                                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': index})}\n\n"
                                    index += 1
                                    in_text_block = False
                                    
                                yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': index, 'content_block': {'type': 'tool_use', 'id': tc['id'], 'name': tc['function']['name'], 'input': {}}})}\n\n"
                                in_tool_block = True
                                
                            # Tool call arguments delta
                            if "function" in tc and "arguments" in tc["function"]:
                                yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': index, 'delta': {'type': 'input_json_delta', 'partial_json': tc['function']['arguments']}})}\n\n"
                        
                        # Handle finish reason
                        finish_reason = choices[0].get("finish_reason")
                        if finish_reason:
                            if in_text_block or in_tool_block:
                                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': index})}\n\n"
                            
                    if "usage" in data and data["usage"]:
                        usage = data["usage"]
                        stop_reason = "end_turn"
                        if choices and choices[0].get("finish_reason"):
                            stop_reason = _map_finish_reason(choices[0]["finish_reason"])
                            if stop_reason == "end_turn" and in_tool_block:
                                stop_reason = "tool_use"
                            
                        yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': stop_reason}, 'usage': {'output_tokens': usage.get('completion_tokens', 0)}})}\n\n"
                        
        except Exception:
            pass
            
    yield "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
