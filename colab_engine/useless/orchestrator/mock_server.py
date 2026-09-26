from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f'>>> GET request received: {self.path}')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        # Anthropic format for model discovery
        resp = {"data": [{"type": "model", "id": "DeepHat-V1-7B", "display_name": "DeepHat V1 7B"}]}
        self.wfile.write(json.dumps(resp).encode('utf-8'))
        
    def do_POST(self):
        print(f'>>> POST request received: {self.path}')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        # Anthropic format for chat messages
        resp = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Local test pass! Claude Desktop is fully wired."}],
            "model": "DeepHat-V1-7B",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 10}
        }
        self.wfile.write(json.dumps(resp).encode('utf-8'))

print('Listening on port 8080...')
HTTPServer(('127.0.0.1', 8080), H).serve_forever()