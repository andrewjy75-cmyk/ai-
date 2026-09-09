r"""
练习 04 · 台阶 B：用 ChatPromptTemplate + 链 重写"结构化提取"
===============================================================

目标：把练习 01 的领料提取，用 LangChain 的提示模板 + 链重写。
重点体会：手写版手工拼 messages，框架版用模板变量 + 管道符。

运行：
    python exercises/ex04-langchain/step_b_extract.py
"""

import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

# TODO-B1【简单】创建 ChatOpenAI（照台阶 A），temperature=0（提取要稳定）
llm = None   # ← 你来改

# ---------- 输入数据（练习 01 的领料记录） ----------
RAW_TEXT = """
今天上午老张来领了6个轴承型号6204，说是给2号生产线用的，仓管员小王发的货。
下午三点左右，维修班刘工拿走了2桶液压油L-HM46，登记是维修用。
还有一笔:紧固件M12螺栓一批,大概200个左右,第3车间领的,经手人赵敏。
"""

# TODO-B2【核心·灵魂】用 ChatPromptTemplate.from_messages 定义提示模板
#   模板用 {变量} 占位，代替手工拼字符串
#   参考：
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", "你是物资领用记录的结构化助手。{rules}"),
#         ("user", "###\n{raw_text}\n###\n请提取领用条目，只返回JSON数组。"),
#     ])
prompt = None   # ← 你来改

# TODO-B3【核心】组装链：prompt | llm | StrOutputParser()
#   管道符 | 表示数据从左流到右，前一个的输出自动成为下一个的输入
#   参考：chain = prompt | llm | StrOutputParser()
chain = None    # ← 你来改

# TODO-B4【核心】调用链
#   chain.invoke({...}) 传一个 dict，填满模板里的所有 {变量}
#   返回的就是纯文本（StrOutputParser 已经把 .content 取出来了）
#   然后 json.loads 解析成列表打印
text = None     # ← 你来改

# ---------- 打印（已给你） ----------
if __name__ == "__main__":
    data = json.loads(text)
    for i, item in enumerate(data, 1):
        print(f"[{i}] {item['material_name']} x{item['quantity']}{item['unit']} | {item['person']}")
