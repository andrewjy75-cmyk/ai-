r"""
练习 05 · 台阶 B：语义检索——只查不答
=========================================

目标：输入一个问题 → 转成向量 → 从台阶 A 建的向量库里找出最相似的 3 块 → 打印原文。

重点体验（对比台阶 A）：
- 台阶 A 是"建库"（写），台阶 B 是"查库"（读）——**加载即可，不重建！**
  这就是 RAG 专讲里"建索引一次、查询无数次"的意义。
- 检索是"语义"的：问题里没有的字，只要意思相关也能命中。
  （问"审批过了会不会自动出库"，能命中文档里"审批 ≠ 出库"那一章）

运行（在 llm-course 目录下）：
    python exercises/ex05-rag/step_b_search.py

验收：三个测试问题，每个都检索出明显相关的原文片段。
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

# 向量库路径（和台阶 A 一致！）
CHROMA_DIR = Path(__file__).parent / "chroma_db"

# TODO-B1【简单】创建 embeddings（和台阶 A 一模一样的配置）
#   ⚠️ 关键认知：查询时用的 embedding 模型必须和建库时是同一个！
#   否则等于"用米尺量、用英尺比"——向量不在同一坐标系，相似度全乱
embeddings = OpenAIEmbeddings(
    base_url=os.getenv("NEWAPI_BASE_URL"),
    api_key=os.getenv("NEWAPI_API_KEY"),
    model="BAAI/bge-m3"
)   # ← 你来改

# TODO-B2【核心】加载已有的向量库（不是重建！）
#   Chroma(persist_directory=str(CHROMA_DIR), embedding=embeddings)
#   对比台阶 A 的 Chroma.from_texts(...)：
#     from_texts = 创建新库（写）
#     Chroma(...) = 打开已有库（读）
db = Chroma(persist_directory=str(CHROMA_DIR))           # ← 你来改

# 三个测试问题（先自己想：各自应该命中文档哪一章？）
TEST_QUESTIONS = [
    "报废审批通过后，会自动生成出库单吗？",
    "出库单的单号是什么格式？",
    "盘点发现数量对不上怎么处理？",
]

def search(question: str, k: int = 3):
    """在向量库里找与问题最相似的 k 个片段并打印"""
    # TODO-B3【核心】相似度搜索
    #   results = db.similarity_search_with_score(question, k=k)
    #   返回：[(Document, 相似度分数), ...]
    #   Document 有 .page_content（原文片段）属性
    #   分数越小越相似（这是距离不是相似度，先不用纠结）
    results = db.similarity_search_with_score(question, k=k)   # ← 你来改

    print(f"\n{'='*50}\n问：{question}\n{'='*50}")
    for i, (doc, score) in enumerate(results, 1):
        # TODO-B4【简单】打印片段原文（doc.page_content）
        print(f"\n--- 片段 {i}（距离 {score:.2f}）---")
        print(doc.page_content[:200])   # 只打印前200字预览


if __name__ == "__main__":
    for q in TEST_QUESTIONS:
        search(q)
