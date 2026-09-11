import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

llm = ChatOpenAI(
    base_url=os.getenv('NEWAPI_BASE_URL'),
    model=os.getenv('NEWAPI_MODEL'),
    api_key=os.getenv('NEWAPI_API_KEY'),
    temperature=0
)






if __name__ == "__main__":
    resp = llm.stream("给我一篇八百字作文，题目随机")
    for chunk in resp:
        piece=chunk.content
        if piece:
            print(piece, end="", flush=True)