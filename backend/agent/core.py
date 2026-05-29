"""
ReAct Agent — 文件上传 → 类型检测 → 内容提取 → LLM 分析 → 发布博客
"""

import json
import aiohttp

from .tools import TOOLS

REACT_SYSTEM_PROMPT = """你是一个博客发布助手。用户给你一个文件，你需要按步骤处理：

1. detect_file_type — 检测文件类型
2. extract_content — 提取文件内容
3. analyze_content — 分析内容，生成标题、摘要、标签、分类
4. format_markdown — 组装 Hugo Markdown
5. publish_to_github — 发布到 GitHub

可用工具:
- detect_file_type: 检测文件 MIME 类型和扩展名，无需输入参数
- extract_content: 提取文件文本内容，无需输入参数
- analyze_content: 分析内容生成元数据，无需输入参数
- format_markdown: 组装 Markdown 文件，无需输入参数
- publish_to_github: 发布到 GitHub，无需输入参数

每一步完成后，根据结果决定下一步。所有工具都不需要额外参数。

输出格式（严格遵守）:
Thought: <你的思考>
Action: <tool_name>

最终发布完成后:
Thought: <总结>
Final Answer: <发布结果，包含文件名和状态>"""


def build_prompt(history: list, filename: str) -> list[dict]:
    """构造 LLM 对话 messages"""
    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": f"请处理这个文件: {filename}"},
    ]

    for step in history:
        messages.append({
            "role": "assistant",
            "content": f"Thought: {step['thought']}\nAction: {step['action']}",
        })
        messages.append({
            "role": "user",
            "content": f"Observation: {json.dumps(step['result'], ensure_ascii=False)}",
        })

    return messages


def parse_response(text: str) -> dict:
    """解析 LLM 响应，提取 Thought / Action / Final Answer"""
    thought = ""
    action = None
    final = None

    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("Thought:"):
            thought = line[len("Thought:"):].strip()
        elif line.startswith("Action:"):
            action = line[len("Action:"):].strip()
        elif line.startswith("Final Answer:"):
            final = line[len("Final Answer:"):].strip()

    return {"thought": thought, "action": action, "final": final}


async def call_llm(messages: list, temperature: float = 0.4, max_tokens: int = 500) -> str:
    """调用 DeepSeek API"""
    import os
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def run_agent(file_bytes: bytes, filename: str):
    """
    ReAct Agent 主循环（异步生成器，逐步 yield 结果）。

    Args:
        file_bytes: 文件原始字节
        filename: 文件名

    Yields:
        dict: 每步的结果 {type, content/tool/result}
    """
    state = {
        "filename": filename,
        "file_bytes": file_bytes,
    }
    history = []

    for i in range(10):  # 最多 10 步防止死循环
        messages = build_prompt(history, filename)
        response = await call_llm(messages)

        parsed = parse_response(response)

        if parsed["thought"]:
            yield {"type": "thought", "content": parsed["thought"]}

        # 最终回复
        if parsed["final"]:
            yield {"type": "done", "content": parsed["final"]}
            return

        # 执行 tool
        action = parsed["action"]
        if action not in TOOLS:
            yield {"type": "error", "content": f"未知工具: {action}"}
            history.append({
                "thought": parsed["thought"],
                "action": action,
                "result": {"error": f"未知工具: {action}，可用工具: {list(TOOLS.keys())}"},
            })
            continue

        try:
            result = await TOOLS[action](state)
        except Exception as e:
            result = {"error": str(e)}

        yield {
            "type": "action",
            "tool": action,
            "result": result,
        }

        history.append({
            "thought": parsed["thought"],
            "action": action,
            "result": result,
        })

    # 超过最大步数
    yield {"type": "error", "content": "Agent 达到最大步数限制"}
