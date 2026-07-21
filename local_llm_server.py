# -*- coding: utf-8 -*-
"""本地 LLM HTTP 服务

用系统的 Python + llama-cpp-python 运行，
PIME 输入法通过 HTTP 调用。

优势：
- 无需 Ollama 进程
- 比 Ollama HTTP 少一层进程间通信
- 模型常驻内存，推理速度快

启动方式：
  python local_llm_server.py [--port 11435] [--model path/to/model.gguf]

API（兼容 Ollama 格式）：
  POST /api/chat
  {
    "messages": [...],
    "max_tokens": 20
  }

  返回：
  {
    "message": {"content": "..."},
    "done": true
  }
"""

import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler


class LLMHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    llm = None  # 类变量，共享模型实例

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                messages = data.get("messages", [])
                max_tokens = data.get("max_tokens", 20)

                if self.llm is None:
                    self._send_error("Model not loaded")
                    return

                r = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                content = r["choices"][0]["message"]["content"] or ""
                response = {
                    "message": {"role": "assistant", "content": content},
                    "done": True,
                }
                self._send_json(response)
            except Exception as e:
                self._send_error(str(e))
        elif self.path == "/api/health":
            self._send_json({"status": "ok", "model_loaded": self.llm is not None})
        else:
            self._send_error("Unknown endpoint", 404)

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json({"status": "ok", "model_loaded": self.llm is not None})
        else:
            self._send_error("Unknown endpoint", 404)

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, code=500):
        self._send_json({"error": msg}, code)

    def log_message(self, format, *args):
        # 静默日志
        pass


def main():
    parser = argparse.ArgumentParser(description="Local LLM HTTP Server")
    parser.add_argument("--port", type=int, default=11435, help="HTTP port")
    parser.add_argument("--model", type=str, default="", help="Model path (.gguf)")
    parser.add_argument("--threads", type=int, default=4, help="Number of threads")
    args = parser.parse_args()

    # 查找模型
    model_path = args.model
    if not model_path:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(script_dir, "models")
        if os.path.isdir(models_dir):
            for f in os.listdir(models_dir):
                if f.endswith(".gguf"):
                    model_path = os.path.join(models_dir, f)
                    break

    if not model_path or not os.path.isfile(model_path):
        print("[ERROR] No .gguf model found")
        print("  Usage: python local_llm_server.py --model path/to/model.gguf")
        return

    # 加载模型
    print("Loading model: {}".format(model_path))
    from llama_cpp import Llama
    LLMHandler.llm = Llama(
        model_path=model_path,
        n_ctx=512,
        n_threads=args.threads,
        verbose=False,
    )
    print("Model loaded. Starting server on port {}".format(args.port))

    # 启动 HTTP 服务
    server = HTTPServer(("127.0.0.1", args.port), LLMHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")


if __name__ == "__main__":
    main()
