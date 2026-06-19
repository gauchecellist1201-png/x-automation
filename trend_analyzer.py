"""
AIトレンド分析モジュール
RSS + Twitter検索 + Claude を組み合わせてバズパターンを抽出する。
"""

import os
import feedparser
import anthropic

# ビジネス層向けAIニュースRSSフィード
BUSINESS_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+DX+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+企業導入+コスト削減+生産性&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+最新+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+automation+workforce+Japan+業界&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]


def fetch_trending_news(max_items: int = 20) -> list[dict]:
    """トレンドのAIビジネスニュースをURL付きで取得する。"""
    items: list[dict] = []
    for url in BUSINESS_RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "url": link})
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def get_trend_context() -> dict:
    """
    トレンドニュースとバイラルパターン分析を返す。

    Returns:
        {
            "news": [{"title": str, "url": str}, ...],
            "top_news": {"title": str, "url": str} | None,
            "buzz_analysis": str,
        }
    """
    news = fetch_trending_news(max_items=15)

    # X検索（オプション。API制限があれば空リストになる）
    viral_tweets: list[dict] = []
    try:
        from x_poster import search_viral_ai_tweets
        viral_tweets = search_viral_ai_tweets(max_results=15)
    except Exception:
        pass

    # Claude でバズパターンを分析
    buzz_analysis = _analyze_buzz_patterns(news, viral_tweets)

    top_news = news[0] if news else None
    return {
        "news": news,
        "top_news": top_news,
        "buzz_analysis": buzz_analysis,
    }


def _analyze_buzz_patterns(news: list[dict], viral_tweets: list[dict]) -> str:
    """Claude にバズパターンとビジネス切り口を分析させる。"""
    news_text = "\n".join(f"- {n['title']}" for n in news[:10])

    viral_section = ""
    if viral_tweets:
        viral_section = "\n## 最近バイラルしたAIツイート（いいね順）\n"
        for t in viral_tweets[:8]:
            viral_section += f"- [{t['likes']}❤️ {t['retweets']}RT] {t['text'][:80]}\n"

    prompt = f"""以下のAIビジネスニュースとバイラルツイートを分析し、
今日ビジネス層（経営者・マネージャー・ITリーダー）に最も刺さるバズパターンを抽出してください。

## 今日のAIビジネスニュース
{news_text}
{viral_section}

出力形式（簡潔に）:
## 今日の推奨トピック
[最も注目すべきトピックを1〜2文で]

## 効果的な切り口
- 切り口A: [理由]
- 切り口B: [理由]
- 切り口C: [理由]

## バズる型（今日向け）
[型1: データ衝撃 / 型2: FOMO / 型3: 逆張り / 型4: 問いかけ / 型5: ランキング のどれが適切か]
"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
