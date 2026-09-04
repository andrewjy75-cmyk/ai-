r"""
第 1 课：第一次调用大模型
==========================

学习目标：
1. 理解"OpenAI 兼容 API"——全行业的通用接口标准，New API / DeepSeek / Ollama 都长一样
2. 理解 messages 列表：system（设定人设）/ user（用户说的话）/ assistant（模型的回复）
3. 跑通公司 New API 平台的第一次调用

运行方式（在 llm-course 目录下）：
    .venv\Scripts\Activate.ps1
    python lessons/lesson01-first-call/hello_llm.py
"""

import os
from dotenv import load_dotenv   # 从 .env 文件读配置，避免密钥写死在代码里
from openai import OpenAI        # 官方 SDK，DeepSeek/Ollama 都兼容它

# 加载同目录的 .env 文件（≈ Spring 的 application.yaml，但只存密钥类配置）
load_dotenv()

# ---------- 通道配置：统一走公司的 New API 平台 ----------
# New API 是一个"模型网关"：把各家大模型（DeepSeek/Qwen/GPT…）聚合成
# OpenAI 兼容接口。对代码来说它就是普通 API，只是 base_url 指向公司平台。
PROVIDERS = {
    "newapi": {
        "base_url": os.getenv("NEWAPI_BASE_URL"),  # 形如 https://公司平台地址/v1
        "api_key": os.getenv("NEWAPI_API_KEY"),    # 平台里生成的令牌，形如 sk-xxx
        "model": os.getenv("NEWAPI_MODEL"),        # 平台模型列表里选一个名字
    },
}

cfg = PROVIDERS["newapi"]

# 创建客户端 ≈ Java 里 new 一个 FeignClient / RestTemplate
client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])

# ---------- 核心：messages 就是一段对话记录 ----------
messages = [
    # system：给模型设定角色和行为准则，用户看不到但全程生效
    {"role": "system", "content": "你是一位耐心的编程老师，擅长用 Java 类比来讲解 Python，回答简洁。"},
    # user：用户的提问
    {"role": "user", "content": "请你告诉我，学习ai大模型应用开发应该从哪里入手"},
    """## 第1步：Python速成（有Java基础，1-2周足够）

不用系统学，掌握这些就能干活：列表 `[]`（≈ `List`）、字典 `{}`（≈ `Map`）、函数、pip 安装依赖（≈ Maven）。

## 第2步：直接调API（最快见效）

就像Java里用 `RestTemplate` 调第三方接口一样简单：

```python
from openai import OpenAI

client = OpenAI(api_key="sk-xxx")  # 国内可用DeepSeek/通义/智谱，格式兼容
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}]
)
print(resp.choices[0].message.content)
```

**这一步就能做出聊天机器人了。**

## 第3步：Prompt工程（零代码，但最影响效果）

学习：系统提示词、Few-shot示例、让模型输出JSON（类似定义接口返回DTO）。

## 第4步：LangChain框架（可选）

类比：**LangChain 之于 AI应用 ≈ Spring 之于 Java后端**，帮你整合模型调用、RAG、Agent等组件。学核心概念即可，不必深钻。

## 第5步：RAG（检索增强生成）— 应用开发核心场景

- **Embedding**：把文本变成向量，相当于生成“语义指纹”
- **向量数据库**：FAISS / Milvus（类比Elasticsearch，按语义相似度搜索而非关键词）
- 流程：文档切分 → 向量化入库 → 用户提问时先检索 → 把相关内容塞给大模型回答

## 第6步：Agent / Function Calling

把你写的函数（Java/Python都行）注册给大模型，模型自己决定何时调用——类似把Service方法暴露成RPC接口，只是“调用方”换成了模型。

---

## 三条建议

1. **从第2步直接动手**，边做边学，别陷入教程
2. **90%的应用开发不需要微调**，微调是最后才考虑的事
3. **实战项目优先**：文档问答机器人 → 智能客服 → 自动化Agent，做完这三个基本就入门了

--- 本次消耗：输入 45 + 输出 1429 = 1474 tokens ---"""
]

print(f">>> 正在调用 {cfg['model']} ...\n")

# 发起对话请求 ≈ POST 一个 JSON，拿回一个 JSON
response = client.chat.completions.create(
    model=cfg["model"],
    messages=messages,
    temperature=1,   # 0~2，越低越严谨稳定，越高越发散有创意
)

# 取回复内容：response.choices[0].message.content
answer = response.choices[0].message.content
print(answer)

# 顺带看看这次花了多少 token（token ≈ 计费单位，1 个汉字约 1~2 token）
print(f"\n--- 本次消耗：输入 {response.usage.prompt_tokens} + 输出 {response.usage.completion_tokens} = {response.usage.total_tokens} tokens ---")

# ========== 课后练习（必做）==========
# 1. 把 user 的问题换成你自己想问的，再跑一次
# 2. 把 temperature 改成 0 和 1.5 各跑一次，对比同一个问题的回答风格
# 3. 在 messages 里追加一条 {"role": "assistant", "content": answer} 和一条新的 user 提问，
#    观察模型能否记住上文 —— 这就是"多轮对话"的全部秘密：每次都把完整历史发过去
