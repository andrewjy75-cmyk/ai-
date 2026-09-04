# 练习 02：Function Calling —— 库存查询助手

> 目标：用户用自然语言提问，**模型自己决定**调用你写的本地函数查数据，再组织回答。
> 这是"模型说话"到"模型干活"的质变，是第 7 课 Agent 的地基。

## 题面

写 `inventory_assistant.py`，实现一个命令行问答：

```
你问：轴承 6204 还有多少个？
助手：仓库现有轴承 6204 共 150 个，位于 A 区 3 号货架，单价 12.5 元。

你问：液压油多少钱一桶？还有货吗？
助手：L-HM46 液压油单价 89 元/桶，当前库存 45 桶，有货。
```

**核心设定**：
- "数据库"用一个硬编码的 Python 字典模拟（库存数据我给你）
- 你要把"查询库存"这个函数**以工具的形式声明给模型**（tools 参数）
- 模型不直接知道库存数据！它只会返回"我要调用 query_inventory(参数xxx)"，
  **你的代码**执行函数、把结果回传，模型才组织成自然语言回答
- 循环对话：每轮问答都带上完整 messages 历史

## 模拟库存数据（直接用）

```python
INVENTORY = {
    "6204":  {"name": "轴承",   "quantity": 150, "unit": "个", "location": "A区-3号货架", "price": 12.5},
    "L-HM46": {"name": "液压油", "quantity": 45,  "unit": "桶", "location": "B区-1号货架", "price": 89.0},
    "M12":   {"name": "螺栓",   "quantity": 800, "unit": "个", "location": "A区-1号货架", "price": 0.5},
    "XL-21": {"name": "配电箱", "quantity": 0,   "unit": "台", "location": "C区-2号货架", "price": 650.0},
}
```

## Function Calling 的完整回合（先理解再动手）

```
第 1 回合：你发 [system, user:"轴承还有多少"] + tools 声明
          → 模型回：finish_reason="tool_calls"，想调 query_inventory(spec="6204")
          （注意：模型此时没有库存数据，它只是"提出申请"）

第 2 回合：你的代码执行 query_inventory("6204") 得到结果，
          把两条消息追加进 messages：
          1. 模型那条 tool_calls 消息（assistant 角色，原样回填）
          2. 函数执行结果（role="tool"，content=JSON字符串）
          再发一次请求
          → 模型回：正常文本，"轴承 6204 还有 150 个……"
```

**关键认知**：模型从不直接碰你的数据。它只发"函数调用申请"，执行权永远在你手里——这就是为什么它能安全地"查数据库"。

## 验收标准

- [ ] 定义 `query_inventory(spec)` 函数，查不到返回 None
- [ ] tools 声明里函数名、参数名、参数描述写清楚（模型靠描述决定怎么传参！）
- [ ] 第一轮响应的 `finish_reason == "tool_calls"` 时，正确取出工具名和参数并执行
- [ ] 工具结果用 `role="tool"` 回传（附 `tool_call_id`），第二轮拿到自然语言回答
- [ ] 主循环：input() 问答，退出词自定（如 q/exit），每轮历史累加
- [ ] 用户问"今天天气怎么样"（无关问题）时，模型应正常聊天而不是乱调函数

## 提示阶梯

<details>
<summary>提示 1：程序骨架（4 块）</summary>

1. `INVENTORY` 字典 + `query_inventory(spec)` 函数
2. `TOOLS` 列表：一个 dict，`"type": "function"`，function 里写 name/description/parameters
3. 一个循环：input() → messages.append(user) → 第一次调用 API
4. 判断 `response.choices[0].finish_reason`：
   是 "tool_calls" → 执行函数、追加两条消息、第二次调用 API → 打印回答；
   不是 → 直接打印回答

</details>

<details>
<summary>提示 2：关键 API 细节</summary>

- 取模型申请：`response.choices[0].message.tool_calls[0]`，其 `.function.name` 和 `.function.arguments`（注意 arguments 是 **JSON 字符串**，要 `json.loads`）
- 回填 assistant 消息：`messages.append(response.choices[0].message)`（SDK 对象直接 append 即可）
- 回传结果：`{"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(结果, ensure_ascii=False)}`
- tools 声明的 parameters 用 JSON Schema 格式：`{"type": "object", "properties": {"spec": {"type": "string", "description": "..."}}, "required": ["spec"]}`

</details>

<details>
<summary>提示 3：容易踩的坑</summary>

- 第二次调用必须带**完整 messages**（含 assistant 的 tool_calls 消息 + tool 结果），少了会报 400
- `role="tool"` 的消息必须带正确的 `tool_call_id`，对不上也报 400
- 函数查不到时返回什么？返回 `{"error": "未找到该物资"}` 让模型自己向用户解释，比返回 None 更稳
- description 写中文就行，模型看得懂；但描述质量直接决定传参质量——把"参数是什么"写清楚

</details>

## 交作业

跑通后贴两段对话实录（一次问库存、一次问天气）+ 你的代码，我重点 review：
tools 声明怎么写的、第二回合 messages 是怎么追加的。

## 参考答案

`solutions/ex02-function-calling/inventory_reference.py`（写完跑通再看）
