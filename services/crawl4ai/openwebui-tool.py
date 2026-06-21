"""
Title: Crawl4AI
Version: 1.0
Author: giografi
Description: Crawl and extract content from webpages using crawl4ai. The LLM should use this
  tool when the user asks to crawl, scrape, fetch, or extract content from any URL.
"""

from pydantic import BaseModel
from typing import Optional
import aiohttp


class Tools:
    class Valves(BaseModel):
        CRAWL4AI_BASE_URL: str = "http://crawl4ai-proxy:8000"

    def __init__(self):
        self.valves = self.Valves()

    async def crawl_webpage(
        self,
        url: str,
    ) -> str:
        """
        Crawl a webpage and return its extracted markdown content.
        Use this when the user provides a URL and asks you to read, crawl, scrape, or summarize it.

        Args:
            url: The full URL to crawl (e.g., https://example.com/article)

        Returns:
            Extracted page content in markdown format
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.valves.CRAWL4AI_BASE_URL}/crawl",
                json={"urls": [url]},
            ) as resp:
                result = await resp.json()
                if isinstance(result, dict):
                    return (
                        result.get("markdown") or result.get("content") or str(result)
                    )
                return str(result)
