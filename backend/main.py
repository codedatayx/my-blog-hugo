import os
import json
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from agent import run_agent

app = FastAPI(title="Blog API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chat service (Redis) — 可选，没有 Redis 时跳过
chat_service = None

@app.on_event("startup")
async def startup():
    global chat_service
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            from chat import ChatService
            chat_service = ChatService()
            await chat_service.connect()
        except Exception as e:
            print(f"[WARN] Redis 连接失败，聊天功能不可用: {e}")
            chat_service = None
    else:
        print("[INFO] 未配置 REDIS_URL，聊天功能已禁用，Agent 功能正常")


@app.on_event("shutdown")
async def shutdown():
    if chat_service:
        await chat_service.close()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    browser_history: list = []


class HistoryResponse(BaseModel):
    session_id: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not chat_service:
        return {"error": "聊天功能未启用（需要 Redis）", "reply": "后端未配置 Redis，聊天功能暂不可用。"}
    result = await chat_service.chat(
        session_id=req.session_id,
        user_message=req.message,
        browser_history=req.browser_history,
    )
    return result


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    if not chat_service:
        async def empty():
            yield f"data: {json.dumps({'content': '聊天功能未启用（需要 Redis）'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    async def generate():
        async for chunk in chat_service.chat_stream(
            session_id=req.session_id,
            user_message=req.message,
            browser_history=req.browser_history,
        ):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    if not chat_service:
        return {"error": "聊天功能未启用"}
    return chat_service.get_history(session_id)


@app.get("/api/profile/{session_id}")
async def get_profile(session_id: str):
    if not chat_service:
        return {"error": "聊天功能未启用"}
    return chat_service.get_profile(session_id)


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    if not chat_service:
        return {"status": "ok", "note": "Redis 未连接"}
    await chat_service.clear_session(session_id)
    return {"status": "ok"}


# ========== Blog Agent ==========

@app.post("/api/agent/upload")
async def agent_upload(file: UploadFile = File(...)):
    content = await file.read()

    async def event_stream():
        async for step in run_agent(content, file.filename):
            yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
