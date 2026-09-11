r"""
练习 03 · 台阶 B 参考答案：FastAPI 把流式包成 SSE 接口
=======================================================

对比自己的代码，重点看：
1. llm_stream 是"生成器"（函数里有 yield）——调用它不会执行，
   返回生成器对象；StreamingResponse 会 for 循环消费它
2. yield 的是 SSE 格式字符串：f"data:{piece}\n\n"
   （data: 前缀标记内容，空行标记一条消息结束）
3. StreamingResponse 的 media_type 必须写 text/event-stream

运行（在 llm-course 目录下）：
    python solutions/ex03-streaming-web/step_b_reference.py
验证（另开终端）：
    curl -N -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" ^
         -d "{\"question\": \"用三句话介绍杭州\"}"
"""

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
    """生成器：每次 yield 一小块 SSE 给客户端。"""
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
            yield f"data:{piece}\n\n"   # SSE 格式：data: 内容 + 空行


@app.post("/chat")
async def chat(payload: dict):
    """接收 {"question": "..."}，返回 SSE 流。"""
    question = payload["question"]
    return StreamingResponse(llm_stream(question), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
