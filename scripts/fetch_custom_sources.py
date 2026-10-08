#!/usr/bin/env python3
"""
抓取全部 26 个信源 RSS，生成 data/custom-sources.json
保留最近 72 小时内条目，最多 300 条
"""
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import feedparser, requests
from dateutil import parser as dateparser

SOURCES = [
    # ── 模型与研究（AIHOT 原有）
    {"id":"openai-news",       "name":"OpenAI News",          "category":"ai-models",   "feed_url":"https://openai.com/news/rss.xml"},
    {"id":"google-deepmind",   "name":"Google DeepMind",      "category":"ai-models",   "feed_url":"https://deepmind.google/blog/rss.xml"},
    {"id":"google-research",   "name":"Google Research",      "category":"ai-models",   "feed_url":"https://research.google/blog/rss/"},
    {"id":"huggingface",       "name":"HuggingFace Blog",     "category":"ai-models",   "feed_url":"https://huggingface.co/blog/feed.xml"},
    {"id":"microsoft-research","name":"Microsoft Research",   "category":"ai-models",   "feed_url":"https://www.microsoft.com/en-us/research/feed/"},
    {"id":"mistral",           "name":"Mistral AI",           "category":"ai-models",   "feed_url":"https://mistral.ai/news/rss"},
    {"id":"bair",              "name":"BAIR Blog",            "category":"ai-models",   "feed_url":"https://bair.berkeley.edu/blog/feed.xml"},
    {"id":"import-ai",         "name":"Import AI",            "category":"ai-models",   "feed_url":"https://importai.substack.com/feed"},
    {"id":"latent-space",      "name":"Latent Space",         "category":"ai-models",   "feed_url":"https://www.latent.space/feed"},
    # ── 产品与工具（AIHOT 原有）
    {"id":"aws-ml",            "name":"AWS Machine Learning", "category":"ai-products", "feed_url":"https://aws.amazon.com/blogs/machine-learning/feed/"},
    {"id":"github-ai",         "name":"GitHub AI & ML",       "category":"ai-products", "feed_url":"https://github.blog/ai-and-ml/feed/"},
    {"id":"nvidia-blog",       "name":"NVIDIA Blog",          "category":"ai-products", "feed_url":"https://blogs.nvidia.com/feed/"},
    # ── 行业观察（AIHOT 原有）
    {"id":"the-verge-ai",      "name":"The Verge AI",         "category":"industry",    "feed_url":"https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"id":"techcrunch-ai",     "name":"TechCrunch AI",        "category":"industry",    "feed_url":"https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"id":"ars-technica-ai",   "name":"Ars Technica AI",      "category":"industry",    "feed_url":"https://arstechnica.com/ai/feed/"},
    {"id":"mit-tech-review",   "name":"MIT Technology Review","category":"industry",    "feed_url":"https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    {"id":"the-decoder",       "name":"The Decoder",          "category":"industry",    "feed_url":"https://the-decoder.com/feed/"},
    {"id":"simon-willison",    "name":"Simon Willison",       "category":"industry",    "feed_url":"https://simonwillison.net/atom/everything/"},
    # ── 供应链与硬件（新增）
    {"id":"nvidia-newsroom",   "name":"NVIDIA Newsroom",      "category":"supply-chain","feed_url":"https://nvidianews.nvidia.com/news/rss"},
    {"id":"amd-ir",            "name":"AMD Press Releases",   "category":"supply-chain","feed_url":"https://ir.amd.com/news-events/press-releases/rss"},
    {"id":"semianalysis",      "name":"SemiAnalysis",         "category":"supply-chain","feed_url":"https://semianalysis.com/feed/"},
    {"id":"digitimes",         "name":"DigiTimes",            "category":"supply-chain","feed_url":"https://www.digitimes.com/rss/news.xml"},
    {"id":"thelec",            "name":"TheElec",              "category":"supply-chain","feed_url":"https://cdn.thelec.net/rss/gn_rss_allArticle.xml"},
    {"id":"venturebeat-ai",    "name":"VentureBeat AI",       "category":"industry",    "feed_url":"https://venturebeat.com/category/ai/feed/"},
]

MODULE_LABELS = {
    "ai-models":   "🤖 模型与研究",
    "ai-products": "🛠️ 产品与工具",
    "supply-chain":"⚙️ 供应链与硬件",
    "industry":    "📊 行业观察",
}

WINDOW_HOURS = 72
MAX_ITEMS    = 300
OUTPUT_PATH  = Path(__file__).parent.parent / "data" / "custom-sources.json"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0; +https://github.com/ShuVicky/AINews)"}

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
    items = []
    try:
        resp = requests.get(source["feed_url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue
            link    = getattr(entry, "link", "") or ""
            title   = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "") or ""
            if len(summary) > 600:
                summary = summary[:597] + "..."
            if not title or not link:
                continue
            items.append({
                "id":           f"{source['id']}-{abs(hash(link)) % 10**10}",
                "source_id":    source["id"],
                "source_name":  source["name"],
                "category":     source["category"],
                "module":       MODULE_LABELS.get(source["category"], source["category"]),
                "title":        title,
                "summary":      summary,
                "link":         link,
                "published_at": pub.isoformat() if pub else None,
            })
    except Exception as e:
        print(f"[WARN] {source['name']}: {e}", file=sys.stderr)
    return items

def main():
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=WINDOW_HOURS)
    all_items = []
    for source in SOURCES:
        items = fetch_feed(source, cutoff)
        print(f"[{'OK' if items else '--'}] {source['name']}: {len(items)} items")
        all_items.extend(items)

    seen, deduped = set(), []
    for item in all_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    deduped.sort(key=lambda x: x["published_at"] or "", reverse=True)
    deduped = deduped[:MAX_ITEMS]

    output = {
        "generated_at":  now.isoformat(),
        "window_hours":  WINDOW_HOURS,
        "source_count":  len(SOURCES),
        "count":         len(deduped),
        "items":         deduped,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✓ 写入 {OUTPUT_PATH}，共 {len(deduped)} 条，来自 {len(SOURCES)} 个信源")

if __name__ == "__main__":
    main()
