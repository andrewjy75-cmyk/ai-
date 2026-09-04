# 大模型应用开发实战课程（个人版）

> 学员背景：Java/Spring Cloud + Vue3 全栈，Python 零基础起步。
> 方式：随学随问，每课一个小目标 + 动手产出。
> 原则（学员定调）：**不学算法/原理/数学，只学应用层实战技术和框架**。
> 把大模型当作"一个会写文字的远程服务"来用——就像当年学 Redis、MQ 一样，会用、会集成、会落地。

## 路线图（纯应用层，零算法）

| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| 0 | Python 最小必要基础 + 环境 | 课程工程搭好（venv + openai 3.6.0 已装好） | ✅ |
| 1 | 第一个 LLM 调用（公司 New API 平台） | `hello_llm.py` 跑通（glm-5.3-flash） | ✅ |
| 2 | Prompt 实战技巧 + 结构化输出（让模型返回 JSON） | 信息提取小工具 | ✅ |
| 3 | Function Calling：让模型调你的函数 | 库存查询助手 | ✅ |
| 4 | 流式输出 + FastAPI 包成接口 + 简单网页 | 网页聊天 demo | ⏳ 练习 03 |
| 5 | LangChain 框架上手：链、提示模板、记忆 | 用框架重写前面的功能 | ⬜ |
| 6 | RAG 实战：文档切分 + 向量库（Chroma）+ 问答 | 物资系统文档问答库 | ⬜ |
| 7 | Agent 实战：给模型配工具，让它自己多步干活 | 物资智能查询助手 | ⬜ |
| 8 | 工程化收尾：配置管理、日志、成本控制、部署 | 可部署的完整应用 | ⬜ |

> 路线里没有任何"训练模型、微调、神经网络原理"——那些是算法工程师的事。
> 我们全程只做一件事：**把现成大模型的能力接进自己的系统**。

## 课程目录

- `lessons/lesson00-python-crash.md` — 给 Java 程序员的 Python 速成（30 分钟）
- `lessons/lesson00b-fstring.md` — f-string 字符串格式化专讲
- `lessons/lesson01b-messages-roles.md` — messages 三角色（system/user/assistant）专讲
- `lessons/lesson01-first-call/` — 第 1 课：第一次调用大模型 ✅
- `exercises/ex01-structured-output/` — 练习 01：结构化信息提取器 ✅
- `exercises/ex02-function-calling/` — 练习 02：Function Calling 库存查询助手 ✅
- `exercises/ex03-streaming-web/` — 练习 03：流式输出 + FastAPI 网页聊天（A 通关，B 进行中）
- `solutions/` — 参考答案目录（写完跑通再看！）

## 学习模式（学员定调，重要）

**我出题 + 给骨架和提示阶梯，你自己写代码，我点评。**
不再直接给成品代码照跑——"看懂"和"会写"之间，差的就是自己掉坑的那几跤。

每道题的固定结构：
1. `exercises/` 题面 + 验收标准 + 渐进提示（卡住再看，最多看一层）
2. 骨架代码带 TODO 桩，你只填 TODO
3. `solutions/` 参考答案 —— 写完跑通或卡死 30 分钟才准看
4. 交作业 = 贴完整运行输出 + 代码，我逐条验收 + review 风格

## 怎么用

1. 每题先读题面和验收标准，自己动手写
2. 卡住先查提示阶梯，还卡就带着具体报错来问
3. 过关后我更新本表，解锁下一题
