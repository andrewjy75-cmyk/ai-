r"""
练习 02 · 台阶 A：纯 Python 库存查询（不碰大模型）
==================================================

目标：把字典、函数、while 循环练熟。这一步全程没有 LLM，
就是普通 Python——但它是台阶 C 里"你的函数"那一半。

运行：
    python exercises/ex02-function-calling/step_a_inventory_cli.py

预期交互效果：
    请输入规格（q 退出）：6204
    轴承 | 库存 150 个 | A区-3号货架 | 12.5 元
    请输入规格（q 退出）：XX-99
    查无此物
    请输入规格（q 退出）：q
"""

INVENTORY = {
    "6204":  {"name": "轴承",   "quantity": 150, "unit": "个", "location": "A区-3号货架", "price": 12.5},
    "L-HM46": {"name": "液压油", "quantity": 45,  "unit": "桶", "location": "B区-1号货架", "price": 89.0},
    "M12":   {"name": "螺栓",   "quantity": 800, "unit": "个", "location": "A区-1号货架", "price": 0.5},
    "XL-21": {"name": "配电箱", "quantity": 0,   "unit": "台", "location": "C区-2号货架", "price": 650.0},
}


# TODO-A1：写 query_inventory(spec)
#   查到 → 返回内层那个 dict
#   查不到 → 返回 None
#   （前置知识专讲第 1 节：in 判断 / .get()）
def query_inventory(spec: str):
    if spec in INVENTORY:
        return INVENTORY[spec]
    else:
        return None


if __name__ == "__main__":
    # TODO-A2：while True 循环
    #   input 提示"请输入规格（q 退出）"，输入 q 或 退出 就 break
    #   调 query_inventory 查询：
    #     查到了 → 用 f-string 打印一行：名字 | 库存 X 单位 | 位置 | 价格 元
    #     没查到 → 打印"查无此物"
    #   （注意：库存为 0 的 XL-21 也能查到记录，只是数量是 0，不要把它当成查不到）

    while True:
        spec = input("请输入规格（q 退出）").strip().upper()
        if spec in ('Q','退出'):
            print("已退出程序")
            break
        else:
            item=query_inventory(spec)
            if item is None:
                print("查无此物")
            else:
                print(f"名称：{item['name']} | 数量：{item['quantity']} | 单位：{item['unit']} | 位置：{item['location']} | 单价：{item['price']}")
