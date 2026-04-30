"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

from trend_analyzer import get_viral_patterns, get_viral_formats

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求、スイスの大学・国連会議での経験あり
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- 2026年現在、Claude Codeを活用して医療×AI×ブロックチェーンで価値創出中
"""

BUSINESS_AUDIENCE_STRATEGY = """
## ビジネス層へのリーチ戦略
- 具体的な数字・ROI・生産性向上に言及する
- 「明日から使える」「自社に当てはめると」と思わせる実用性
- 経営者・管理職が抱える課題（人材・コスト・競争力）と直結させる
- ハッシュタグ: #AI #生成AI #ChatGPT #DX のうち1〜2個まで
- 過度なセールス感を排除し、洞察・価値提供を前面に
"""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し 140 文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def select_best_tweet(candidates: list[str]) -> str:
    """Claude がビジネス層へのバズり期待度でベスト1を選ぶ"""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿候補から、ビジネス層への拡散力・バズり期待度が最も高い1案を選んでください。

{numbered}

回答は選んだ番号（数字のみ）で答えてください。"""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    match = re.search(r"\d+", text)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]


def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
) -> list[str]:
    """Note 記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    viral_patterns = get_viral_patterns()
    viral_formats = get_viral_formats()

    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を再現）\n{examples}\n"

    link_note = f"\n- 文末に自然な形でNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるバズりX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_STRATEGY}

## バズりパターン（分析済み）
{viral_patterns}

## 使用するフォーマット（いずれか1つを選ぶ）
{viral_formats}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 3案それぞれ異なるフォーマットを使う{link_note}
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ).content[0].text
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 8) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    viral_patterns = get_viral_patterns()
    viral_formats = get_viral_formats()
    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるバズりX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_STRATEGY}

## バズりパターン（分析済み）
{viral_patterns}

## 使用するフォーマット（いずれか1つを選ぶ）
{viral_formats}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 3案それぞれ異なるフォーマットを使う
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ).content[0].text
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSS が取得できない場合のオリジナル洞察ツイート生成"""
    viral_patterns = get_viral_patterns()
    viral_formats = get_viral_formats()

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さるバズりX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE_STRATEGY}

## バズりパターン（分析済み）
{viral_patterns}

## 使用するフォーマット（いずれか1つを選ぶ）
{viral_formats}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 3案それぞれ異なるフォーマットを使う
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ).content[0].text
    return _extract_tweets(raw)
