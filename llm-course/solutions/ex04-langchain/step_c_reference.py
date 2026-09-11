r"""
练习 04 · 台阶 C 参考答案：用 LangChain 流式重写终端打字机
===========================================================

对比自己的代码，重点看：
1. llm.stream("...") 返回可迭代对象，for 直接遍历
2. chunk.content 直接就是文字——手写版要 chunk.choices[0].delta.content 再判空，
   LangChain 把这些结构封装了
3. load_dotenv() 必须调用（只 import 不会读 .env！）

运行（在 llm-course 目录下）：
    python solutions/ex04-langchain/step_c_reference.py
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
    model=os.getenv("NEWAPI_MODEL"),
    temperature=0.7,
)

if __name__ == "__main__":
    print("你：", end="")
    question = input()
    print("\n助手：", end="")
    for chunk in llm.stream(f"请用三句话回答：{question}"):
        piece = chunk.content
        if piece:   # 过滤空块
            print(piece, end="", flush=True)
    print()
