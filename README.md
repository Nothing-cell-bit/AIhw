# Mini ReAct Agent

一个从零实现的简化版 AI Agent 框架，不依赖 LangChain / LlamaIndex。它可以接收自然语言任务，让大模型按 ReAct 思路自主选择工具、调用工具、读取结果，并进行多轮思考后给出最终回答。

## 功能

- 支持 OpenAI 兼容接口，例如 ModelScope Inference API
- 支持多轮 `思考 -> 行动 -> 观察` 循环
- 使用 JSON 格式解析模型的工具调用指令
- 内置工具：
  - `calculator`：安全数学计算
  - `wikipedia_search`：维基百科搜索摘要
  - `file_write`：写入本地文件
  - `file_read`：读取本地文件
- 提供命令行版本和 Streamlit Web 界面
- 支持对话历史裁剪，避免上下文无限增长

## 项目结构

```text
.
├── agent.py
├── app.py
├── config.py
├── llm_client.py
├── main.py
├── memory.py
├── prompts.py
├── requirements.txt
├── tools.py
├── .env
├── .env.example
└── data/
```

## 安装

```bash
pip install -r requirements.txt
```

如果只运行命令行版本，可以跳过安装依赖，直接执行 `python main.py`。

## 配置

复制 `.env.example` 为 `.env`，然后填入你的 API 信息：

```env
MODELSCOPE_API_KEY=你的密钥
MODELSCOPE_BASE_URL=https://api-inference.modelscope.cn/v1/
MODELSCOPE_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

## 命令行运行

```bash
python main.py
```

示例问题：

```text
查一下爱因斯坦的出生年份和去世年份，然后计算他活了多少岁。
```

## Web 界面运行

零依赖版本：

```bash
python web_app.py
```

然后打开：

```text
http://localhost:8501
```

Streamlit 版本：

```bash
streamlit run app.py
```

## Demo 任务建议

```text
帮我计算 23 * 45 + 100。
```

```text
查一下爱因斯坦的出生年份和去世年份，然后计算他活了多少岁。
```

```text
查一下图灵的简介，保存到 notes.txt，然后读取 notes.txt 确认内容。
```

## 实现思路

Agent 每一轮都会把用户任务、对话历史和工具说明发给 LLM。LLM 必须返回 JSON：

```json
{
  "thought": "我需要查询信息",
  "action": "wikipedia_search",
  "action_input": {
    "query": "Albert Einstein"
  }
}
```

如果已经完成任务，则返回：

```json
{
  "thought": "已经得到完整答案",
  "final_answer": "爱因斯坦出生于 1879 年，去世于 1955 年，享年 76 岁。"
}
```

程序解析 JSON 后执行对应工具，并把工具结果作为 observation 再发给 LLM，直到得到 `final_answer` 或达到最大步数。
