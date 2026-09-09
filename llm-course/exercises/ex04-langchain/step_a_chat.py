r"""
练习 04 · 台阶 A：用 ChatOpenAI 重写"第一个调用"
=================================================

目标：把 hello_llm.py 用 LangChain 重写。
对比：手写版 vs LangChain 版，感受封装。

运行：
    python exercises/ex04-langchain/step_a_chat.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

# TODO-A1【核心】导入并创建 ChatOpenAI
#   base_url/api_key/model 三个参数和手写版完全一样（读 .env）
#   temperature 也直接传
# 对比：手写版要 new OpenAI(...) 再 client.chat.completions.create
#       LangChain 版一个对象搞定
llm = None   # ← 你来改

if __name__ == "__main__":
    # TODO-A2【简单】用 llm.invoke("...") 提问，打印 .content
    # 对比：手写版是 client.chat.completions.create(model=..., messages=...)
    #       然后 response.choices[0].message.content
    pass
