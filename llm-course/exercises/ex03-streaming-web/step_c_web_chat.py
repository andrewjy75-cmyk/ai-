r"""
练习 03 · 台阶 C：网页打字机（最终步）
========================================

把台阶 B 的 FastAPI 服务升级：托管一个静态网页，
网页里输入问题 → 调 /chat 接口 → 回答逐字上屏（打字机效果）。

运行：
    python exercises/ex03-streaming-web/step_c_web_chat.py
然后浏览器打开：http://127.0.0.1:8000
（如果 8000 端口被台阶 B 的服务占着，先 Ctrl+C 停掉旧的）
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

# 当前文件所在目录，用来定位 index.html
BASE_DIR = Path(__file__).parent

app = FastAPI()


def llm_stream(question: str):
    """模型流式输出 → SSE 格式（台阶 B 写好的，原样搬过来）"""
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
    """复用台阶 B 的 SSE 接口"""
    question = payload["question"]
    return StreamingResponse(llm_stream(question), media_type="text/event-stream")


@app.get("/")
async def index():
    """访问根路径时返回网页"""
    # TODO-C1【简单】用 FileResponse 返回 index.html
    #   提示：FileResponse(BASE_DIR / "index.html")
    pass


# TODO-C2【简单】挂载静态资源目录（可选，如果有 css/js 文件的话）
#   提示：app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
#   如果 index.html 全部内联写（不引外部 css/js），这一步可跳过


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
