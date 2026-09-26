"""Open WebUI external document loader: tika first, glm-ocr fallback for scanned
PDFs/images whose tika text is empty or too short.

Protocol (open_webui/retrieval/loaders/external_document.py):
PUT /process, raw bytes, Authorization: Bearer <token>, X-Filename header.
Response: {"page_content", "metadata"} or a list of those (one per OCR'd page).
"""

import base64
import logging
import os
from urllib.parse import unquote

import pymupdf
import requests
from fastapi import Body, FastAPI, Header, HTTPException

log = logging.getLogger("ocr-loader")

TOKEN = os.environ.get("OCR_LOADER_TOKEN", "")
MIN_CHARS = int(os.environ.get("OCR_LOADER_MIN_CHARS", "50"))
MAX_PAGES = int(os.environ.get("OCR_LOADER_MAX_PAGES", "30"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
MODEL = os.environ.get("OCR_LOADER_MODEL", "glm-ocr:latest")
TIKA_URL = os.environ.get("TIKA_URL", "http://tika:9998").rstrip("/")
DPI = 150
NUM_PREDICT = 3000
PAGE_TIMEOUT = 600
PROMPT = "Extract all the text from this image."

OCR_EXTS = {"pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"}

app = FastAPI()


def tika_text(data: bytes, mime: str) -> str:
    r = requests.put(
        f"{TIKA_URL}/tika/json/text",
        data=data,
        headers={"Content-Type": mime or "application/octet-stream"},
        timeout=300,
    )
    r.raise_for_status()
    return (r.json().get("tk:content") or "").strip()


def ocr_image(png: bytes) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": PROMPT,
            "images": [base64.b64encode(png).decode()],
            "stream": False,
            # stop at first markdown fence: without it glm-ocr loops "```"
            # until the token budget (observed 400s/page vs ~3s with stop)
            "options": {"stop": ["```"], "num_predict": NUM_PREDICT},
        },
        timeout=PAGE_TIMEOUT,
    )
    r.raise_for_status()
    return (r.json().get("response") or "").split("```")[0].strip()


def render_pages(data: bytes, ext: str) -> list[bytes]:
    doc = pymupdf.open(stream=data, filetype=ext)
    zoom = DPI / 72 if ext == "pdf" else 1
    pages = []
    for i, page in enumerate(doc):
        if i >= MAX_PAGES:
            break
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        pages.append(pix.tobytes("png"))
    doc.close()
    return pages


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.put("/process")
def process(
    body: bytes = Body(...),
    authorization: str = Header(""),
    x_filename: str = Header(""),
    content_type: str = Header(""),
):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "invalid token")

    filename = unquote(x_filename) or "document"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        text = tika_text(body, content_type)
    except Exception as e:
        log.warning("tika failed for %s: %s", filename, e)
        text = ""

    if ext in OCR_EXTS and len(text) < MIN_CHARS:
        page_texts = [ocr_image(p) for p in render_pages(body, ext)]
        if sum(len(t) for t in page_texts) > len(text):
            return [
                {
                    "page_content": t,
                    "metadata": {
                        "page": i,
                        "page_label": i + 1,
                        "total_pages": len(page_texts),
                        "file_name": filename,
                        "processing_engine": "glm-ocr",
                    },
                }
                for i, t in enumerate(page_texts)
                if t.strip()
            ]

    return {
        "page_content": text or "<No text content found>",
        "metadata": {"file_name": filename, "processing_engine": "tika"},
    }
