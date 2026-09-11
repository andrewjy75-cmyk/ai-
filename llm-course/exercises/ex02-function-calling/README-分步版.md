# 练习 02（重制版）：Function Calling 拆成三级台阶

> 原版一次压太多前置知识，已拆解。**按 A → B → C 顺序做**，
> 每步只引入一个新概念，前一步的产出就是后一步的原料。

## 台阶 A：纯 Python 库存查询（0% 大模型）

文件：`step_a_inventory_cli.py`（TODO-A1、A2）
练什么：字典取值、in 判断、while 循环、f-string——全是台阶 C 里"你的函数"那一半。
过关标准：输入 6204 打出轴承信息，输入 XX-99 打出"查无此物"，q 退出。
预期 15 分钟。**这就是普通 Python 编程，和大模型无关。**

## 台阶 B：亲眼看一次模型的"点菜单"（一回合，不回传）

文件：`step_b_see_tool_call.py`（TODO-B1、B2）
练什么：把 TOOLS 声明发给模型，**只打印**它返回的 tool_calls 结构。
你会亲眼看到：finish_reason 变成 "tool_calls"，模型递上来的是
函数名 + JSON 字符串参数——它"点菜"了，但没人做菜。
过关标准：三个问题跑完，前两个触发 tool_calls 且你解析出了 spec，
"你是谁"没触发（finish_reason=stop）。
预期 15 分钟。TOOLS 声明本步直接给你，照抄即可。

## 台阶 C：完整两回合（原版练习 02）

文件：`inventory_assistant.py`（TODO 1~6，题面见本目录原 README）
做完 A 和 B，这一步只剩下：
1. 把台阶 A 的 query_inventory 搬进来
2. 把台阶 B 的 TOOLS 声明搬进来（自己重新写一遍，加深理解）
3. 补上"执行函数 + role=tool 回传 + 二次调用"的闭环
预期 30~45 分钟。卡住时问自己：现在卡的是 Python 语法，还是两回合协议？

## 前置知识

`lessons/lesson02a-fc-prep.md` —— 字典嵌套 / json 模块 / while 循环 /
SDK 响应对象取值 / 两回合协议全景图，末尾有 5 题自测。

## 顺序建议

1. 先读 lesson02a-fc-prep.md，做对末尾自测
2. 台阶 A → 跑通 → 台阶 B → 跑通 → 台阶 C
3. 每个台阶跑通都可以贴给我看，不用攒到最后
