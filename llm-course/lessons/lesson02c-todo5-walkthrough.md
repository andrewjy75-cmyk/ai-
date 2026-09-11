# 前置知识专讲 3：TODO-5 逐行拆解——工具回合到底发生了什么

> 抄代码不丢人，抄完搞懂就是自己的。这篇把 TODO-5 的每一行掰开讲：
> 为什么必须有它、删了会怎样。配合你自己的 inventory_assistant.py 对照看。

## 先建立画面：一个前厅 + 后厨的比喻

```
你        = 顾客（打字提问）
模型      = 前厅服务员（能说会道，但进不了后厨）
你的代码   = 后厨（唯一能真正拿食材做菜的地方）
messages  = 点菜单账本（每一笔往来都记录在案）
```

规则只有一条：**服务员不许进后厨**。他只能递单子，后厨做完把菜端给他，他才能向顾客描述这道菜。

TODO-5 干的事，就是把"递单子 → 做菜 → 交菜 → 服务员复述"这四步串起来。

## 逐行拆解

### 第 1 行：`messages.append(choice.message)` —— 把服务员的点菜单存档

模型的回复（choice.message）这次不是普通聊天，而是一张"申请单"：

> "我要调 query_inventory，参数 spec='L-HM46'"（finish_reason=tool_calls）

为什么要存回 messages？——**账本必须完整**。第二次请求时，模型要看着"我之前申请了什么"才知道自己在等哪道菜。删了这行，第二回合 API 直接报 400（账本对不上）。

回忆第 1 课补充讲义：messages 是你手动维护的对话记忆，**每次调用都全量重发**。这条申请单也是对话的一部分，当然也要进账本。

### 第 2 行：`for tool_call in choice.message.tool_calls:` —— 逐张处理申请单

为什么是 for 循环？因为 `tool_calls` 是**列表**——模型可以一次申请调多个函数（比如"轴承和螺栓都查一下"）。现在通常只有一张，但代码要按协议的本来面目写。

### 第 3 行：`result_str = execute_tool_call(tool_call)` —— 后厨做菜

把申请单（tool_call 对象）交给你的执行引擎。里面发生的事（见你的 execute_tool_call）：

```
json.loads 申请单参数 → 调 query_inventory 真的查库存 → json.dumps 结果
```

这是**全流程唯一碰到真实数据的地方**。模型从头到尾没碰过 INVENTORY 字典——它只递单子，菜是你做的。安全边界就在这。

### 第 4 行：`messages.append({"role": "tool", ...})` —— 把菜端回去、登记入账

```python
{
    "role": "tool",               ← 告诉 API：这条消息是"工具的输出"（第 4 种角色！）
    "tool_call_id": tool_call.id, ← 申请单编号。模型发单时有 id，回菜必须带同一个 id
    "content": result_str,        ← 菜本身（库存数据的 JSON 字符串）
}
```

三个字段缺一不可：
- role 错了 → API 不认（"tool" 是协议规定的角色名）
- tool_call_id 对不上 → 模型不知道这盘菜对应哪张单子（尤其多张单子时）
- content 忘了 dumps 成字符串 → SDK 序列化报错

### 第 5~6 行：`response2 = chat_once(messages)` + 打印 —— 服务员拿到菜，向顾客复述

第二次请求：账本里 [system, user, 申请单, 菜] 全在。模型看到自己要的数据到了，这次 finish_reason 变回 "stop"，content 里就是人话回答：

> "液压油 L-HM46 当前库存 45 桶，位于 B区-1号货架，单价 89 元。"

注意它回答里的数字（45、89、B区）——**全部来自你回传的 content，模型自己编不出来**。这就是验证闭环是否真通了的标志。

## 全流程时序（最终版，背下来）

```
你: "查L-HM46"
    ↓ messages=[system, user]
模型: finish_reason=tool_calls，递申请单          ← 第1次API调用返回
你: 账本记下申请单（append choice.message）
你: 后厨做菜（execute_tool_call → 真函数）
你: 账本记下菜（append role=tool, id对上）
    ↓ messages=[system, user, 申请单, 菜]
模型: finish_reason=stop，"库存45桶…"            ← 第2次API调用返回
你: 打印回答
```

**两次 API 调用、一次函数执行**——这就是 Function Calling 的全部成本。

## 自测：删掉会怎样？（在心里推演，别真删）

1. 删 `messages.append(choice.message)` → 第二次请求怎样？
2. 删 `tool_call_id` → 模型会怎样？
3. execute_tool_call 里不调 query_inventory，return "查到了" → 模型会说什么？
（答案：1.报400，账本断裂；2.不知道菜对应哪张单；3.编造一个假库存——数据造假模型无法识别，这正说明执行权在你的代码手里）
