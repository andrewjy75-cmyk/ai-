r"""
练习 03 · 台阶 C 参考答案：网页打字机（FastAPI 服务端）
=========================================================

配套网页见同目录 index_reference.html。
把台阶 B 的服务加一个 GET / 出口：用 FileResponse 把 index.html 寄给浏览器。
网页里的 JS 再 POST /chat 拿 SSE 流 → 打字机效果。

运行（在 llm-course 目录下）：
    python solutions/ex03-streaming-web/step_c_reference.py
浏览器打开 http://127.0.0.1:8000
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

BASE_DIR = Path(__file__).parent
app = FastAPI()


def llm_stream(question: str):
    """模型流式输出 → SSE 格式（和台阶 B 一样）"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是智能助手，回答用中文且简洁"},
            {"role": "user", "content": question},
        ],
        stream=True,
    )
    for chunk in response:
        piece = chunk.choices[0].delta.content
        if piece:
            yield f"data:{piece}\n\n"


@app.post("/chat")
async def chat(payload: dict):
    """复用 SSE 接口"""
    return StreamingResponse(
        llm_stream(payload["question"]), media_type="text/event-stream"
    )


@app.get("/")
async def index():
    """根路径返回网页文件"""
    return FileResponse(BASE_DIR / "index_reference.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
