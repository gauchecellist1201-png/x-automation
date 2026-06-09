"""
Claude API を使った戦略的投稿文生成モジュール
ターゲット: ビジネス層向けAI情報発信・フォロワー獲得
"""

import os
import re
import random
import anthropic
from viral_analyzer import (
    fetch_trending_ai_news,
    format_patterns_for_prompt,
    VIRAL_TWEET_PATTERNS,
)

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## アカウントコンセプト
- ビジネス層向けAI最新情報・活用事例を発信するアカウント
- ターゲット読者: 経営者・管理職・ビジネスパーソン・AI導入担当者
- ゴール: フォロワー獲得・エンゲージメント最大化
- スタイル: 専門的かつ実践的、難解すぎない、今日から使える視点
- 発信テーマ: 最新AI情報、ビジネス活用事例、未来予測、実践ノウハウ
"""

TWEET_RULES = """
## ツイート生成ルール
- 140文字以内（URLは23文字換算）
- ハッシュタグは #AI #生成AI #ビジネスAI のうち1〜2個まで
- 具体的な数字・事例を入れると拡散力が2〜3倍になる
- 絵文字は1〜2個まで（使う場合は冒頭か末尾）
- スレッドフック（🧵）はパターン「スレッドフック」専用
- URLは「案3」にのみ入れる（指示がある場合）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_numbered_tweets(raw: str) -> list[str]:
    """番号付きリストからツイート本文を抽出・整形"""
    tweets = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)[\.\)]\s*(.+)$", line)
        if not m:
            continue
        tweet = m.group(2).strip()
        # 余分なラベル・括弧を除去
        tweet = re.sub(r"^\[[\w_]+\]\s*", "", tweet)
        tweet = re.sub(r"^【[\w\s]+】\s*", "", tweet)
        if 10 < len(tweet) <= MAX_TWEET_LENGTH + 30:  # URL分の余裕
            tweets.append(tweet[:MAX_TWEET_LENGTH + 30])
    return tweets


def _pick_patterns(n: int = NUM_CANDIDATES) -> list[dict]:
    """毎日バリエーションが出るようパターンをランダムに選択"""
    return random.sample(VIRAL_TWEET_PATTERNS, min(n, len(VIRAL_TWEET_PATTERNS)))


def generate_posts_from_rss() -> list[dict]:
    """最新AIトレンドニュースからビジネス向けバイラルツイートを生成"""
    topics = fetch_trending_ai_news(max_items=10)

    if topics:
        top = topics[0]
        headlines_text = "\n".join(f"- {t.title}" for t in topics[:8])
        source_url = top.url
        source_title = top.title
    else:
        return _generate_original_ai_insight()

    selected_patterns = _pick_patterns(NUM_CANDIDATES)
    patterns_text = format_patterns_for_prompt([p["id"] for p in selected_patterns])

    link_note = (
        f"\n- 案{NUM_CANDIDATES}にはこのニュースリンクを文末に入れてよい（23文字換算）: {source_url}"
        if source_url else ""
    )

    prompt = f"""あなたはビジネス層向けAI情報発信アカウントの投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネスパーソンに強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_RULES}

## 今日使うバイラルパターン（それぞれ1案ずつ、順番通りに）
{patterns_text}
{link_note}

## 今日の最新AIニュース（最もビジネス関連度が高いものを優先）
{headlines_text}

出力形式（ツイート本文のみ、説明不要）:
1. [ツイート本文]
2. [ツイート本文]
3. [ツイート本文]
"""
    raw = _call_claude(prompt)
    tweets = _extract_numbered_tweets(raw)

    result = []
    for i, tweet in enumerate(tweets[:NUM_CANDIDATES]):
        pattern = selected_patterns[i] if i < len(selected_patterns) else selected_patterns[0]
        result.append({
            "tweet": tweet,
            "pattern_name": pattern["name"],
            "pattern_id": pattern["id"],
            "image_hint": pattern["image_hint"],
            "source_url": source_url if i == NUM_CANDIDATES - 1 else "",
            "source_title": source_title,
        })
    return result


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[dict]:
    """Note記事 + 過去実績（few-shot）からバイラルツイートを生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    selected_patterns = _pick_patterns(NUM_CANDIDATES)
    patterns_text = format_patterns_for_prompt([p["id"] for p in selected_patterns])
    link_note = (
        f"\n- 案{NUM_CANDIDATES}には以下のNoteリンクを文末に入れてよい（23文字換算）: {note_url}"
        if note_url else ""
    )

    prompt = f"""あなたはビジネス層向けAI情報発信アカウントの投稿担当AIです。
以下のNote記事を読み、ビジネスパーソンに刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_RULES}

## 今日使うバイラルパターン（それぞれ1案ずつ、順番通りに）
{patterns_text}
{link_note}
{few_shot}
## Note記事本文
{note_text[:4000]}

出力形式（ツイート本文のみ、説明不要）:
1. [ツイート本文]
2. [ツイート本文]
3. [ツイート本文]
"""
    raw = _call_claude(prompt)
    tweets = _extract_numbered_tweets(raw)

    result = []
    for i, tweet in enumerate(tweets[:NUM_CANDIDATES]):
        pattern = selected_patterns[i] if i < len(selected_patterns) else selected_patterns[0]
        result.append({
            "tweet": tweet,
            "pattern_name": pattern["name"],
            "pattern_id": pattern["id"],
            "image_hint": pattern["image_hint"],
            "source_url": note_url if i == NUM_CANDIDATES - 1 else "",
            "source_title": "Note記事",
        })
    return result


def _generate_original_ai_insight() -> list[dict]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成（フォールバック）"""
    selected_patterns = _pick_patterns(NUM_CANDIDATES)
    patterns_text = format_patterns_for_prompt([p["id"] for p in selected_patterns])

    prompt = f"""あなたはビジネス層向けAI情報発信アカウントの投稿担当AIです。
2026年のAI業界で最も重要なビジネストピックについて、
経営者・ビジネスパーソンに強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_RULES}

## 今日使うバイラルパターン（それぞれ1案ずつ）
{patterns_text}

優先テーマ: AI自動化・業務効率化・AIエージェント・企業のAI戦略・AIと雇用・ROI

出力形式（ツイート本文のみ、説明不要）:
1. [ツイート本文]
2. [ツイート本文]
3. [ツイート本文]
"""
    raw = _call_claude(prompt)
    tweets = _extract_numbered_tweets(raw)

    result = []
    for i, tweet in enumerate(tweets[:NUM_CANDIDATES]):
        pattern = selected_patterns[i] if i < len(selected_patterns) else selected_patterns[0]
        result.append({
            "tweet": tweet,
            "pattern_name": pattern["name"],
            "pattern_id": pattern["id"],
            "image_hint": pattern["image_hint"],
            "source_url": "",
            "source_title": "AIビジネス洞察",
        })
    return result
