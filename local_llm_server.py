# -*- coding: utf-8 -*-
"""本地 LLM HTTP 服务

用系统的 Python + llama-cpp-python 运行，
PIME 输入法通过 HTTP 调用。

推荐模型：
- qwen3-0.6b-instruct-q4_k_m.gguf（400MB，输入法专用，需关闭思考模式）
- qwen2.5-0.5b-instruct-q4_k_m.gguf（400MB，输入法专用，无思考模式）

模型要求：
1. 必须是 .gguf 格式
2. 必须是 Instruct/Chat 微调版（base 模型不会按格式回复）
3. 建议 ≤1B 参数（大了推理太慢，输入法等不了）
4. 必须支持中文

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
import os
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler


# 推荐模型关键词（用于自动选择最佳模型）
PREFERRED_KEYWORDS = ["qwen", "instruct"]
# 不推荐的模型关键词（base 模型不会按 chat 格式回复）
BASE_MODEL_KEYWORDS = ["base", "pretrained", "continuation"]


def _pick_best_model(models_dir):
    """从 models/ 目录中选择最佳模型

    优先级：
    1. 包含 qwen + instruct 的模型
    2. 包含 instruct/chat 的模型
    3. 第一个 .gguf 文件（带警告）
    """
    if not os.path.isdir(models_dir):
        return None, ""

    gguf_files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
    if not gguf_files:
        return None, ""

    # 优先选择含 qwen+instruct 的
    best = None
    best_score = 0
    warnings = []

    for f in gguf_files:
        name_lower = f.lower()
        score = 0

        # 加分项
        if "qwen" in name_lower:
            score += 10
        if "instruct" in name_lower or "chat" in name_lower or "it" in name_lower:
            score += 5
        if "0.5b" in name_lower or "0.6b" in name_lower or "1b" in name_lower:
            score += 3  # 小模型更适合输入法
        if "q4" in name_lower or "q5" in name_lower:
            score += 1  # 量化格式合理

        # 警告项
        if any(kw in name_lower for kw in BASE_MODEL_KEYWORDS):
            score -= 20
            warnings.append("[WARN] {} 可能是 base 模型（非指令微调），无法按 chat 格式回复".format(f))
        if any(kw in name_lower for kw in ["7b", "8b", "13b", "14b", "32b", "70b"]):
            warnings.append("[WARN] {} 参数量较大，推理可能较慢（建议 ≤1B）".format(f))
            score -= 5
        if "q2" in name_lower or "q1" in name_lower:
            warnings.append("[WARN] {} 量化太低，输出质量差".format(f))

        if score > best_score:
            best_score = score
            best = f

    if best and gguf_files.index(best) > 0:
        print("[INFO] 发现多个模型，已自动选择: {} (score={})".format(best, best_score))

    for w in warnings:
        if best and any(kw in best.lower() for kw in ["base", "7b", "8b", "13b", "q2", "q1"]):
            print(w)

    return os.path.join(models_dir, best) if best else None, "".join(warnings)


def _is_qwen3_model(model_path):
    """判断是否为 Qwen3 系列模型"""
    name = os.path.basename(model_path).lower()
    return "qwen3" in name or "qwen-3" in name or "qwq" in name


class LLMHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    llm = None  # 类变量，共享模型实例
    is_qwen3 = False  # 是否为 Qwen3 模型（需要关闭思考模式）

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

                # Qwen3 系列关闭思考模式：在最后一条 user 消息追加 /no_think
                if self.is_qwen3:
                    msgs = [dict(m) for m in messages]
                    if msgs and msgs[-1].get("role") == "user":
                        original = msgs[-1].get("content", "")
                        if "/no_think" not in original:
                            msgs[-1]["content"] = original + " /no_think"
                    messages = msgs

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
            model_name = ""
            if self.llm and hasattr(self.llm, 'model_path'):
                model_name = os.path.basename(self.llm.model_path)
            self._send_json({
                "status": "ok",
                "model_loaded": self.llm is not None,
                "model": model_name,
            })
        else:
            self._send_error("Unknown endpoint", 404)

    def do_GET(self):
        if self.path == "/api/health":
            model_name = ""
            if self.llm and hasattr(self.llm, 'model_path'):
                model_name = os.path.basename(self.llm.model_path)
            self._send_json({
                "status": "ok",
                "model_loaded": self.llm is not None,
                "model": model_name,
            })
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
    parser.add_argument("--gpu", type=int, default=-1, help="GPU layers (-1=auto, 0=CPU only)")
    args = parser.parse_args()

    # 查找模型
    model_path = args.model
    if not model_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(script_dir, "models")
        model_path, warning = _pick_best_model(models_dir)

    if not model_path or not os.path.isfile(model_path):
        print("[ERROR] No .gguf model found")
        print("  Put a model in the models/ directory, then retry.")
        print("  Recommended: qwen2.5-0.5b-instruct-q4_k_m.gguf")
        print("  Download: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF")
        return

    # 加载模型
    print("Loading model: {}".format(model_path))
    n_gpu = args.gpu
    if n_gpu != 0:
        try:
            import llama_cpp
            if hasattr(llama_cpp, 'GGML_USE_CUBLAS') or hasattr(llama_cpp, '__version__'):
                print("GPU mode: n_gpu_layers={} (-1=auto detect)".format(n_gpu))
        except Exception:
            print("GPU not available, falling back to CPU")
            n_gpu = 0

    from llama_cpp import Llama
    LLMHandler.llm = Llama(
        model_path=model_path,
        n_ctx=512,
        n_threads=args.threads,
        n_gpu_layers=n_gpu,
        verbose=False,
    )
    # 保存模型路径供 health API 使用
    LLMHandler.llm.model_path = model_path
    LLMHandler.is_qwen3 = _is_qwen3_model(model_path)
    if LLMHandler.is_qwen3:
        print("Qwen3 model detected: thinking mode will be disabled (/no_think)")
    print("Model loaded. Starting server on port {}".format(args.port))

    # 启动 HTTP 服务
    server = HTTPServer(("127.0.0.1", args.port), LLMHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")


if __name__ == "__main__":
    main()
