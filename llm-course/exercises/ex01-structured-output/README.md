# 练习 01：结构化信息提取器（第 2 课作业）

> 目标：**不看参考答案**，自己写出"乱文本 → 规整 JSON"的完整流程。
> 这是 LLM 应用里出现频率最高的模式，写完这个你就入门了。

## 题面

写一个脚本 `extract_info.py`，实现：

1. 读取下面这段"领料记录"（格式故意很乱）
2. 调用 New API 平台的模型，提取所有领用条目
3. 把结果解析成 Python 列表，逐条打印 + 统计总件数

**待处理的原始文本**（放在代码里就行）：

```
今天上午老张来领了6个轴承型号6204，说是给2号生产线用的，仓管员小王发的货。
下午三点左右，维修班刘工拿走了2桶液压油L-HM46，登记是维修用。
还有一笔:紧固件M12螺栓一批,大概200个左右,第3车间领的,经手人赵敏。
```

**每个条目要求提取 6 个字段**：
`material_name`（物资名）、`spec`（规格型号，没有填"未知"）、`quantity`（数量，"一批/大概200个"要推断成数字 200）、`unit`（单位）、`department`（部门/用途，没有填"未知"）、`person`（经手人，没有填"未知"）

## 验收标准（全部满足才算过）

- [ ] 运行不报错，`Process finished with exit code 0`
- [ ] 模型返回的原始文本会先打印出来（方便你观察它到底说了啥）
- [ ] `json.loads` 解析成功，打印出 3 条记录
- [ ] 每条记录 6 个字段齐全，最后打印合计件数
- [ ] `temperature` 设为 0（想想为什么）
- [ ] 密钥从 `.env` 读，代码里不出现任何 `sk-` 开头的字符串

## 提示阶梯（卡住了再看，最多看到哪层你自己定）

<details>
<summary>提示 1：整个程序的骨架长什么样（5 步）</summary>

1. `load_dotenv()` 读配置，用配置创建 `OpenAI` 客户端
2. 定义原始文本 RAW_TEXT 和系统提示词 SYSTEM_PROMPT（把验收标准里的字段要求写进去）
3. 组 `messages` 列表：system + user（user 里放原始文本，用分隔符包住）
4. 调 `client.chat.completions.create(...)`，拿到 `response.choices[0].message.content`
5. 防御性清洗（剥掉可能的 \`\`\`json 包裹）→ `json.loads` → for 循环打印

</details>

<details>
<summary>提示 2：几个 Python 语法点（都是第 0 课讲过的）</summary>

- 多行长文本用三引号字符串：`RAW_TEXT = """..."""`
- f-string 拼消息：`f"###\n{raw_text}\n###"`
- 字符串方法：`.strip()` 去首尾空白、`.startswith("```")` 判断开头
- 解析失败的兜底：`try: ... except json.JSONDecodeError as e:`
- 打印循环：`for i, item in enumerate(result, 1):`（enumerate 从 1 计数）

</details>

<details>
<summary>提示 3：防御性清洗的思路（不给你完整代码）</summary>

模型有时不理睬"只返回 JSON"，会包一层 \`\`\`json ... \`\`\`。你的处理逻辑：

```text
拿到 text 后：
  如果 text 以 ``` 开头 → 去掉开头的 ``` 和可能的 "json" 字样 → 去掉结尾的 ```
  最后再 strip() 一次
```

用 `strip("`")` 可以把两端的反引号都去掉，剩下的再判断开头是不是 `json` 四个字符。

</details>

## 交作业方式

跑通后把**完整输出**（含模型原始返回）贴到对话里，我会：
1. 对照验收标准逐条检查
2. Review 你的代码风格（命名、注释、结构）
3. 有更优雅的写法我会指出——但前提是你先自己写出来

## 参考答案

`solutions/ex01-structured-output/extract_reference.py`
**先自己写！写完跑通再看，或者卡死 30 分钟以上再看。** 看的时候重点对比：
你的 messages 是怎么组的？你的清洗逻辑和答案差在哪？为什么？
