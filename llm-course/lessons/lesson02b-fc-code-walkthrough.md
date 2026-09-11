# 前置知识专讲 2：写 Function Calling 代码前的四个概念

> 台阶 C 卡壳，99% 是这四个概念没吃透。每个概念配"错误写法 vs 正确写法"。
> 读完再改代码，每改一处跑一次。

## 概念 1：变量名 vs 字符串字面量（`'spec'` ≠ `spec`）

```python
spec = "6204"                 # spec 是变量，装着 "6204"

INVENTORY[spec]               # ✅ 取键 "6204" → 轴承那条记录
INVENTORY['spec']             # ❌ 取键 "spec"（字面量！）→ 字典里没有这个键
```

判别方法：**带引号 = 固定文本；不带引号 = 变量里装的东西**。
函数参数 `def query_inventory(spec)` 里的 spec 是变量，用的时候写 `INVENTORY[spec]`。

Java 类比：`map.get("spec")` 是取键 "spec"；`map.get(spec)` 是取 spec 变量的值当键。

## 概念 2：json.loads 和 json.dumps 的方向（谁进谁出）

```python
args = json.loads(arguments_str)     # 字符串 → dict（收到模型的参数后，转成能用的）
result_str = json.dumps(result_dict, ensure_ascii=False)   # dict → 字符串（回传给模型前，转成能传的）
```

口诀：**收进来 loads，发出去 dumps**。模型那边只会读字符串，你的代码这边只方便用 dict。

## 概念 3：choice、message、tool_calls 三层关系

```python
choice = response.choices[0]        # 一次回复的整体（含 finish_reason 和 message）
choice.message                      # 模型这条回复消息本身（assistant 角色的那条）
choice.message.tool_calls           # 模型想调函数时才有值；是个【列表】（可能申请调多个）

choice.message.tool_calls[0].function.name        # 函数名
choice.message.tool_calls[0].function.arguments   # 参数 JSON 字符串
choice.message.tool_calls[0].id                   # 这张申请单的编号（回传结果时要对上号）
```

**回填历史时 append 的是整个 message 对象**（不是 choice）：

```python
messages.append(choice.message)     # ✅ SDK 对象直接进列表
messages.append(choice)             # ❌ choice 不是消息，序列化会炸
```

## 概念 4：第二回合的 messages 必须长这样

```
[system,
 user: "轴承还有多少？",                      ← 第 1 回合的
 assistant(tool_calls=[申请单]),              ← 模型那条，原样回填
 tool(tool_call_id=申请单编号, content=结果)]  ← 你的执行结果，编号对上
```

**漏一条、编号对不上，第二回合必报 400。** 逻辑：模型要看完整的"申请 → 结果"对应关系才知道自己在等什么数据。

## 执行引擎的正确工序（概念 2 + 3 的合体）

```
收到 tool_call（一张申请单）：
  1. name = tool_call.function.name              # 看菜单上点的什么菜
  2. args = json.loads(tool_call.function.arguments)   # 读懂菜单细节（loads！）
  3. result = query_inventory(args["spec"])      # ★ 真的去做菜：调你自己的函数
  4. return json.dumps(result, ensure_ascii=False)     # 装盘外送（dumps！）
```

最容易漏的是第 3 步——**申请单解析得再漂亮，不调真函数就永远没有菜**。
（扩展：函数多了以后，第 3 步要按 name 路由到不同函数；现在只有一个函数可以先写死。）

## 自测（对着你的 inventory_assistant.py 找茬）

1. 你的 `INVENTORY['spec']` 命中了概念几的坑？
2. 你的 execute_tool_call 返回了"解析后的申请单"——漏了上面工序的第几步？
3. 你 append 的是 choice 还是 choice.message？
4. execute_tool_call(tool_call=user_input) —— user_input 是什么类型的东西？它有 .function 属性吗？该传什么？
