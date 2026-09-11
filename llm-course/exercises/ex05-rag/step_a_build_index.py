r"""
练习 05 · 台阶 A：离线建库（切分 + 向量化 + 存 Chroma）
===========================================================

目标：把《物资系统知识总结》文档变成"可检索的向量库"。
这是 RAG 的"①准备"阶段——跑一次即可，之后反复查询。

数据源：exercises/ex05-rag/material-system-knowledge.md（系统知识总结）

运行（在 llm-course 目录下）：
    python exercises/ex05-rag/step_a_build_index.py

产出：exercises/ex05-rag/chroma_db/ 目录（向量库，持久化在磁盘）
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# 数据源文档路径
KNOWLEDGE_FILE = Path(__file__).parent / "material-system-knowledge.md"
# 向量库存放目录
CHROMA_DIR = Path(__file__).parent / "chroma_db"

# TODO-A1【核心】从 .env 读取 embedding 配置，创建向量化模型
#   你们平台有 BAAI/bge-m3！embedding 是"文字→向量"的模型，和对话模型不同
#   用 langchain_openai 的 OpenAIEmbeddings：
#     embeddings = OpenAIEmbeddings(
#         model="BAAI/bge-m3",
#         base_url=os.getenv("NEWAPI_BASE_URL"),
#         api_key=os.getenv("NEWAPI_API_KEY"),
#     )
#   OpenAIEmbeddings 内部兼容 OpenAI 的 embeddings API
embeddings = OpenAIEmbeddings(
        model="BAAI/bge-m3",
        base_url=os.getenv("NEWAPI_BASE_URL"),
        api_key=os.getenv("NEWAPI_API_KEY"),
    )   # ← 你来改

# TODO-A2【简单】读取知识文档全文
#   用 Path.read_text(encoding="utf-8") 读 KNOWLEDGE_FILE
doc_text = KNOWLEDGE_FILE.read_text(encoding="utf-8")     # ← 你来改

# TODO-A3【核心】切分文档成块（chunking）
#   LangChain 的 RecursiveCharacterTextSplitter：
#     from langchain_text_splitters import RecursiveCharacterTextSplitter
#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=500,        # 每块最多约500字符
#         chunk_overlap=50,      # 块间重叠50字符，防止语义被切断
#     )
#     chunks = splitter.split_text(doc_text)
#   思考：为什么文档要切成小块而不是整篇存？（RAG专讲第4节）
splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,        # 每块最多约500字符
        chunk_overlap=50,      # 块间重叠50字符，防止语义被切断
    )     # ← 你来改
chunks = splitter.split_text(doc_text)       # ← 你来改



# ---------- 验证（已给你） ----------
if __name__ == "__main__":
    # TODO-A4【核心】把块存进 Chroma 向量库
    #   from langchain_chroma import Chroma
    #   db = Chroma.from_texts(
    #       texts=chunks,          # 切好的文本块
    #       embedding=embeddings,  # 向量化模型
    #       persist_directory=str(CHROMA_DIR),  # 存哪
    #   )
    #   这一步内部做了：每块 → embedding → 存进向量库
    db = Chroma.from_texts(
        texts=chunks,  # 切好的文本块
        embedding=embeddings,  # 向量化模型
        persist_directory=str(CHROMA_DIR),  # 存哪
    )  # ← 你来改

    print(f"文档总长度：{len(doc_text)} 字符")
    print(f"切分得到：{len(chunks)} 个块")
    print(f"向量库已保存到：{CHROMA_DIR}")
    print("台阶 A 完成！下一步用台阶 B 查询它。")
