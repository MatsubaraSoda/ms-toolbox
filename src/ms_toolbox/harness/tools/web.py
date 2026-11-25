import json

import requests

from ms_toolbox.harness.config import get_harness_config


def search(provider: str, api_key: str, query: str) -> list[dict]:
    """返回格式契约: [{"title": str, "url": str, "snippet": str}, ...]"""
    if provider == "tavily":
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "max_results": 5},
        )
        data = response.json()
        return [
            {
                "title": item["title"],
                "url": item["url"],
                "snippet": item["content"],
            }
            for item in data["results"]
        ]


def fetch(provider: str, api_key: str, url: str) -> str:
    """返回格式契约: Markdown 格式的网页正文"""
    if provider == "tavily":
        response = requests.post(
            "https://api.tavily.com/extract",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"urls": [url], "format": "markdown"},
        )
        data = response.json()
        if data["results"]:
            return data["results"][0]["raw_content"]
        return f"错误：{data['failed_results'][0]['error']}"


def web_search(query: str) -> str:
    """在互联网上搜索信息，返回相关网页的标题、链接和摘要（JSON 数组格式）。

    Args:
        query (str): 搜索关键词。
    """
    cfg = get_harness_config()
    results = search(cfg["web_provider"], cfg["web_api_key"], query)
    return json.dumps(results, ensure_ascii=False)


def web_fetch(url: str) -> str:
    """读取指定 URL 网页的正文内容（Markdown 格式）。

    Args:
        url (str): 目标网页的完整链接（以 http:// 或 https:// 开头）。
    """
    cfg = get_harness_config()
    return fetch(cfg["web_provider"], cfg["web_api_key"], url)


def create_web_tools() -> list:
    return [web_search, web_fetch]
