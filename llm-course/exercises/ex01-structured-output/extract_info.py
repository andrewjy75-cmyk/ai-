r"""
练习 01：结构化信息提取器 —— 你的作业骨架
==========================================

规则：只在 TODO 的地方写代码，其他地方不要动。
每个 TODO 标了【难度】，卡住了先看 exercises/ex01-structured-output/README.md 的提示阶梯。
提示还看不懂，再来问我。

运行方式（在 llm-course 目录下）：
    .venv\Scripts\Activate.ps1
    python exercises/ex01-structured-output/extract_info.py
"""

import json
import os
from json import JSONDecodeError

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 这些配置行已经给你写好了（.env 在课程根目录，读同一份配置）
client = OpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
MODEL = os.getenv("NEWAPI_MODEL")

# ---------- 第 1 步：定义输入 ----------
# TODO-1【简单】把题面里那段领料记录贴到这里，用三引号字符串
RAW_TEXT = """
今天上午老张来领了6个轴承型号6204，说是给2号生产线用的，仓管员小王发的货。
下午三点左右，维修班刘工拿走了2桶液压油L-HM46，登记是维修用。
还有一笔:紧固件M12螺栓一批,大概200个左右,第3车间领的,经手人赵敏。
晚上十点，物资部小陈领走了一批螺丝刀。
"""

# TODO-2【核心】写系统提示词 SYSTEM_PROMPT
# 要求覆盖：模型的任务是什么、只返回 JSON 数组不要其他文字、
# 6 个字段的名字和含义、缺字段填"未知"、模糊数量要推断
# 这一步是本练习的灵魂，写 10 分钟都值得
SYSTEM_PROMPT = """
你是一个物料领用结构化数据助手，帮助我提取数据，只能返回json数组格式。
一共有六个字段，分别是物料名称，领用人，单位，数量，领用部门，型号。单个json示例如下
{
  "name":"螺栓",
  "person":"老陈",
  "unit":"根",
  "quantity":200,
  "department":"仓管部",
  "spec":"M12"
}

如果某个字段判断不出来，模糊不清，则先填未知,但quantity必须是数字，未知则填0，必须严格按照这种格式，并且禁止增减字段
"""

# ---------- 第 2 步：调用模型 ----------
def extract(raw_text: str):
    """调用模型提取条目。成功返回列表，失败返回 None"""
    # TODO-3【核心】组 messages 列表：
    #   第 1 条：system 角色，内容是 SYSTEM_PROMPT
    #   第 2 条：user 角色，内容用 ### 分隔符把 raw_text 包住，结尾加一句提取指令
    messages = [
        # 在这里写两条消息
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "请帮我提取下面这段文字中的数据。\n" + RAW_TEXT}
    ]

    # TODO-4【核心】发起调用（注意 temperature 该设多少？想想为什么）
    response = client.chat.completions.create(
        # model=?  messages=?  temperature=?
        model=MODEL,
        messages=messages,
        temperature=0,
    )

    text = response.choices[0].message.content.strip()

    # 先看看模型到底返回了什么（验收标准要求打印原始返回）
    print(">>> 模型原始返回：")
    print(text)
    print()

    # TODO-5【进阶】防御性清洗：
    # 如果 text 以 ``` 开头，剥掉代码块包裹（思路见 README 提示 3）
    # 没被包住就直接跳过，别把正常文本弄坏

    # TODO-6【核心】用 try/except 把 text 解析成 Python 对象：
    #   成功 → return 解析结果
    #   失败（json.JSONDecodeError）→ 打印报错信息，return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"解析失败:{e}")
        return None


# ---------- 第 3 步：消费结果 ----------
if __name__ == "__main__":
    result = extract(RAW_TEXT)

    # TODO-7【简单】result 为 None 时：打印"提取失败"并结束
    # TODO-8【简单】result 不为 None 时：
    #   for 循环打印每条记录（用 f-string，格式自定，信息要全）
    #   最后打印合计总件数
    try:
        total=0
        if result is None:
            print("提取失败")
        else:
            print("提取成功")
            for item in result:
                print(f"{item['name']}: {item['quantity']}---{item['unit']}---{item['department']}---{item['spec']}---{item['person']}")
                print("-" * 20)
                total+=item['quantity']
            print(f"合计总数：{total}")
    except Exception as e:
        print(f"提取失败：{e}")
    pass
