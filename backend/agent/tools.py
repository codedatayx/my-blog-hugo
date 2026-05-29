"""
Agent 工具集 — 5 个 tool 的实现
"""

import io
import json
import re
import mimetypes
from pathlib import Path
from datetime import datetime

import aiohttp


# ========== Tool 1: 检测文件类型 ==========

async def detect_file_type(state: dict) -> dict:
    filename = state["filename"]
    ext = Path(filename).suffix.lower()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    state["mime_type"] = mime
    state["extension"] = ext
    return {"mime_type": mime, "extension": ext}


# ========== Tool 2: 提取文件内容 ==========

async def extract_content(state: dict) -> dict:
    ext = state["extension"]
    content = state["file_bytes"]

    text_exts = {".md", ".txt", ".py", ".java", ".json", ".yaml", ".yml",
                 ".toml", ".sh", ".js", ".ts", ".go", ".rs", ".c", ".cpp",
                 ".html", ".css", ".sql", ".xml", ".csv", ".log", ".cfg", ".ini"}

    if ext in text_exts:
        if ext == ".html":
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, "html.parser")
                state["text_content"] = soup.get_text(separator="\n")
            except ImportError:
                state["text_content"] = content.decode("utf-8", errors="replace")
        else:
            state["text_content"] = content.decode("utf-8", errors="replace")

    elif ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            state["text_content"] = "\n".join(
                p.extract_text() or "" for p in reader.pages
            )
        except ImportError:
            state["text_content"] = f"[PDF 文件: {state['filename']}，需要安装 PyPDF2]"

    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            state["text_content"] = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            state["text_content"] = f"[DOCX 文件: {state['filename']}，需要安装 python-docx]"

    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
        state["is_image"] = True
        state["text_content"] = f"[图片文件: {state['filename']}，将作为封面图]"

    else:
        # 尝试作为文本读取
        state["text_content"] = content.decode("utf-8", errors="replace")

    return {"length": len(state["text_content"]), "preview": state["text_content"][:200]}


# ========== Tool 3: LLM 分析内容 ==========

async def analyze_content(state: dict) -> dict:
    text = state["text_content"][:3000]

    prompt = f"""分析以下内容，为博客文章生成元数据。

内容:
{text}

请严格用 JSON 格式回复，不要包含其他文字:
{{"title": "文章标题", "summary": "一句话摘要", "tags": ["标签1", "标签2", "标签3"], "category": "分类"}}

分类只能从以下选项中选择: 技术笔记, 学习心得, 生活随笔, 项目记录, 其他
标签要简洁，2-4个，反映文章核心主题。"""

    from .core import call_llm
    result = await call_llm(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    # 提取 JSON
    result = result.strip()
    if "```" in result:
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]

    metadata = json.loads(result)
    state["metadata"] = metadata
    return metadata


# ========== Tool 4: 组装 Markdown ==========

async def format_markdown(state: dict) -> dict:
    meta = state["metadata"]
    content = state["text_content"]
    date = datetime.now().strftime("%Y-%m-%d")

    # 生成 slug
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", meta["title"]).strip("-").lower()
    filename = f"content/posts/{date.replace('-', '')}-{slug}.md"

    tags_str = ", ".join(f'"{t}"' for t in meta.get("tags", []))
    category = meta.get("category", "其他")

    md = f"""---
title: "{meta['title']}"
date: {date}
description: "{meta['summary']}"
author: "杨轩"
tags: [{tags_str}]
categories: ["{category}"]
showtoc: true
ShowReadingTime: true
ShowCodeCopyButtons: true
---

{content}"""

    state["md_content"] = md
    state["output_filename"] = filename
    return {"filename": filename, "preview": md[:500]}


# ========== Tool 5: 发布到 GitHub ==========

async def publish_to_github(state: dict) -> dict:
    import os
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return {"error": "未配置 GITHUB_TOKEN 环境变量"}

    repo = os.getenv("GITHUB_REPO", "codedatayx/my-blog-hugo")
    branch = os.getenv("GITHUB_BRANCH", "main")

    filename = state["output_filename"]
    content = state["md_content"]
    encoded = __import__("base64").b64encode(content.encode()).decode()

    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
    }

    body = {
        "message": f"feat: 新增文章「{state['metadata']['title']}」",
        "content": encoded,
        "branch": branch,
    }

    async with aiohttp.ClientSession() as session:
        # 检查文件是否已存在
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                existing = await resp.json()
                body["sha"] = existing["sha"]

        # 创建或更新文件
        async with session.put(url, headers=headers, json=body) as resp:
            if resp.status in (200, 201):
                return {
                    "status": "success",
                    "filename": filename,
                    "url": f"https://github.com/{repo}/blob/{branch}/{filename}",
                }
            else:
                error_text = await resp.text()
                return {"status": "error", "detail": error_text[:300]}


# ========== Tool 注册表 ==========

TOOLS = {
    "detect_file_type": detect_file_type,
    "extract_content": extract_content,
    "analyze_content": analyze_content,
    "format_markdown": format_markdown,
    "publish_to_github": publish_to_github,
}
