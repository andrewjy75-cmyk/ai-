r"""
练习 04 · 台阶 A 参考答案：用 ChatOpenAI 重写"第一个调用"
===========================================================

对比自己的代码，重点看：
1. ChatOpenAI 一个对象封装了 client + model + temperature
2. llm.invoke("...") 一步调用，.content 直接拿文本
   （手写版：client.chat.completions.create(model=..., messages=[...]) 再取
    response.choices[0].message.content）
3. 环境变量名用大写（.env 里就是大写，Linux 上大小写敏感）

运行（在 llm-course 目录下）：
    python solutions/ex04-langchain/step_a_reference.py
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
    answer = llm.invoke("用一句话解释什么是API")
    print(answer.content)
