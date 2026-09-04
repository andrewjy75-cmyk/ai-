r"""
练习 03 · 台阶 B：FastAPI 把流式包成 SSE 接口
================================================

目标：把台阶 A 的终端流式，升级成"别人能通过 HTTP 访问的接口"。
别人 POST 一个问题，接口把模型的回答**分批推送**回去（不是等全部生成完一次性返回）。

学两个新东西：
1. FastAPI：Python 最流行的 Web 框架（你比价工具已经用过，顺手）
2. StreamingResponse + SSE 格式：连接不关、分批写

先装依赖（装一次即可）：
    .venv\Scripts\pip install fastapi uvicorn

运行：
    python exercises/ex03-streaming-web/step_b_stream_api.py

验证（另开一个终端）：
    curl -N -X POST http://127.0.0.1:8000/chat ^
         -H "Content-Type: application/json" ^
         -d "{\"question\": \"用三句话介绍杭州\"}"
    （-N 是 no-buffer，让 curl 实时显示到达的数据）
    你会看到 data: 开头的文字一段段冒出来
"""

import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

app = FastAPI()


def llm_stream(question: str):
    """生成器：把模型的流式输出，转成 SSE 格式一段段 yield"""
    # TODO-B1【核心】调 create(..., stream=True)，遍历 chunks
    #   每拿到一段增量文字，就 yield 成 SSE 格式：
    #     f"data: {text}\n\n"
    #   SSE 协议格式：data: 内容，然后一个空行
    #   提示：把台阶 A 的遍历逻辑搬过来，print 换成 yield SSE 串
    response=client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一个智能助手，擅长回答问题，回答用中文且简洁明了"},
            {"role": "user", "content": question}
        ],
        stream=True
    )

    for chunk in response:
        piece=chunk.choices[0].delta.content
        if piece:
            yield f"data:{piece}\n\n"


@app.post("/chat")
async def chat(payload: dict):
    """接收 {"question": "..."}，返回 SSE 流"""
    # TODO-B2【简单】取 payload["question"]，
    #   用 StreamingResponse(llm_stream(question), media_type="text/event-stream") 返回

    return StreamingResponse(llm_stream(payload["question"]), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
