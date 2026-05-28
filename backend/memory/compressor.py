import gzip
import json
import aiohttp
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, SUMMARY_MAX_TOKENS


def compress_conversation(messages: list) -> bytes:
    """Gzip compress conversation JSON."""
    return gzip.compress(json.dumps(messages, ensure_ascii=False).encode("utf-8"))


def decompress_conversation(data: bytes) -> list:
    """Decompress gzipped conversation JSON."""
    return json.loads(gzip.decompress(data))


async def generate_summary(messages: list) -> dict:
    """Use DeepSeek to generate a summary of the conversation."""
    if not messages or not DEEPSEEK_API_KEY:
        return {"summary": "", "topics": ""}

    # Format conversation for summarization
    conv_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '杨轩'}: {m['content']}"
        for m in messages
    )

    prompt = f"""请用中文简短总结以下对话的要点（不超过100字），并提取3-5个关键话题（用逗号分隔）。

格式要求：
摘要: <一句话总结>
话题: <话题1, 话题2, ...>

对话内容:
{conv_text}"""

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": SUMMARY_MAX_TOKENS,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
            data = await resp.json()
            content = data["choices"][0]["message"]["content"]

            # Parse summary and topics
            summary = ""
            topics = ""
            for line in content.split("\n"):
                if line.startswith("摘要:"):
                    summary = line.replace("摘要:", "").strip()
                elif line.startswith("话题:"):
                    topics = line.replace("话题:", "").strip()

            return {"summary": summary or content[:100], "topics": topics}
    except Exception as e:
        return {"summary": f"摘要生成失败: {e}", "topics": ""}


async def extract_facts(messages: list) -> list:
    """Extract key facts from conversation (user preferences, interests, etc.)."""
    if not messages or not DEEPSEEK_API_KEY:
        return []

    conv_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '杨轩'}: {m['content']}"
        for m in messages[-6:]  # Only look at recent messages
    )

    prompt = f"""从以下对话中提取关于用户的3-5条关键事实（如兴趣、工作、技术栈、偏好等）。
每条事实一行，简洁明了。如果没有值得记录的事实，返回空。

对话:
{conv_text}"""

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
            data = await resp.json()
            content = data["choices"][0]["message"]["content"]
            facts = [f.strip() for f in content.strip().split("\n") if f.strip() and not f.startswith("没有")]
            return facts[:5]
    except Exception:
        return []
