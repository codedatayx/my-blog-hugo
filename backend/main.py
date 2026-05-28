import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from chat import ChatService

app = FastAPI(title="Blog Chat API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_service = ChatService()


@app.on_event("startup")
async def startup():
    await chat_service.connect()


@app.on_event("shutdown")
async def shutdown():
    await chat_service.close()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    browser_history: list = []


class HistoryResponse(BaseModel):
    session_id: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    result = await chat_service.chat(
        session_id=req.session_id,
        user_message=req.message,
        browser_history=req.browser_history,
    )
    return result


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
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
    return chat_service.get_history(session_id)


@app.get("/api/profile/{session_id}")
async def get_profile(session_id: str):
    return chat_service.get_profile(session_id)


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    await chat_service.clear_session(session_id)
    return {"status": "ok"}
