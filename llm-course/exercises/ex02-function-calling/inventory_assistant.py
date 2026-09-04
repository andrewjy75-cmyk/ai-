r"""
练习 02：Function Calling —— 库存查询助手（你的作业骨架）
==========================================================

规则：只在 TODO 处写代码。卡住看同目录 README.md 的提示阶梯。

运行方式（在 llm-course 目录下）：
    .venv\Scripts\Activate.ps1
    python exercises/ex02-function-calling/inventory_assistant.py
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

# ---------- 已给你：模拟数据库 ----------
INVENTORY = {
    "6204":  {"name": "轴承",   "quantity": 150, "unit": "个", "location": "A区-3号货架", "price": 12.5},
    "L-HM46": {"name": "液压油", "quantity": 45,  "unit": "桶", "location": "B区-1号货架", "price": 89.0},
    "M12":   {"name": "螺栓",   "quantity": 800, "unit": "个", "location": "A区-1号货架", "price": 0.5},
    "XL-21": {"name": "配电箱", "quantity": 0,   "unit": "台", "location": "C区-2号货架", "price": 650.0},
}

# TODO-1【核心】写查询函数：按 spec 查字典，查到返回整条记录（dict），查不到返回错误 dict
def query_inventory(spec: str):
    if spec in INVENTORY:
        return INVENTORY[spec]
    else:
        return None



# TODO-2【核心·灵魂】写工具声明 TOOLS
# 结构：[{"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}]
# description 要让模型明白：什么时候该调这个函数、参数是什么意思
TOOLS = [
    # 你来写
    {
        "type":"function",
        "function":{
            "name":"query_inventory",
            "description":"这是一个根据规格型号查询物资详细信息的方法，用户传入物资的规格型号，返回物资详细信息（名称，数量，单位，位置，单价，严格按照这个返回，禁止增加或者减少字段）。在用户询问物资库存，并传入规格型号时调用",
            "parameters":{
                "type":"object",
                "properties": {
                    "spec":{
                        "type":"string",
                        "description":"物资的规格型号，如L-324等"
                    }
                },
                "required":["spec"]
            }

        }
    }
]

# TODO-3【简单】system 提示词：告诉模型它是"物资库存助手"，用中文简洁回答
SYSTEM_PROMPT = """
你是一个掌管物资数据的物资库存助手，擅长用中文总结物资数据并简洁回答
"""


# TODO-4【核心】执行引擎：收到模型的工具调用申请，执行对应函数并返回结果字符串
def execute_tool_call(tool_call):
    """
    tool_call 是模型发来的调用申请：
      tool_call.function.name       → 函数名（字符串）
      tool_call.function.arguments  → 参数（JSON 字符串，需要 json.loads）
    返回：函数执行结果的 JSON 字符串（ensure_ascii=False 保留中文）
    """
    print(f"函数名：{tool_call.function.name}")
    print(f"参数：{tool_call.function.arguments}")
    args=json.loads(tool_call.function.arguments)
    result=query_inventory(args['spec'])
    return json.dumps(result,ensure_ascii=False)


def chat_once(messages: list):
    """发起一次对话请求。temperature 该设几？想想这是查询任务"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        temperature=0,
    )
    return response


# ---------- 主循环（已给你，看懂逻辑即可） ----------
if __name__ == "__main__":
    print("=== 库存查询助手（输入 q 退出）===")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in ("q", "exit", "退出"):
            print("再见！")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        response = chat_once(messages)
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            # TODO-5【核心】工具调用回合：
            #   1. 把模型这条 tool_calls 消息原样 append 进 messages
            #   2. 对每个 tool_call 调 execute_tool_call，把结果按
            #      {"role": "tool", "tool_call_id": ..., "content": ...} append 进 messages
            #   3. 带完整 messages 再调一次 chat_once，打印最终回答
            messages.append(choice.message)
            # 2. 处理每张申请单，回传结果
            for tool_call in choice.message.tool_calls:

                result_str = execute_tool_call(tool_call)  # 传的是申请单对象！
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,  # 申请单编号，必须对上
                    "content": result_str,
                })
            # 3. 带完整历史再问一次
            response2 = chat_once(messages)
            print(response2.choices[0].message.content)

        else:
            # TODO-6【简单】普通回答：把模型回复打印出来，
            #   并把这条 assistant 消息 append 进 messages（多轮对话的记忆，还记得吗）
            print(choice.message.content)
