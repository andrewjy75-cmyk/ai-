# 练习 03：让模型"打字给你看"——流式输出 + FastAPI + 网页

> 前两题你看到的是"模型想 5 秒，一次性吐一坨"。
> 这题做 ChatGPT 那种**逐字蹦出来的打字机效果**——工业界叫流式（streaming）。
> 流式让用户第一感觉快 10 倍，是**所有**聊天产品的标配。

## 为什么需要流式？（先理解再动手）

大模型回答长文可能要 10 秒。非流式：用户盯着转圈 10 秒，然后"啪"整篇出现。
流式：模型每生成一个字就推送一个字，用户 1 秒内就看到开头，像在打字。

技术本质：HTTP 一次普通请求只能响应一次；流式用 **SSE（Server-Sent Events）**——
服务端保持连接，**多次推送**数据块。底层就是"连接不关，分批写"。

## 三级台阶

### 台阶 A：终端版流式（纯 Python，不碰 Web）

文件 `step_a_stream_terminal.py`
让模型回答在你的终端里**一个字一个字蹦出来**（而非一次打印）。
练：`stream=True` 参数 + 遍历 `chunks`。

预期效果：
```
你：用三句话介绍杭州
杭
州
是
浙
江
省
的
省
会
...
（逐字蹦完一整段）
```

### 台阶 B：FastAPI 把流式包成 HTTP 接口

文件 `step_b_stream_api.py`
用 FastAPI 起一个服务：POST 一个 `{"question": "..."}`，
接口用 SSE 流式返回模型的回答（不是等全部生成完再返回一次）。
练：FastAPI + StreamingResponse + SSE 格式 `data: 内容\n\n`。

验证方法：浏览器/curl 直接访问，能看到逐字到达。

### 台阶 C：网页打字机

文件 `step_c_web_chat.py` + 同目录 `index.html`
最小网页：一个输入框 + 一个回答区，提交后用 JS 的
`fetch` + `ReadableStream` 读取 SSE 流，逐字上屏。
练：EventSource / fetch stream 读取、DOM 操作。

预期效果：在网页里问问题，回答像 ChatGPT 一样逐字打出。

## 验收标准（分台阶）

- [ ] A：回答确实逐字/逐块到达（不是等 5 秒一次出）
- [ ] B：`python step_b_stream_api.py` 起服务，curl 访问看到 `data: ` 前缀的多次推送
- [ ] C：浏览器输入问题，打字机效果流畅，能连续多轮提问

## 交作业

A、B、C 各自跑通都可以贴给我。最终贴：C 的网页效果截图/文字记录 + 你的代码。
我重点 review：chunks 的遍历方式、SSE 格式是否正确、JS 端流读取。

## 提示阶梯

<details>
<summary>台阶 A 提示：SDK 流式就是这么简单</summary>

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    stream=True,          # 关键！流式开关
)
for chunk in response:    # 每个 chunk 是一小片增量
    delta = chunk.choices[0].delta
    if delta.content:     # 有些 chunk 是空的（比如刚开头）
        print(delta.content, end="", flush=True)   # end="" 不换行；flush=True 强制立刻输出
```

`print(x, end="", flush=True)` 是终端打字机效果的核心：end="" 取消自动换行，
flush=True 让缓冲区立刻吐出而不是攒着。

</details>

<details>
<summary>台阶 B 提示：FastAPI + SSE 骨架</summary>

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

def llm_stream(question: str):
    """生成器：每次 yield 一小块给客户端"""
    # TODO：调 OpenAI stream=True，把每个 content 小块 yield 成 SSE 格式
    yield "data: 前缀示例\n\n"   # SSE 约定：data: 内容 + 空行

@app.post("/chat")
async def chat(req_body: dict):   # 简化：body 里 {"question": "..."}
    return StreamingResponse(llm_stream(req_body["question"]),
                             media_type="text/event-stream")
```

SSE 格式是协议：每块数据以 `data: ` 开头、以空行 `\n\n` 结尾。
装依赖：`pip install fastapi uvicorn`（没有就装：`.venv\Scripts\pip install fastapi uvicorn`）
运行：`python step_b_stream_api.py`（uvicorn.run(app, port=8000)）

</details>

<details>
<summary>台阶 C 提示：JS 读 SSE 流</summary>

用 EventSource 只支持 GET；POST + body 要用 fetch 手动读流：

```javascript
const resp = await fetch("/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({question: 输入框的值}),
});
const reader = resp.body.getReader();       // 拿到流
const decoder = new TextDecoder();
while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    // TODO：把 text 追加进回答区（注意要去掉 "data: " 和空行）
}
```

CORS 提示：若 index.html 用 file:// 打开会被浏览器拦，改用 `python -m http.server` 起个静态服务，或用 FastAPI 的 StaticFiles 托管 index.html。

</details>
