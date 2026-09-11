# ex00：第 1 课——第一次调用大模型

> 这是课程的"Hello World"：用公司 New API 平台（OpenAI 兼容网关）完成第一次 LLM 调用。
> 已通关 ✅，保留作为"最小可运行样例"——以后任何环境配置问题都可以拿它验证通道通不通。

## 文件

- `hello_llm.py` — 完整示例代码（不是 TODO 练习，是演示）

## 运行（在 llm-course 目录下）

```powershell
python exercises/ex00-hello-llm/hello_llm.py
```

## 它教会你什么

1. OpenAI 兼容 API 是行业通用标准（New API / DeepSeek / Ollama 接口都长一样）
2. messages 三角色：system（人设）/ user（提问）/ assistant（模型回复）
3. 密钥从根目录 `.env` 读取，不写死在代码里
4. 模型通道统一走 `NEWAPI_*` 环境变量，换模型只改 `.env`
