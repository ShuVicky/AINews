#!/usr/bin/env python3
"""
抓取自定义信源 RSS，生成 data/custom-sources.json
每次运行保留最近 72 小时内的条目，最多 200 条
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from dateutil import parser as dateparser

# ── 信源定义 ──────────────────────────────────────────────────────────────────
SOURCES = [
    # 芯片厂商
    {
        "id": "nvidia-blog",
        "name": "NVIDIA Blog",
        "category": "supply-chain",
        "feed_url": "https://blogs.nvidia.com/feed/",
    },
    {
        "id": "nvidia-newsroom",
        "name": "NVIDIA Newsroom",
        "category": "supply-chain",
        "feed_url": "https://nvidianews.nvidia.com/news/rss",
    },
    {
        "id": "amd-ir",
        "name": "AMD Press Releases",
        "category": "supply-chain",
        "feed_url": "https://ir.amd.com/news-events/press-releases/rss",
    },
    # 算力 / 行业分析
    {
        "id": "semianalysis",
        "name": "SemiAnalysis",
        "category": "supply-chain",
        "feed_url": "https://semianalysis.com/feed/",
    },
    # 供应链新闻
    {
        "id": "digitimes",
        "name": "DigiTimes",
        "category": "supply-chain",
        "feed_url": "https://www.digitimes.com/rss/news.xml",
    },
    {
        "id": "thelec",
        "name": "TheElec",
        "category": "supply-chain",
        "feed_url": "https://cdn.thelec.net/rss/gn_rss_allArticle.xml",
    },
    # 行业报告 / 媒体
    {
        "id": "mit-tech-review",
        "name": "MIT Technology Review",
        "category": "industry",
        "feed_url": "https://www.technologyreview.com/feed/",
    },
    {
        "id": "venturebeat-ai",
        "name": "VentureBeat AI",
        "category": "industry",
        "feed_url": "https://venturebeat.com/category/ai/feed/",
    },
]

WINDOW_HOURS = 72
MAX_ITEMS = 200
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "custom-sources.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0; +https://github.com/ShuVicky/AINews)"
}

def parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    for attr in ("published", "updated"):
        s = getattr(entry, attr, None)
        if s:
            try:
                dt = dateparser.parse(s)
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None


def fetch_feed(source, cutoff):
    url = source["feed_url"]
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue
            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "") or ""
            if len(summary) > 500:
                summary = summary[:497] + "..."
            if not title or not link:
                continue
            items.append({
                "id": f"{source['id']}-{abs(hash(link)) % 10**10}",
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": title,
                "summary": summary,
                "link": link,
                "published_at": pub.isoformat() if pub else None,
            })
    except Exception as e:
        print(f"[WARN] {source['name']}: {e}", file=sys.stderr)
    return items


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=WINDOW_HOURS)

    all_items = []
    for source in SOURCES:
        items = fetch_feed(source, cutoff)
        print(f"[OK] {source['name']}: {len(items)} items")
        all_items.extend(items)

    seen = set()
    deduped = []
    for item in all_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    deduped.sort(key=lambda x: x["published_at"] or "", reverse=True)
    deduped = deduped[:MAX_ITEMS]

    output = {
        "generated_at": now.isoformat(),
        "window_hours": WINDOW_HOURS,
        "count": len(deduped),
        "items": deduped,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✓ 写入 {OUTPUT_PATH}，共 {len(deduped)} 条")


if __name__ == "__main__":
    main()
