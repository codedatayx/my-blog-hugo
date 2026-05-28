import aiohttp
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, CHAT_MAX_TOKENS, SOUL_PATH
from memory.redis_memory import RedisMemory
from memory.sqlite_memory import SQLiteMemory
from memory.compressor import (
    compress_conversation,
    generate_summary,
    extract_facts,
)

# Load soul.md at startup
_soul_content = ""
try:
    with open(SOUL_PATH, "r", encoding="utf-8") as f:
        _soul_content = f.read()
except FileNotFoundError:
    _soul_content = "你是杨轩的博客AI助手。"


class ChatService:
    def __init__(self):
        self.redis = RedisMemory()
        self.sqlite = SQLiteMemory()

    async def connect(self):
        await self.redis.connect()

    async def close(self):
        await self.redis.close()

    async def chat(
        self,
        session_id: str,
        user_message: str,
        browser_history: list = None,
    ) -> dict:
        """
        Main chat flow with three-layer memory.
        Returns: {"reply": str, "session_id": str}
        """
        # 1. Short-term memory from Redis
        short_memory = await self.redis.get_context(session_id)

        # 2. Long-term memory from SQLite
        profile = self.sqlite.get_profile(session_id)
        facts = self.sqlite.get_all_facts(limit=20)
        summaries = self.sqlite.get_recent_summaries(session_id, limit=3)

        # 3. Build system prompt
        system_prompt = self._build_system_prompt(profile, facts, summaries)

        # 4. Assemble message list
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(short_memory)
        if browser_history:
            messages.extend(browser_history[-6:])
        messages.append({"role": "user", "content": user_message})

        # 5. Call DeepSeek
        reply = await self._call_deepseek(messages)

        # 6. Save to Redis
        await self.redis.save_turn(session_id, "user", user_message)
        await self.redis.save_turn(session_id, "assistant", reply)

        # 7. Update profile
        self.sqlite.save_profile(session_id)

        # 8. Periodic compression
        turn_count = await self.redis.get_turn_count(session_id)
        if turn_count > 0 and turn_count % 10 == 0:
            await self._compress_and_save(session_id, short_memory)

        return {"reply": reply, "session_id": session_id}

    async def chat_stream(self, session_id: str, user_message: str, browser_history: list = None):
        """
        Streaming chat flow. Yields chunks of the reply.
        """
        short_memory = await self.redis.get_context(session_id)
        profile = self.sqlite.get_profile(session_id)
        facts = self.sqlite.get_all_facts(limit=20)
        summaries = self.sqlite.get_recent_summaries(session_id, limit=3)

        system_prompt = self._build_system_prompt(profile, facts, summaries)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(short_memory)
        if browser_history:
            messages.extend(browser_history[-6:])
        messages.append({"role": "user", "content": user_message})

        # Stream from DeepSeek
        full_reply = ""
        async for chunk in self._call_deepseek_stream(messages):
            full_reply += chunk
            yield chunk

        # Save after streaming completes
        await self.redis.save_turn(session_id, "user", user_message)
        await self.redis.save_turn(session_id, "assistant", full_reply)
        self.sqlite.save_profile(session_id)

        turn_count = await self.redis.get_turn_count(session_id)
        if turn_count > 0 and turn_count % 10 == 0:
            await self._compress_and_save(session_id, short_memory)

    def _build_system_prompt(self, profile: dict, facts: list, summaries: list) -> str:
        parts = [_soul_content]

        if profile:
            parts.append(f"\n## 关于这个用户\n兴趣: {profile.get('interests', '未知')}\n聊过的话题: {profile.get('topics', '未知')}")

        if facts:
            facts_text = "\n".join(f"- {f}" for f in facts)
            parts.append(f"\n## 已知事实\n{facts_text}")

        if summaries:
            sums = "\n".join(
                f"- [{s['date'][:10]}] {s['summary']}" for s in summaries
            )
            parts.append(f"\n## 历史对话摘要\n{sums}")

        return "\n".join(parts)

    async def _call_deepseek(self, messages: list) -> str:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": CHAT_MAX_TOKENS,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            )
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_deepseek_stream(self, messages: list):
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": CHAT_MAX_TOKENS,
                    "stream": True,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            )
            async for line in resp.content:
                decoded = line.decode("utf-8").strip()
                if not decoded or not decoded.startswith("data:"):
                    continue
                payload = decoded[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    import json
                    obj = json.loads(payload)
                    delta = obj["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue

    async def _compress_and_save(self, session_id: str, messages: list):
        """Compress old conversation and save to SQLite."""
        if not messages:
            return
        compressed = compress_conversation(messages)
        result = await generate_summary(messages)
        facts = await extract_facts(messages)

        self.sqlite.save_summary(
            session_id=session_id,
            summary=result["summary"],
            topics=result["topics"],
            compressed_data=compressed,
            turn_count=len(messages),
        )

        for fact in facts:
            self.sqlite.save_fact(fact, session_id)

    async def clear_session(self, session_id: str):
        await self.redis.clear_session(session_id)

    def get_profile(self, session_id: str) -> dict:
        return self.sqlite.get_profile(session_id)

    def get_history(self, session_id: str) -> dict:
        return {
            "summaries": self.sqlite.get_recent_summaries(session_id),
            "facts": self.sqlite.get_facts(session_id),
        }
