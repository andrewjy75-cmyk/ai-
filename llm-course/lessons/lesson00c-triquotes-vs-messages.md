# 第 0 课补充：`"""三引号"""` 和 messages 列表是什么关系？

> 一个常见混淆：三引号是**字符串的书写格式**，messages 是**发给 API 的数据结构**。
> 它们不是二选一的关系，而是嵌套关系——字符串被装进字典里。

## 1. 三引号只是"多行字符串"的写法

```python
a = "hello"           # 单行字符串
b = 'hello'           # 和上面完全一样
c = """hello
world"""              # 也能跨多行，仅此而已

print(type(a), type(b), type(c))   # 全都是 <class 'str'>
```

三引号字符串和普通字符串是**同一个类型**，唯一区别：可以原样写多行、保留换行。
Prompt 通常很长很多行，用三引号写可读性好。

Java 类比：Java 15+ 的文本块（text block）——`String s = """ 多行内容 """`，一模一样的动机。

## 2. messages 是 API 规定的"信封格式"

API 不收"裸文本"，它收结构化的 JSON。SDK 帮你把 Python 对象转成 JSON：

```python
SYSTEM_PROMPT = """你是物资领用记录的结构化助手……"""   # ← str，内容素材

messages = [                                          # ← list，信封
    {"role": "system", "content": SYSTEM_PROMPT},     # ← dict，一张卡片
]
```

最终发出去的请求体长这样（SDK 自动完成）：

```json
{
  "model": "glm-5.3-flash",
  "messages": [
    {"role": "system", "content": "你是物资领用记录的结构化助手……"}
  ]
}
```

Java 类比：`List<Map<String, String>>`，最后被 Jackson 序列化成请求体。

## 3. 数据流一句话

```
三引号字符串（素材） → 装进字典的 content 字段（贴上 role 标签）→ 装进列表（按顺序排好）→ SDK 序列化成 JSON → 发给服务器
```

## 4. 30 秒自证

随便找个文件跑两行：

```python
SYSTEM_PROMPT = """你是助手"""
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
print(type(SYSTEM_PROMPT))   # <class 'str'>
print(type(messages))        # <class 'list'>
print(type(messages[0]))     # <class 'dict'>
```

## 5. 为什么要列表装多个字典？

因为一次请求可以传**多条消息**（system + 历史 + 当前提问），
模型按列表顺序读整段"对话剧本"。单条消息只有"角色 + 内容"两个信息，
多条按序排列才能表达"谁在什么时候说了什么"。
