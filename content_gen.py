"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import requests
import anthropic
from dataclasses import dataclass
from xml.etree import ElementTree as ET

RSS_FEEDS = [
    # 日本語 AI/ビジネス
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ChatGPT+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+経営+DX+自動化+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語グローバルトレンド（タイトルのみ参照）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+business+enterprise&hl=en&gl=US&ceid=US:en",
]

# X(Twitter)の文字数カウント仕様
# CJK文字は1文字=2ウェイト、URLは常に23ウェイト
# 上限280ウェイト → 日本語のみなら140文字
MAX_TWEET_CHARS = 140   # 日本語基準の最大文字数
URL_WEIGHT = 23         # t.co短縮後のURL消費文字数
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求、スイス研究経験、国連会議参加
- 課題解決志向、グローバル視点、専門知識を持ちながら一般読者にも届ける
- ターゲット読者：経営者・管理職・スタートアップ創業者・医療従事者
"""

# 実証済みバイラルパターン（日本語X・ビジネス層向け）
VIRAL_PATTERNS = """
## バズるAI投稿の実証済みパターン（必ずこれを参考に）

### パターン1: 数字×衝撃の事実
AIで年間1000万円削減した中小企業が増えている。
ツールのコストは月3万円以下。
この差を生む「使い方の差」がすべて。 #AI #DX

### パターン2: 逆張り×本質をつく
「AIはまだ補助ツール」と言う経営者が2年後に後悔する理由。
補助ではない。意思決定のコアになっている。
この認識差が、企業の生存を分ける。 #生成AI

### パターン3: 問いかけ×自分事化
あなたの会社のAI導入、誰が主導していますか？
IT部門が主導 → 失敗しやすい
経営者自身が主導 → 成功しやすい
これはデータが示している事実です。 #AI経営

### パターン4: ビフォーアフター時系列
2023年：ChatGPTを「試した」
2024年：業務の一部に組み込んだ
2025年：AIなしでは動けない設計になった
2026年：AIを知らない人材を採用できなくなる #生成AI

### パターン5: 医療×AI（専門性を活かす）
AIが診断を奪うという恐怖は誤解だった。
AIは医師の見落としを防ぎ、患者と向き合う時間を増やす。
本当の敵は「AIを使わない慣習」かもしれない。 #医療AI

### パターン6: シンプルな洞察
「AIに仕事を奪われる」より「AIを使える人に仕事が集まる」の方が正確。
同じ時代に生きているのに、差は広がる一方。 #AI

## 共通の成功要素（必ず守る）
- 1行目：「続きを読む」と思わせる引きの強い一文
- 具体的な数字を入れると共有率が上がる（「3倍」「30%」「1000万円」など）
- 問いで終わるとRT・引用が増える
- 改行を活用して視覚的に読みやすくする
- ハッシュタグは1〜2個に絞る（多いと逆効果）
- ビジネス層が「自社に当てはまる」と感じる具体性
"""


@dataclass
class NewsItem:
    title: str
    url: str = ""
    summary: str = ""
    image_url: str = ""
    source: str = ""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _score_tweet(tweet: str) -> float:
    """バイラル要素に基づくヒューリスティックスコアリング"""
    score = 0.0
    # 数字があるとシェアされやすい
    if re.search(r'\d+', tweet):
        score += 2.0
    # 問いかけで終わる → RT率向上
    if tweet.strip().endswith(('？', '?', 'か。', 'のか。')):
        score += 1.5
    # ハッシュタグ1〜2個が最適
    hashtag_count = len(re.findall(r'#\w+', tweet))
    if 1 <= hashtag_count <= 2:
        score += 1.0
    # 最適文字数（80〜120文字）
    length = len(tweet.replace('\n', ''))
    if 80 <= length <= 120:
        score += 1.0
    elif 60 <= length <= 130:
        score += 0.5
    # 改行による視覚構造
    if tweet.count('\n') >= 1:
        score += 0.5
    # ビジネス層キーワード
    biz_keywords = ['経営', '企業', 'コスト', '効率', '採用', '競合', 'DX', '自動化', '業務']
    if any(kw in tweet for kw in biz_keywords):
        score += 0.5
    # AI専門キーワード
    ai_keywords = ['Claude', 'GPT', 'LLM', '生成AI', '大規模言語モデル']
    if any(kw in tweet for kw in ai_keywords):
        score += 0.3
    return score


def _extract_tweets(raw: str, max_chars: int = MAX_TWEET_CHARS) -> list[str]:
    """Claude出力から有効なツイートを抽出・スコアリングして返す"""
    tweets: list[str] = []

    # 番号付きブロックに分割（ルックアヘッドで番号行の手前を分割点にする）
    blocks = re.split(r'\n(?=\d+[\.\)]\s)', raw.strip())

    for block in blocks:
        # 番号プレフィックスを除去
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', block.strip())
        # 末尾の空行・余分な空白を整理
        cleaned = re.sub(r'\n{2,}', '\n', cleaned).strip()
        if not cleaned or len(cleaned) < 15:
            continue
        # 文字数チェック（ゆとりを10文字持たせて柔軟に）
        effective_len = len(cleaned.replace('\n', ''))
        if effective_len <= max_chars + 10:
            tweets.append(cleaned)

    # フォールバック：行単位でシンプルに解析
    if not tweets:
        for line in raw.splitlines():
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            if 20 <= len(cleaned) <= max_chars:
                tweets.append(cleaned)

    # スコアで降順ソート（最良案を先頭に）
    tweets.sort(key=_score_tweet, reverse=True)
    return tweets[:NUM_CANDIDATES]


def _parse_rss_xml(xml_text: str) -> list[dict]:
    """RSS 2.0 XML を標準ライブラリでパースしてエントリリストを返す"""
    entries = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return entries

    ns = {"media": "http://search.yahoo.com/mrss/"}
    channel = root.find("channel")
    if channel is None:
        return entries

    feed_title = (channel.findtext("title") or "").strip()

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        url = (item.findtext("link") or "").strip()
        summary = re.sub(r'<[^>]+>', '', item.findtext("description") or "")[:200]

        # 画像URL（media:content から）
        image_url = ""
        media_content = item.find("media:content", ns)
        if media_content is not None:
            image_url = media_content.get("url", "")

        entries.append({
            "title": title,
            "url": url,
            "summary": summary,
            "image_url": image_url,
            "source": feed_title,
        })
    return entries


def fetch_top_news(max_items: int = 12) -> list[NewsItem]:
    """RSSから最新AIニュースを取得（URL・サマリー付き）"""
    items: list[NewsItem] = []
    seen: set[str] = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RSS-Reader/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=15)
            resp.raise_for_status()
            entries = _parse_rss_xml(resp.text)

            for entry in entries[:max_items]:
                title = entry["title"]
                if len(title) < 10:
                    continue
                # 重複排除（タイトル正規化）
                key = re.sub(r'[^\w]', '', title.lower())[:40]
                if key in seen:
                    continue
                seen.add(key)

                items.append(NewsItem(
                    title=title,
                    url=entry["url"],
                    summary=entry["summary"],
                    image_url=entry["image_url"],
                    source=entry["source"],
                ))
                if len(items) >= max_items:
                    return items
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を再現）\n{examples}\n"

    url_rule = (
        f"\n- 文末にNoteリンクを自然に入れる（URL={URL_WEIGHT}文字換算で140文字以内）: {note_url}"
        if note_url else ""
    )
    max_chars = MAX_TWEET_CHARS - (URL_WEIGHT if note_url else 0)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

【出力ルール】
- 各投稿は{max_chars}文字以内{url_rule}
- 番号付きリスト（1. 2. 3.）で出力し、番号の直後から投稿本文を書く
- 各案の間に説明は不要（投稿文のみ）
- ハッシュタグは1〜2個まで
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw, max_chars=max_chars)


def generate_posts_from_news(news_items: list[NewsItem]) -> tuple[list[str], NewsItem | None]:
    """最新AIニュースを元に、バズる意見投稿を生成。採用したニュースアイテムも返す。"""
    if not news_items:
        return _generate_original_ai_insight(), None

    # URL付加を想定した文字数制限
    max_chars = MAX_TWEET_CHARS - URL_WEIGHT

    headlines_block = "\n".join(
        f"{i+1}. 【{item.source[:20]}】{item.title}"
        + (f"\n   概要: {item.summary[:80]}" if item.summary else "")
        for i, item in enumerate(news_items[:10])
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから、ビジネス層に最も刺さるトピックを1つ選び、
バズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

【出力ルール】
- 最初に「選んだニュース番号: X」と明記（Xは選んだ番号）
- 各投稿は{max_chars}文字以内（文末に記事URLを付加するため）
- 番号付きリスト（1. 2. 3.）で出力し、番号の直後から投稿本文を書く
- 各案の間に説明は不要（投稿文のみ）
- ハッシュタグは1〜2個まで
- 医療×AI・社会変革・ビジネスインパクトの視点を絡める
- 経営者が「うちの会社も考えないと」と感じる具体性

## 今日の最新AIニュース
{headlines_block}
"""
    raw = _call_claude(prompt)

    # 採用ニュースを特定
    selected: NewsItem | None = None
    m = re.search(r'選んだニュース番号[：:]\s*(\d+)', raw)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(news_items):
            selected = news_items[idx]

    tweets = _extract_tweets(raw, max_chars=max_chars)
    return tweets, selected


def _generate_original_ai_insight() -> list[str]:
    """RSS取得不可時のフォールバック：オリジナル洞察ツイート"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
バズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

【出力ルール】
- 各投稿は{MAX_TWEET_CHARS}文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude・GPT・医療AI・AIと社会変革などを優先テーマに
- ビジネス層への洞察を最優先
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> list[str]:
    """後方互換性のためのラッパー"""
    news_items = fetch_top_news()
    tweets, _ = generate_posts_from_news(news_items)
    return tweets
