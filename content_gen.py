"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import requests
import anthropic
from typing import TypedDict

from viral_analyzer import fetch_viral_patterns

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点（スイス研究、国連参加経験）
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるX投稿の鉄則
1. 冒頭1文で「え？」「本当に？」「考えたことなかった」を引き出す
2. 具体的数字・固有名詞を必ず1つ入れる（信頼性と検索性）
3. 専門的だが難解すぎない言葉選び（医療×AI×社会）
4. 結論より「問い」や「余白」で終わるとRTされやすい
5. ハッシュタグは末尾に #AI #生成AI のうち1〜2個まで
6. URLリンクをつける場合は文末に1つだけ（23文字換算）
7. ビジネス層が「保存・シェア」したくなる有益情報を含める
"""


class TweetCandidate(TypedDict):
    text: str
    image_url: str | None
    source_url: str | None


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweet_candidates(raw: str) -> list[str]:
    """
    番号付きリスト形式からツイート候補を抽出する。
    複数行にまたがるツイートにも対応。
    """
    candidates: list[str] = []
    current_lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+\S", stripped):
            if current_lines:
                tweet = " ".join(current_lines).strip()
                if tweet:
                    candidates.append(tweet)
            current_lines = [re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()]
        elif stripped and current_lines:
            current_lines.append(stripped)

    if current_lines:
        tweet = " ".join(current_lines).strip()
        if tweet:
            candidates.append(tweet)

    # X上限280文字（実質的な可読性のため200文字を上限とする）
    return [t for t in candidates if 0 < len(t) <= 280]


def fetch_article_image(url: str) -> str | None:
    """記事URLからog:imageを取得する"""
    try:
        resp = requests.get(
            url, timeout=6, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True
        )
        if resp.status_code != 200:
            return None
        html = resp.text
        # og:image のmeta tagを探す（属性順序が異なる2パターン）
        for pattern in [
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                img_url = m.group(1).strip()
                if img_url.startswith("http"):
                    return img_url
    except Exception:
        pass
    return None


def fetch_rss_items(max_items: int = 8) -> list[dict]:
    """RSSからタイトル・URL・サムネイルを取得する"""
    items: list[dict] = []
    seen_titles: set[str] = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or len(title) < 10 or title in seen_titles:
                    continue
                seen_titles.add(title)

                # enclosure または media_thumbnail から画像URL取得
                image_url = None
                for link_item in entry.get("links", []):
                    if link_item.get("type", "").startswith("image"):
                        image_url = link_item.get("href")
                        break
                if not image_url:
                    for thumb in entry.get("media_thumbnail", []):
                        image_url = thumb.get("url")
                        break

                items.append({"title": title, "url": link, "image_url": image_url})
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
) -> list[TweetCandidate]:
    """Note記事 + 過去実績 + バズりパターンから投稿候補を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"
            )

    link_instruction = f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""
    viral_patterns = fetch_viral_patterns()

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{viral_patterns}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは末尾に1〜2個まで
- ビジネス層・医療関係者が思わずRTしたくなる洞察を込める{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    texts = _extract_tweet_candidates(raw)

    image_url = fetch_article_image(note_url) if note_url else None
    return [
        TweetCandidate(text=t, image_url=image_url, source_url=note_url or None)
        for t in texts
    ]


def generate_posts_from_rss() -> list[TweetCandidate]:
    """最新AIニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_items()
    if not items:
        return _generate_original_ai_insight()

    # 最初のアイテムの画像を試みる（記事URLからog:imageも試みる）
    top_item = items[0]
    image_url = top_item.get("image_url")
    source_url = top_item.get("url")
    if not image_url and source_url:
        image_url = fetch_article_image(source_url)

    headlines_text = "\n".join(f"- {it['title']}" for it in items)
    viral_patterns = fetch_viral_patterns()

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{viral_patterns}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI・社会変革・未来への問いを絡めると尚良い
- ビジネス層が「これは知らなかった」と思える切り口にする
- ハッシュタグは末尾に1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    texts = _extract_tweet_candidates(raw)
    return [
        TweetCandidate(text=t, image_url=image_url, source_url=source_url)
        for t in texts
    ]


def _generate_original_ai_insight() -> list[TweetCandidate]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    viral_patterns = fetch_viral_patterns()

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{viral_patterns}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude・GPT・医療AI・AIと社会変革などのテーマを優先
- ビジネス層が思わずシェアしたくなる内容にする
"""
    raw = _call_claude(prompt)
    texts = _extract_tweet_candidates(raw)
    return [TweetCandidate(text=t, image_url=None, source_url=None) for t in texts]
