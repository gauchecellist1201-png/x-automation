"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import xml.etree.ElementTree as ET
import anthropic
import requests
from dataclasses import dataclass, field
from viral_patterns import (
    BUSINESS_AUDIENCE_PROFILE,
    VIRAL_HOOKS,
    TWEET_FORMATS,
    THREAD_FORMAT,
    ENGAGEMENT_CHECKLIST,
    AVOID_PATTERNS,
)

RSS_FEEDS = [
    # Google News（日本語AI関連）
    "https://news.google.com/rss/search?q=AI+人工知能+ChatGPT+Claude&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Google+AI+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AI専門メディア
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://the-decoder.com/feed/",
]

MAX_TWEET_LENGTH = 140
URL_LENGTH = 23  # X上でのURL固定文字数
NUM_CANDIDATES = 3


@dataclass
class PostContent:
    tweets: list[str] = field(default_factory=list)     # シングルツイート候補
    thread: list[str] = field(default_factory=list)     # スレッド形式（複数ツイート）
    image_prompt: str = ""                               # 画像生成プロンプト
    source_url: str = ""                                 # 参照記事URL
    source_title: str = ""                               # 参照記事タイトル


AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大テーマに活動
- スイス大学での研究経験・国連会議参加のグローバル視点
- Claude Codeなど最新AIツールを実践活用
- 専門知識を持ちながら読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""


def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=(
            "あなたはバイラルマーケティングの専門家兼AIエキスパートです。"
            "X（旧Twitter）でビジネス層に刺さる、エンゲージメントの高い投稿を作成します。"
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweet_blocks(raw: str) -> list[str]:
    """番号付きブロックからツイート本文を抽出（複数行対応）"""
    # 番号ラベルで分割（1. / 1) / 【案1】 などに対応）
    blocks = re.split(r'\n(?=(?:\d+[\.\)]|\【案\d+\】))', raw.strip())
    tweets = []
    for block in blocks:
        text = re.sub(r'^(?:\d+[\.\)]|\【案\d+\】)\s*', '', block).strip()
        if not text:
            continue
        # URL換算: URLは23文字
        url_count = len(re.findall(r'https?://\S+', text))
        url_chars = sum(len(u) for u in re.findall(r'https?://\S+', text))
        adjusted_len = len(text) - url_chars + url_count * URL_LENGTH
        if 10 < adjusted_len <= MAX_TWEET_LENGTH + 10:  # 少し余裕を持たせる
            tweets.append(text)
    return tweets[:NUM_CANDIDATES]


def _extract_thread_blocks(raw: str) -> list[str]:
    """スレッド番号（1/n: ...）ブロックを抽出"""
    blocks = re.split(r'\n(?=\d+/\d+[:\s])', raw.strip())
    tweets = []
    for block in blocks:
        text = re.sub(r'^\d+/\d+[:\s]*', '', block).strip()
        if text and len(text) > 5:
            tweets.append(text)
    return tweets


def _generate_image_prompt(topic: str) -> str:
    """投稿テーマに合った画像プロンプトをClaudeで生成"""
    prompt = f"""
以下のトピックのX投稿に添付する画像のプロンプトを1文で作成してください。
（Canva・Midjourney・DALL-Eで使用）

トピック: {topic}

条件:
- ビジネス層に刺さるプロフェッショナルなビジュアル
- 日本語・英語混在可
- 50文字以内
- 「画像:」で始める
"""
    result = _call_claude(prompt, max_tokens=200)
    return result.strip()


def _parse_rss(xml_text: str) -> list[dict]:
    """RSS/Atom XMLからタイトルとURLを抽出（標準ライブラリのみ使用）"""
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        # Atom形式
        for entry in root.findall(".//atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.get("href", "") if link_el is not None else ""
            if title and len(title) > 10:
                items.append({"title": title, "url": link})
        # RSS 2.0形式（Atomで何も取れなかった場合）
        if not items:
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                if title and len(title) > 10:
                    items.append({"title": title, "url": link})
    except ET.ParseError:
        pass
    return items


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSからタイトル・URLを取得（標準ライブラリのみ）"""
    items: list[dict] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSS-Reader/1.0)"}
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            items.extend(_parse_rss(resp.text))
        except Exception:
            continue
        if len(items) >= max_items:
            break
    # 重複除去（タイトルで）
    seen: set[str] = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
) -> PostContent:
    """Note記事から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    url_note = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""
{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_PROFILE}
{TWEET_FORMATS}
{ENGAGEMENT_CHECKLIST}
{AVOID_PATTERNS}
{few_shot}

## タスク
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 上記フォーマットのどれかを必ず使う{url_note}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweet_blocks(raw)

    # スレッド生成
    thread = _generate_thread(
        topic=note_text[:500],
        source_url=note_url,
    )

    # 画像プロンプト
    topic_summary = note_text[:100].replace("\n", " ")
    image_prompt = _generate_image_prompt(topic_summary)

    return PostContent(
        tweets=tweets,
        thread=thread,
        image_prompt=image_prompt,
        source_url=note_url,
    )


def generate_posts_from_rss() -> PostContent:
    """最新AIニュースからバイラル投稿案を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h['title']}" for h in headlines)
    # 最も注目度が高そうな記事URLを1つ選ぶ
    source_url = headlines[0]["url"] if headlines else ""
    source_title = headlines[0]["title"] if headlines else ""

    prompt = f"""
{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_PROFILE}
{TWEET_FORMATS}
{ENGAGEMENT_CHECKLIST}
{AVOID_PATTERNS}

## タスク
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI・ビジネス変革・未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 上記フォーマットのどれかを必ず使う
- 関連する記事URLを文末に入れてもよい（23文字換算）

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweet_blocks(raw)

    # 最もビジネス関連度が高いトピックでスレッド生成
    thread = _generate_thread(
        topic=source_title,
        source_url=source_url,
    )

    image_prompt = _generate_image_prompt(source_title[:80])

    return PostContent(
        tweets=tweets,
        thread=thread,
        image_prompt=image_prompt,
        source_url=source_url,
        source_title=source_title,
    )


def _generate_thread(topic: str, source_url: str = "") -> list[str]:
    """4ツイートのスレッドを生成"""
    url_note = f"\n- 最後のツイートに参照URL入れてもよい: {source_url}" if source_url else ""

    prompt = f"""
{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_PROFILE}
{THREAD_FORMAT}
{ENGAGEMENT_CHECKLIST}

## タスク
以下のトピックについて、X用の4ツイートスレッドを作成してください。

トピック: {topic}

ルール:
- 各ツイートは「1/4:」「2/4:」「3/4:」「4/4:」で始める
- 各ツイートは100文字以内（スレッドはコンパクトに）
- 1/4は「続きが気になる」フックにする
- 4/4はフォロー・保存を促すCTA{url_note}
- ハッシュタグは4/4にのみ1〜2個
"""
    raw = _call_claude(prompt, max_tokens=1024)
    return _extract_thread_blocks(raw)


def _generate_original_ai_insight() -> PostContent:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""
{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_PROFILE}
{TWEET_FORMATS}
{ENGAGEMENT_CHECKLIST}
{AVOID_PATTERNS}

## タスク
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さる深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude・GPT・医療AI・AI×ビジネス変革などのテーマを優先
- 上記フォーマットのどれかを必ず使う
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweet_blocks(raw)
    thread = _generate_thread(topic="2026年のAIとビジネスの未来")
    image_prompt = _generate_image_prompt("2026年のAIとビジネス変革")

    return PostContent(
        tweets=tweets,
        thread=thread,
        image_prompt=image_prompt,
    )
