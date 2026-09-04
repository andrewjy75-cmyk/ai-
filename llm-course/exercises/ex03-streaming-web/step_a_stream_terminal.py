r"""
练习 03 · 台阶 A：终端版流式输出（纯 Python，不碰 Web）
==========================================================

目标：让模型的回答在终端里逐字蹦出来，而不是等 5 秒后一次性打印。
核心就两个新东西：stream=True 参数 + 遍历 chunks 取增量。

运行：
    python exercises/ex03-streaming-web/step_a_stream_terminal.py
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


def chat_stream(question: str):
    """带流式的对话。逐块 yield 出模型生成的内容"""
    # TODO-A1【核心】调用 chat.completions.create：
    #   model=MODEL, messages=[system+user], stream=True
    #   返回的 response 可以 for 遍历，每个 chunk 是一小片增量
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"你是一个智能助手，擅长帮助我解决问题，回答用中文且简洁明了"},
            {"role":"user","content":question}
        ],
        temperature=0.5,
        stream=True
    )   # ← 你来改

    # TODO-A2【核心】遍历 chunks，取每块的增量文本
    #   chunk.choices[0].delta.content 是这一小片的文字（可能为空）
    #   用 if 过滤空的，yield 出来

    for chunk in response:
        piece=chunk.choices[0].delta.content
        if piece :
            yield piece


if __name__ == "__main__":
    question = input("你：").strip()
    print("\n助手：", end="")

    # TODO-A3【简单】for 循环消费 chat_stream 的每个片段，
    #   print(片段, end="", flush=True)   ← 打字机效果的关键！
    #   end="" 不换行，flush=True 强制立刻输出
    for picec in chat_stream(question):
        print(picec,end="",flush=True)


    print()   # 最后补一个换行
