r"""
练习 02 参考答案：Function Calling 库存查询助手（标准完整版）
================================================================

对比自己的代码，重点看：
1. query_inventory 查不到时返回错误 dict 而非 None（让模型自己解释，更稳）
2. 主循环里：无论工具回合还是普通回合，assistant 消息都 append 回 messages
   （普通回合容易漏——漏了多轮对话就"失忆"）
3. 循环处理多个 tool_call（for 循环而非只取 [0]）

运行（在 llm-course 目录下）：
    python solutions/ex02-function-calling/inventory_reference.py
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

# ---------- 模拟数据库（题面给的） ----------
INVENTORY = {
    "6204":   {"name": "轴承",   "quantity": 150, "unit": "个", "location": "A区-3号货架", "price": 12.5},
    "L-HM46": {"name": "液压油", "quantity": 45,  "unit": "桶", "location": "B区-1号货架", "price": 89.0},
    "M12":    {"name": "螺栓",   "quantity": 800, "unit": "个", "location": "A区-1号货架", "price": 0.5},
    "XL-21":  {"name": "配电箱", "quantity": 0,   "unit": "台", "location": "C区-2号货架", "price": 650.0},
}


def query_inventory(spec: str) -> dict:
    """按规格型号查库存。查到返回整条记录；查不到返回错误信息（让模型向用户解释）。"""
    if spec in INVENTORY:
        return INVENTORY[spec]
    return {"error": f"未找到规格型号为 {spec} 的物资"}


# ---------- 工具声明 ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_inventory",
            "description": (
                "当用户询问物资的库存数量、位置、单价等信息时调用。"
                "入参是物资的规格型号，例如 6204、L-HM46、M12。"
            ),
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

SYSTEM_PROMPT = "你是物资库存查询助手，根据查询结果用中文简洁回答用户；查不到就如实说明。"


def execute_tool_call(tool_call) -> str:
    """执行模型的函数调用申请，返回 JSON 字符串结果。

    tool_call.function.name      → 函数名
    tool_call.function.arguments → JSON 字符串（要 json.loads 才能用）
    """
    args = json.loads(tool_call.function.arguments)
    result = query_inventory(args["spec"])
    return json.dumps(result, ensure_ascii=False)


def chat_once(messages: list):
    """发起一次对话请求。查询类任务 temperature=0 保证稳定。"""
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        temperature=0,
    )


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
            # ---- 工具回合 ----
            # 1. 把模型这条 tool_calls 消息原样回填（SDK 对象直接 append）
            messages.append(choice.message)
            # 2. 每个申请单执行一次，结果用 role="tool" 回传（tool_call_id 必须对上）
            for tool_call in choice.message.tool_calls:
                print(f"  [调用工具] {tool_call.function.name}({tool_call.function.arguments})")
                result_str = execute_tool_call(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                })
            # 3. 带完整历史二次请求 → 模型组织自然语言
            response2 = chat_once(messages)
            reply = response2.choices[0].message
            print(f"助手：{reply.content}")
            # ★ 关键：把这次回答也记进历史（否则下一轮提问会失忆）
            messages.append(reply)
        else:
            # ---- 普通回合 ----
            reply = choice.message
            print(f"助手：{reply.content}")
            # ★ 普通回合同样要 append，这是多轮对话记忆的根基
            messages.append(reply)
