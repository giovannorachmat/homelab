"""
Title: Auto-Web Loader (crawl4ai)
Version: 1.0
Author: giografi
Description: Automatically detects URLs in user messages and fetches their content using
  crawl4ai, injecting the extracted content into the conversation context.
"""

from pydantic import BaseModel
from typing import Optional
import re
import aiohttp


class Filter:
    class Valves(BaseModel):
        CRAWL4AI_BASE_URL: str = "http://crawl4ai-proxy:8000"
        AUTO_CRAWL_URLS: bool = True
        MAX_URLS_PER_MESSAGE: int = 3

    def __init__(self):
        self.valves = self.Valves()

    def _extract_urls(self, text: str) -> list[str]:
        url_pattern = r"https?://[^\s<>\"']+|www\.[^\s<>\"']+"
        urls = re.findall(url_pattern, text)
        filtered = []
        for url in urls:
            if not re.search(
                r"\.(png|jpg|jpeg|gif|svg|webp|mp4|mp3|pdf|zip)$", url, re.I
            ):
                filtered.append(url)
        return filtered[: self.valves.MAX_URLS_PER_MESSAGE]

    async def _crawl_url(self, url: str) -> str | None:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.valves.CRAWL4AI_BASE_URL}/crawl",
                    json={"urls": [url]},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    result = await resp.json()
                    return (
                        result.get("markdown") or result.get("content") or str(result)
                    )
            except Exception:
                return None

    async def inlet(self, body: dict, user: dict | None = None) -> dict:
        if not self.valves.AUTO_CRAWL_URLS:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last = messages[-1]
        content = last.get("content", "")

        urls = self._extract_urls(content)
        if not urls:
            return body

        results = []
        for url in urls:
            crawled = await self._crawl_url(url)
            if crawled:
                results.append(f"## Content from {url}\n\n{crawled}")

        if results:
            existing = body.get("context", [])
            for r in results:
                existing.append({"role": "system", "content": r})
            body["context"] = existing

        return body
