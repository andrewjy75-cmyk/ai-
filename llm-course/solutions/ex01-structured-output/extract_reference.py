r"""
第 2 课：Prompt 实战技巧 + 结构化输出
======================================

为什么这课重要：聊天谁都会，但做应用时，模型的输出是要**给程序用的**。
程序需要的是规整的数据（JSON），不是一段散文。这一课教你把"会聊天的模型"
变成"可靠的接口"。

核心任务：给它一段乱糟糟的领料记录，让它提取成规整的 JSON。

Prompt 的四个实战技巧（本课代码里都有用到）：
1. 设定角色：告诉模型它是谁，输出风格立刻变专业
2. 明确约束：直接说"只返回 JSON，不要任何其他文字"
3. 给出示例（few-shot）：举一个输入输出样例，模型模仿能力极强
4. 用分隔符隔离内容：三引号/### 把"指令"和"待处理文本"分开，防止混淆

运行方式：
    python lessons/lesson02-structured-output/extract_info.py
"""

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 密钥等配置一律从 .env 读（和第 1 课同一个 .env 文件），绝不写死在代码里
client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

# ---------- 待提取的原始文本（模拟现实：格式乱、字段不齐） ----------
RAW_TEXT = """
今天上午老张来领了6个轴承型号6204，说是给2号生产线用的，仓管员小王发的货。
下午三点左右，维修班刘工拿走了2桶液压油L-HM46，登记是维修用。
还有一笔:紧固件M12螺栓一批,大概200个左右,第3车间领的,经手人赵敏。
"""

# ---------- 精心设计的 Prompt（重点看注释） ----------
SYSTEM_PROMPT = """你是一个物资领用记录的结构化助手。你的任务是：
从用户提供的原始领料记录文本中，提取出所有领用条目。

要求：
1. 只返回 JSON 数组，不要返回任何解释、寒暄或 markdown 代码块标记
2. 每个条目包含以下字段：
   - material_name: 物资名称（字符串）
   - spec: 规格型号（字符串，原文没有就填 "未知"）
   - quantity: 数量（数字，"一批""大概200个"这类模糊描述要推断出最可能的数字）
   - unit: 单位（字符串，如 个/桶/批）
   - department: 领用部门（字符串，原文没有就填 "未知"）
   - person: 经手人（字符串，原文没有就填 "未知"）
3. 字段名必须和上面完全一致，不要增减字段"""

# few-shot：给模型看一个"输入→输出"的样例，它的输出格式会非常稳定
FEW_SHOT_EXAMPLE = """
示例输入：
张三领了3袋水泥，给1号工地。

示例输出：
[{"material_name": "水泥", "spec": "未知", "quantity": 3, "unit": "袋", "department": "1号工地", "person": "张三"}]
"""


def extract(raw_text: str) -> list | None:
    """调用模型提取条目，返回解析后的列表；失败返回 None"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": FEW_SHOT_EXAMPLE},   # few-shot 也是对话消息
            {"role": "assistant", "content": "明白了，我将严格按示例格式只返回 JSON 数组。"},
            # 分隔符：### 包住待处理文本，和指令清晰隔开
            {"role": "user", "content": f"###\n{raw_text}\n###\n请提取上面的领用条目。"},
        ],
        temperature=0,      # 提取任务要"稳定"，不要创造性 → 直接 0
    )

    text = response.choices[0].message.content.strip()
    print(">>> 模型原始返回：")
    print(text)
    print()

    # 模型偶尔会自作主张包一层 ```json ... ```，做点防御性清洗
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        data = json.loads(text)     # JSON 字符串 → Python 列表/字典
        return data
    except json.JSONDecodeError as e:
        print(f"!!! JSON 解析失败：{e}")
        return None


if __name__ == "__main__":
    result = extract(RAW_TEXT)

    if result is None:
        print("提取失败。实战中的标准做法：带着报错信息让模型重试（见课后练习3）")
    else:
        print(f">>> 解析成功，共 {len(result)} 条记录，程序可以直接使用了：\n")
        total = 0
        for i, item in enumerate(result, 1):
            print(f"[{i}] {item['material_name']}（{item['spec']}）"
                  f" x{item['quantity']}{item['unit']}"
                  f" | 部门：{item['department']} | 经手：{item['person']}")
            total += item['quantity']
        print(f"\n合计 {total} 件 —— 这就是'给程序用的数据'，可以直接写库/生成单据")

# ========== 课后练习（必做）==========
# 1. 在 RAW_TEXT 里加一条故意很乱的记录（比如"螺丝钉拿了一盒"），看模型怎么推断
# 2. 把 SYSTEM_PROMPT 里的字段删掉一个（如 person），看输出有什么变化
# 3. 【进阶】实现"解析失败自动重试"：extract 失败时，把错误信息发给模型
#    "你上次的输出无法被 json.loads 解析，报错是 xxx，请重新只返回 JSON"
#    —— 这是生产环境的真实套路，叫"自动纠错循环"
