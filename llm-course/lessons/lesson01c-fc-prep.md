# 前置知识专讲：做 Function Calling 前，把这几块补齐

> 每块都很短，配一个 30 秒小实验。做完这页，练习 02 的台阶就矮了。

## 1. 字典的嵌套取值（练 02 的"数据库"就是字典套字典）

```python
INVENTORY = {
    "6204": {"name": "轴承", "quantity": 150, "price": 12.5},
}

item = INVENTORY["6204"]        # 取出内层字典 → {"name": "轴承", ...}
print(item["name"])             # 轴承（链式取值：字典套字典就连续下标）
print(INVENTORY["6204"]["quantity"])   # 150（一步到位的写法）

# 判断某个键存不存在（Java: map.containsKey）
if "6204" in INVENTORY:
    print("有这个规格")

# 安全取值：键不存在不报错，给默认值
print(INVENTORY.get("不存在的", None))   # None
```

## 2. json 模块：Python 对象 ↔ JSON 字符串 的双向转换

| 方向 | 函数 | 用途 |
|---|---|---|
| 字符串 → 对象 | `json.loads(s)` | 解析模型返回的 JSON 文本，变成 dict/list 才能用 |
| 对象 → 字符串 | `json.dumps(obj)` | 把 dict 变成字符串传给别人（如回传给模型） |

```python
import json

s = '{"name": "轴承", "quantity": 150}'
d = json.loads(s)              # str → dict
print(d["quantity"])           # 150，能当字典用了

back = json.dumps(d, ensure_ascii=False)   # dict → str（ensure_ascii=False 中文不转义）
print(back)                    # {"name": "轴承", "quantity": 150}
```

**为什么练 02 处处是它**：网络传输只能传字符串。模型传给你的参数是字符串，你回传的结果也得是字符串；到了 Python 里处理时再转成 dict。

## 3. while True 死循环 + break（命令行交互的标准写法）

```python
while True:                    # 永远循环
    cmd = input("请输入：").strip()
    if cmd == "q":             # 满足条件就 break 跳出
        break
    print(f"你输入了 {cmd}")
```

`.strip()` 去掉首尾空格和换行——input() 的返回值永远要 strip，肌肉记忆。

## 4. SDK 响应对象：一层层"点"下去

响应对象就像嵌套的字典，但用 `.` 取：

```python
response.choices[0]                    # 一个 choice（choices 是列表，所以用 [0]）
response.choices[0].message.content    # 回答文本（前面用过）
response.choices[0].finish_reason      # "stop"=正常说话结束 / "tool_calls"=它想调你的函数
response.choices[0].message.tool_calls # 想调函数时才有值，是个列表
response.choices[0].message.tool_calls[0].function.name       # 函数名
response.choices[0].message.tool_calls[0].function.arguments  # 参数（JSON字符串！）
```

记忆法：**choices 是列表（用[0]），后面全是属性（用.），最后两层落在 function 上**。

## 5. 两回合协议全景图（先看熟，写的时候照着走）

```
第 1 回合请求:  messages=[system, user]  +  tools=[声明]
第 1 回合响应:  finish_reason="tool_calls"
               message.tool_calls = [申请]     ← 模型只是"点菜"

你的代码:      执行函数 → 得到结果 dict → json.dumps 成字符串

第 2 回合请求:  messages = [system, user,
                          assistant的tool_calls消息,     ← 原样回填
                          role="tool"的结果消息]          ← 带 tool_call_id
第 2 回合响应:  finish_reason="stop"，content=人话回答
```

## 自测（全对再去做练习 02）

1. `INVENTORY["6204"]["location"]` 取的是什么？
2. `"XL-21" not in INVENTORY` 什么时候为 True？
3. 模型返回的 `arguments` 是 dict 还是 str？要怎么处理才能 `args["spec"]`？
4. `finish_reason` 等于什么说明模型想调函数？
5. 第 2 回合的 messages 比第 1 回合多了哪两条？

（答案：1.位置字符串；2.键不存在时；3.str，json.loads；4."tool_calls"；5.assistant 的 tool_calls 消息 + role="tool" 的结果消息）
