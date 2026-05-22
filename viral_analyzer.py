"""
AIニュース収集・バイラリティ分析モジュール
ビジネス層向けXアカウント @GAUCHE_cellist 用
"""
import re
import feedparser
from dataclasses import dataclass

RSS_SOURCES = [
    ("https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "ITmedia AI+"),
    (
        "https://news.google.com/rss/search?q=生成AI+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
        "Google News AI-Biz",
    ),
    (
        "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業活用&hl=ja&gl=JP&ceid=JP:ja",
        "Google News LLM",
    ),
    ("https://feeds.feedburner.com/ledge-ai", "Ledge.ai"),
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI"),
    ("https://www.technologyreview.com/feed/", "MIT Technology Review"),
    (
        "https://news.google.com/rss/search?q=AI+automation+business+2026&hl=en&gl=US&ceid=US:en",
        "Google News AI-EN",
    ),
]

# ビジネス層が反応するキーワード
BUSINESS_KEYWORDS = [
    "ROI", "効率化", "コスト", "売上", "競合", "自動化", "DX",
    "生産性", "業務改善", "収益", "経営", "戦略", "意思決定", "変革",
    "イノベーション", "スケール", "KPI", "リード",
]

# バイラルツイート構造パターン（プロンプト用ヒント）
VIRAL_PATTERNS = {
    "shock_stat": "【実績】{数字}%の企業が{AI}を導入した結果→{衝撃の事実}",
    "fomo_warning": "まだ{AI_topic}を使っていない企業は3年後に詰む",
    "expert_reveal": "AIコンサルが教えてくれない{topic}の真実",
    "number_list": "{topic}で差がつく{n}つのAI活用法",
    "prediction": "2027年、{topic}業界に起きる3つの変化（今動くか、消えるか）",
    "personal_result": "{AI_tool}を3ヶ月使った正直な感想→",
    "contrarian": "「{common_belief}」という思い込みが{業界}を危険にしている",
    "thread_hook": "{topic}について誤解していること🧵（{n}選）",
}


@dataclass
class TrendItem:
    title: str
    url: str
    source: str
    summary: str = ""
    virality_score: float = 1.0


def _score(title: str) -> float:
    score = 1.0

    if re.search(r"\d+", title):
        score += 0.35

    for w in ["衝撃", "革命", "変革", "注目", "急成長", "危機", "爆発", "禁断"]:
        if w in title:
            score += 0.2
            break

    for w in BUSINESS_KEYWORDS:
        if w.lower() in title.lower():
            score += 0.3
            break

    for w in ["ChatGPT", "Claude", "Gemini", "GPT", "生成AI", "LLM", "AGI", "OpenAI"]:
        if w in title:
            score += 0.2
            break

    if any(c in title for c in ["？", "?", "なぜ", "どう", "どのように"]):
        score += 0.25

    # 英語記事はターゲット（日本語層）との親和性がやや低い
    if not re.search(r"[ぁ-ん]|[ァ-ン]|[一-龥]", title):
        score -= 0.1

    return round(min(score, 3.0), 2)


def fetch_trends(max_items: int = 10) -> list[TrendItem]:
    """複数RSSから最新AIニュースを取得し、バイラリティスコア順に返す"""
    items: list[TrendItem] = []
    seen: set[str] = set()

    for feed_url, source_name in RSS_SOURCES:
        try:
            feed = feedparser.parse(feed_url, agent="Mozilla/5.0")
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:200]

                if not title or len(title) < 8:
                    continue
                key = re.sub(r"\s+", "", title.lower())[:50]
                if key in seen:
                    continue
                seen.add(key)

                items.append(
                    TrendItem(
                        title=title,
                        url=link,
                        source=source_name,
                        summary=summary,
                        virality_score=_score(title),
                    )
                )
        except Exception:
            continue

    items.sort(key=lambda x: x.virality_score, reverse=True)
    return items[:max_items]


def format_for_prompt(trends: list[TrendItem], max_items: int = 6) -> str:
    """Claudeプロンプト用にトレンドをフォーマット"""
    lines = []
    for i, t in enumerate(trends[:max_items], 1):
        lines.append(f"{i}. 【{t.source}】{t.title}")
        if t.url:
            lines.append(f"   URL: {t.url}")
        if t.summary:
            lines.append(f"   概要: {t.summary[:100]}")
    return "\n".join(lines)
