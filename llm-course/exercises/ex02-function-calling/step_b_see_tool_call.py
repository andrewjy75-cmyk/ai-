r"""
练习 02 · 台阶 B：亲眼看一次模型的"点菜单"（只发一回合，不回传）
==================================================================

目标：把 tools 声明发给模型，然后**只打印**它返回的 tool_calls 结构。
你要亲眼看清楚：模型返回的不是库存数据，而是一张"函数调用申请单"。
看懂了这个，台阶 C 的两回合协议就只剩"照单执行+回传"了。

TOOLS 声明本步直接给你（照抄即可，台阶 C 你再自己写一遍）。
你只填两个 TODO，各 3~5 行。

运行：
    python exercises/ex02-function-calling/step_b_see_tool_call.py
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

# 工具声明：这是给模型看的"菜单"，说明有什么函数、怎么传参
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_inventory",
            "description": "根据物资规格型号查询仓库库存，返回名称、数量、单位、位置、单价。当用户询问某种物资的库存、价格、位置时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "string",
                        "description": "物资的规格型号，如 6204、L-HM46、M12",
                    }
                },
                "required": ["spec"],
            },
        },
    }
]

SYSTEM_PROMPT = "你是物资库存助手，用中文简洁回答。"


def peek_tool_call(question: str):
    """发一回合带 tools 的请求，把模型的'点菜单'打印出来"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=TOOLS,
        temperature=0,
    )
    choice = response.choices[0]

    print(f"finish_reason = {choice.finish_reason}")
    print()

    if choice.finish_reason == "tool_calls":
        tool_call = choice.message.tool_calls[0]
        print("模型想调用的函数名：", tool_call.function.name)
        print("模型传来的参数（注意类型）：", repr(tool_call.function.arguments))

        # TODO-B1【3行】把 arguments（JSON字符串）用 json.loads 转成 dict，
        #   打印 args["spec"] 的值
        item=json.loads(tool_call.function.arguments)
        print(item["spec"])
    else:
        # 模型认为不需要调函数，直接回答了
        print("模型直接回答：", choice.message.content)


if __name__ == "__main__":
    # TODO-B2【1行】调用 peek_tool_call 三次，问题分别是：
    #   "轴承 6204 还有多少个？"   （应该触发 tool_calls）
    #   "液压油多少钱一桶？"       （应该触发 tool_calls，注意模型自己会从 INVENTORY 的键里挑 L-HM46）
    #   "你是谁？"                （不应该触发——观察 finish_reason 是什么）
    peek_tool_call("轴承 6204 还有多少个？")
    peek_tool_call("液压油多少钱一桶？")
    peek_tool_call("你是谁？")
    pass
