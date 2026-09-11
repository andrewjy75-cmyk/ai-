r"""
练习 04 · 台阶 B 参考答案：用 ChatPromptTemplate + 链重写"结构化提取"
=======================================================================

对比自己的代码，重点看：
1. prompt 模板只写 {变量} 占位，不嵌 f-string、不带数据
2. chain = prompt | llm | StrOutputParser()：数据从左流到右
3. chain.invoke({...}) 填变量——换数据只改这里，链本身复用

运行（在 llm-course 目录下）：
    python solutions/ex04-langchain/step_b_reference.py
"""

import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

# temperature=0：提取类任务要稳定，不要创造性
llm = ChatOpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
    model=os.getenv("NEWAPI_MODEL"),
    temperature=0,
)

RAW_TEXT = """
今天上午老张来领了6个轴承型号6204，说是给2号生产线用的，仓管员小王发的货。
下午三点左右，维修班刘工拿走了2桶液压油L-HM46，登记是维修用。
还有一笔:紧固件M12螺栓一批,大概200个左右,第3车间领的,经手人赵敏。
"""

# ① 提示模板：{rules} 和 {raw_text} 是占位符，调用时才填
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是物资领用记录的结构化助手。{rules}"),
    ("user", "###\n{raw_text}\n###\n请提取领用条目，只返回JSON数组。"),
])

# ② 链：输入 dict → 模板填充 → 调模型 → 抽出纯文本
chain = prompt | llm | StrOutputParser()

RULES = (
    "只返回JSON数组，每项字段：material_name(物资名称), spec(规格型号), "
    "quantity(数量，填数字), unit(单位), department(领用部门), person(经手人)；"
    "模糊不清的填'未知'；数量模糊时按常识推断成数字。"
)

# ③ 调用：模板和数据分离——以后换一段文本，只改 raw_text
text = chain.invoke({
    "rules": RULES,
    "raw_text": RAW_TEXT,
})

if __name__ == "__main__":
    data = json.loads(text)
    for i, item in enumerate(data, 1):
        print(
            f"[{i}] {item['material_name']} {item.get('spec', '')} "
            f"x{item['quantity']}{item['unit']} | {item['department']} | {item['person']}"
        )
