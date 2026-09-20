#!/usr/bin/env python3
"""Post-consume OCR rescue: re-OCR documents whose tesseract text is empty/too short
via a vision model on ollama, then PATCH the content back through the paperless API.

Runs inside the paperless container. Env: DOCUMENT_ID, PAPERLESS_ADMIN_TOKEN,
optional PAPERLESS_API_URL, OCR_RESCUE_MIN_CHARS, OCR_RESCUE_MAX_PAGES.
Never exits non-zero.

Self-check / manual use: ocr_rescue.py --ocr-file FILE [FILE ...]
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

API_URL = os.environ.get("PAPERLESS_API_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("PAPERLESS_ADMIN_TOKEN", "")
OLLAMA_URL = "http://ollama:11434"
MODEL = "glm-ocr:latest"
MIN_CHARS = int(os.environ.get("OCR_RESCUE_MIN_CHARS", "50"))
MAX_PAGES = int(os.environ.get("OCR_RESCUE_MAX_PAGES", "20"))


def log(msg):
    print(f"[ocr_rescue] {msg}", flush=True)


def api(method, path, data=None, raw=False):
    req = urllib.request.Request(
        f"{API_URL}{path}",
        method=method,
        data=data,
        headers={
            "Authorization": f"Token {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return body if raw else json.loads(body)


def ocr_image(png_bytes):
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(
            {
                "model": MODEL,
                "prompt": "Extract all the text from this image.",
                "images": [base64.b64encode(png_bytes).decode()],
                "stream": False,
                # stop at first markdown fence: without it glm-ocr loops "```"
                # until the token budget (observed 400s/page vs ~3s with stop)
                "options": {"stop": ["```"], "num_predict": 3000},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        text = json.load(r).get("response", "")
    return text.split("```")[0].strip()


def file_to_pages(path):
    """Return list of PNG byte blobs, one per page."""
    if Path(path).suffix.lower() == ".pdf":
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "150",
                    "-l",
                    str(MAX_PAGES),
                    str(path),
                    f"{td}/p",
                ],
                check=True,
                capture_output=True,
            )
            return [p.read_bytes() for p in sorted(Path(td).glob("p-*.png"))]
    with tempfile.TemporaryDirectory() as td:
        out = f"{td}/p.png"
        subprocess.run(["magick", str(path), out], check=True, capture_output=True)
        return [Path(out).read_bytes()]


def ocr_file(path):
    pages = file_to_pages(path)
    log(f"{path}: {len(pages)} page(s)")
    return "\n\n".join(filter(None, (ocr_image(p) for p in pages)))


def rescue(document_id):
    doc = api("GET", f"/api/documents/{document_id}/")
    content = (doc.get("content") or "").strip()
    if len(content) >= MIN_CHARS:
        log(f"doc {document_id}: content ok ({len(content)} chars), nothing to do")
        return
    original = api(
        "GET", f"/api/documents/{document_id}/download/?original=1", raw=True
    )
    ext = (
        ".pdf"
        if (doc.get("mime_type") or "").lower() == "application/pdf"
        else Path(doc.get("original_file_name") or "f.png").suffix
    )
    with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
        tmp.write(original)
        tmp.flush()
        text = ocr_file(tmp.name)
    if len(text) <= len(content):
        log(
            f"doc {document_id}: OCR found no more text ({len(text)} vs {len(content)}), keeping original"
        )
        return
    api(
        "PATCH",
        f"/api/documents/{document_id}/",
        json.dumps({"content": text}).encode(),
    )
    log(
        f"doc {document_id}: content replaced via OCR ({len(content)} -> {len(text)} chars)"
    )


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--ocr-file":
        for f in sys.argv[2:]:
            print(ocr_file(f))
        return
    document_id = os.environ.get("DOCUMENT_ID")
    if not document_id:
        log("DOCUMENT_ID not set, nothing to do")
        return
    if not TOKEN:
        log("PAPERLESS_ADMIN_TOKEN not set, cannot use API")
        return
    try:
        rescue(document_id)
    except Exception as e:
        # never fail the consume pipeline because of a rescue attempt
        log(f"doc {document_id}: failed: {e}")


if __name__ == "__main__":
    main()
