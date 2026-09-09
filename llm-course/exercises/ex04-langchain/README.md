# 练习 04：LangChain 框架——把你写过的功能"重写"一遍

> 阶段 5 的核心思路：**用框架重写你已经手工实现过的功能**。
> 目标不是学会新功能，而是看懂"框架替我省了什么"。
> 你已经有裸写底子，这题会感觉像"换了个更省力的工具"。

## 前置：为什么你已经能学框架了？

练习 01~03 你手工做过：
- 组 messages（system/user/assistant）
- 调 chat.completions.create
- 解析 content
- 流式 for chunk
- Function Calling 两回合

LangChain 把这些全部封装。**看懂封装的前提是你见过裸写**——你已经见过了。

## 本练习 3 个台阶（每步都是"重写"你做过的东西）

### 台阶 A：用 ChatOpenAI 重写"第一个调用"

文件：`step_a_chat.py`
把 hello_llm.py 用 LangChain 重写：ChatOpenAI + invoke。

预期：跑起来输出模型回答（和 hello_llm.py 一样）。

### 台阶 B：用 PromptTemplate + 链 重写"结构化提取"

文件：`step_b_extract.py`
把练习 01 的领料提取用 LangChain 重写：
- ChatPromptTemplate 代替手工拼 system/user
- 链：`prompt | llm | StrOutputParser()`
- 解析 JSON 部分不变（json.loads）

预期：四条记录全部提取正确，和你手写版输出一致。

### 台阶 C（可选挑战）：用链重写"流式聊天"

文件：`step_c_stream_chat.py`
把练习 03 台阶 A 的流式用 `llm.stream()` 重写。
感受：LangChain 里流式只要 `for chunk in llm.stream(messages)`。

## 安装依赖（已完成/或运行这条）

```powershell
.\.venv\Scripts\python.exe -m pip install langchain langchain-openai
```

## 验收标准

- [ ] A：输出模型回答，无报错
- [ ] B：输出 3~4 条提取记录，字段齐全
- [ ] C：文字逐字/逐块蹦出（打字机效果）

## 提示阶梯

<details>
<summary>台阶 A 提示：ChatOpenAI 基本用法</summary>

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
    model=os.getenv("NEWAPI_MODEL"),
    temperature=0.7,
)

response = llm.invoke("用一句话解释什么是API")   # invoke = 调用一次
print(response.content)                          # .content 就是回答文本
```

注意：ChatOpenAI 的 `invoke` 直接接受字符串（简单提问）或消息列表（复杂场景）。
temperature 参数直接传。这是对 `client.chat.completions.create` 的封装。

</details>

<details>
<summary>台阶 B 提示：PromptTemplate + 链</summary>

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ① 提示模板：用 {变量} 占位，代替手工拼接
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是物资领用记录的结构化助手。{rules}"),
    ("user", "###\n{raw_text}\n###\n请提取领用条目。"),
])

# ② 组装一条链：输入 dict → prompt → llm → 字符串
chain = prompt | llm | StrOutputParser()

# ③ 调用链：传一个 dict，填满模板里的变量
text = chain.invoke({
    "rules": "只返回JSON数组，六个字段...",
    "raw_text": RAW_TEXT,
})
```

链的管道 `|`：左→右依次执行，前一个的输出自动成为后一个的输入。
`chain.invoke({"rules":..., "raw_text":...})` = 你手写版里的 messages 组装 + API 调用。

</details>

<details>
<summary>台阶 C 提示：LangChain 流式</summary>

```python
for chunk in llm.stream("用三句话介绍杭州"):
    print(chunk.content, end="", flush=True)
```

llm.stream() 返回一个可迭代对象，每次 yield 一块。对比你手写的 for chunk in response，
LangChain 把"处理 chunk 结构"也封装了——chunk.content 直接就是文字。

</details>

## 交作业

A/B 跑通贴输出 + 你的代码。重点思考（交作业时回答我）：
1. 台阶 B 里，`chain.invoke({...})` 代替了你手写版的哪几行？
2. 你觉得 LangChain 封装是好是坏？什么场景下你会想用手写而不是框架？
