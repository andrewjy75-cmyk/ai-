r"""
练习 03 · 台阶 A 参考答案：终端流式
=====================================

对比自己的代码，重点看：
1. stream=True 后 response 本身可迭代
2. 每个 chunk 取 delta.content，用 if piece: 过滤空块（开头/结尾常有空块）
3. print(x, end="", flush=True)：end="" 不换行，flush=True 强制立刻吐出

运行（在 llm-course 目录下）：
    python solutions/ex03-streaming-web/step_a_reference.py
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

print("你：", end="")
question = input()

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你是智能助手，回答用中文且简洁"},
        {"role": "user", "content": question},
    ],
    stream=True,          # 流式开关
)

print("\n助手：", end="")
for chunk in response:    # 每个 chunk 是模型生成的一小片增量
    piece = chunk.choices[0].delta.content
    if piece:             # 过滤空块
        print(piece, end="", flush=True)   # 逐字蹦出
print()
