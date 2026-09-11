# 练习 05：RAG 实战——把物资系统文档做成"可问答的大脑"

> 阶段 6 核心目标：用你自己的《物资系统知识总结》文档，搭建一个 **RAG 问答库**。
> 问模型它从没训练过的问题（你们公司内部业务规则），它靠"先检索文档再回答"给出正确答案。
> 前置：已读 `lessons/lesson05a-rag-basics.md`（RAG 概念专讲），已装 chromadb。

## 数据源

`exercises/ex05-rag/material-system-knowledge.md`（148KB，真实系统知识总结）——
**这文档是你自己的系统总结，模型训练时绝没见过**，是验证 RAG 效果的最佳素材。

## 3 个台阶

### 台阶 A：离线建库（切分 + 向量化 + 存 Chroma）

文件：`step_a_build_index.py`
把知识文档切成块 → 每块用 bge-m3 转成向量 → 存进本地 Chroma 向量库。
**跑一次即可**，之后反复查询不重建。

验收：打印出文档长度、切块数量、向量库保存路径。

### 台阶 B：语义检索（只查不答）

文件：`step_b_search.py`（待布置）
输入一个问题 → 转成向量 → 从 Chroma 找出最相似的 3 个块 → 打印原文。
**感受**：关键词完全不含也能找到（"审批过了会不会自动出库"能命中"审批≠出库"章节）。

验收：对 3 个测试问题，检索出的片段确实相关。

### 台阶 C：检索增强问答（完整 RAG）

文件：`step_c_rag_answer.py`（待布置）
台阶 B 的检索结果 + 问题 拼进 prompt → 模型基于片段回答。
**灵魂体验**：问"报废审批通过后会自动生成出库单吗？"，模型必须检索到第 0 章才能答对。

验收：3 个测试问题答案正确且基于文档；故意问文档里没有的，模型承认不知道（不瞎编）。

## 提示阶梯

<details>
<summary>台阶 A 提示 1：OpenAIEmbeddings 适配 OpenAI 兼容网关</summary>

langchain-openai 的 `OpenAIEmbeddings` 走 OpenAI 兼容的 `/embeddings` 接口。
你们平台的 bge-m3 是 OpenAI 兼容网关下的 embedding 模型，参数照 ChatOpenAI 写：

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
)
```

**注意**：embedding 和对话是两类不同模型（专讲第 7 节），别用 glm-5.3-flash 当 embedding。
</details>

<details>
<summary>台阶 A 提示 2：切分器</summary>

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
chunks = splitter.split_text(doc_text)
```
</details>

<details>
<summary>台阶 A 提示 3：存 Chroma</summary>

```python
from langchain_chroma import Chroma

db = Chroma.from_texts(
    texts=chunks,
    embedding=embeddings,
    persist_directory=str(CHROMA_DIR),
)
```
</details>

<details>
<summary>踩坑预警：langchain 1.x 与 chromadb 兼容</summary>

如果你遇到 `langchain-chroma` 导入报错（版本冲突），在 llm-course 目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -q "langchain-chroma>=0.2" -i https://mirrors.aliyun.com/pypi/simple/
```

或改在系统 Python313 下运行脚本（本机 chromadb 1.5.9 已装到系统解释器）。
</details>

## 交作业

A 跑通贴输出。随后 B/C 我会逐题布置。
跑台阶 A 前，先把 RAG 专讲末尾的 5 道自测在脑子里过一遍。
