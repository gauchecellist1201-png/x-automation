"""
Claude API を使った投稿文生成モジュール
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini&hl=ja&gl=JP&ceid=JP:ja",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリスト（1. / 2. / 3.）から投稿文を抽出し、140文字以内に絞る"""
    lines = [re.sub(r"^\d+[\.\)]\s*", "", l).strip() for l in raw.splitlines() if re.match(r"^\d+", l.strip())]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str) -> list[str]:
    """Note記事 + 過去に伸びた投稿 (few-shot) から投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        few_shot_section = f"""
## 過去に反応が良かった投稿例（文体・トーンを参考にしてください）
{feedback_text.strip()}
"""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist の中の人です。
以下のNote記事の内容を元に、Xへの投稿文を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内（日本語）
- 番号付きリスト（1. 2. 3.）で出力
- 押しつけがましくなく、読者に考えさせる一言を入れる
- ハッシュタグは1〜2個まで
{few_shot_section}
## Note記事
{note_text[:3000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 5) -> list[str]:
    """RSSフィードから最新ニュースタイトルを取得"""
    headlines: list[str] = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            if title:
                headlines.append(title)
    return headlines[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIニュースのタイトルを元に意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return []

    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = f"""あなたはXアカウント @GAUCHE_cellist の中の人です。
以下のAI関連ニュースのタイトルから1つを選び、そのニュースに対する短い意見・感想をX投稿として{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内（日本語）
- 番号付きリスト（1. 2. 3.）で出力
- 専門家の視点を交えつつ、一般読者にも分かりやすく
- ハッシュタグは1〜2個まで

## 最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
