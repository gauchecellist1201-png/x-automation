"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けユーザー獲得目的のバズ投稿生成
"""

import os
import re
import feedparser
import requests
import anthropic
from dataclasses import dataclass

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+ChatGPT+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+AIエージェント+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+DX+自動化+業務効率+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語（グローバルトレンド）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+business+2026&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Claude+Google+Gemini+news&hl=en-US&gl=US&ceid=US:en",
]

MAX_TWEET_BODY = 250  # 250文字 + URL(23) = 273 < 280
NUM_CANDIDATES = 3
TWEET_SEP = "===TWEET==="

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学研究経験・国連会議参加のグローバル視点
- 専門知識を持ちながら、読者が行動したくなるメッセージを届けるスタイル
- 静かに鋭い洞察で、ビジネス層に「気づき」を与える
"""

VIRAL_STRATEGY = """
## バズるビジネス層向けAI投稿の戦略

### 高エンゲージメント切り口（優先順）
1. 衝撃ファクト型: 「これ知ってる人少なすぎる」「○○%が知らない事実」
2. データ・統計型: 「【調査】AI導入企業の利益率は非導入企業の2.3倍」
3. 逆張り・反直感型: 「AIが仕事を奪う」より「AIを使う人が仕事を奪う」
4. 問いかけ型: 最後を「？」で締める → RT・返信率↑
5. リスト型: 「5つの理由」でスレッドに誘導
6. FOMO型: 「今知らないと5年後に取り返せない」

### ビジネス層が反応するテーマ
- 生産性・ROI・コスト削減の具体的な数字
- 「競合他社がすでに使っている」系の危機感
- 日本企業のAI遅れ vs グローバルスタンダード
- 意思決定・採用・経営戦略とAI
- 医療×AI（著者固有の専門性でオリジナリティ）

### フォーマットルール
- 1文目: 最強のフック（スクロールを止める一言）
- 本文: 具体的・簡潔・数字を使う
- 末尾: 問いかけ or 行動促進フレーズ
- ハッシュタグ: 1〜2個のみ（#AI #生成AI のいずれか）
- 本文は250文字以内（URLは自動追加）
- 絵文字は効果的に使う（多用しない）
"""

VIRAL_EXAMPLES = """
## 高バズ投稿の参考フォーマット

【衝撃ファクト型】
ChatGPTが1時間でやる作業、人間だと丸3日。
でも日本企業の82%はまだ「試験導入段階」。

このギャップ、5年後には取り返せない。 #AI

【問いかけ型】
「AIが仕事を奪う」は半分正解。
正確には「AIを使いこなす人が仕事を奪う」。

この違いを理解して動いている人は、まだ少数派。
あなたはどちら側にいますか？ #生成AI

【データ型】
【2026年調査】
AI活用企業の生産性：+47%
未活用企業：+3%

「AIは難しい」はもう言い訳にならない。

【スレッドopener型】
医学生がAIで起業して気づいた5つのこと 🧵

3年前の自分に教えたい話です。

1/5↓

【逆張り型】
AIに脅かされていない職種がある。

医師・弁護士・コンサル——
でも実はこれらが最も早く変わる。

「変わらない」ではなく「変え方が違う」だけ。 #AI

【FOMO型】
今年AIを学んでいない経営者へ。

来年の競合との差は、もう埋められないかもしれない。
"""


@dataclass
class NewsItem:
    title: str
    url: str
    summary: str = ""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_tweet_candidates(raw: str) -> list[str]:
    """===TWEET=== セパレータで区切られた投稿案を抽出"""
    parts = raw.split(TWEET_SEP)
    candidates = []
    for part in parts:
        text = part.strip()
        # 「案1:」「[投稿案1]」などの番号プレフィックスを除去
        text = re.sub(r"^[\[【]?[投稿案\d]+[\]】\.:\s]+", "", text).strip()
        if text and 5 <= len(text) <= MAX_TWEET_BODY:
            candidates.append(text)
    return candidates[:NUM_CANDIDATES]


def fetch_rss_news(max_items: int = 8) -> list[NewsItem]:
    """複数RSSから最新AIニュースをURL付きで取得"""
    news_items: list[NewsItem] = []
    seen: set[str] = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()[:200]
                if title and url and title not in seen and len(title) > 10:
                    seen.add(title)
                    news_items.append(NewsItem(title=title, url=url, summary=summary))
        except Exception:
            continue

    return news_items[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事＋過去実績から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    url_instruction = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}
{VIRAL_EXAMPLES}
{few_shot}

## 出力形式（必ずこの形式で出力）
各案を {TWEET_SEP} で区切る。本文のみ（番号・ラベル不要）。250文字以内。{url_instruction}

{TWEET_SEP}
（投稿案1の本文）
{TWEET_SEP}
（投稿案2の本文）
{TWEET_SEP}
（投稿案3の本文）
{TWEET_SEP}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースからビジネス層向け投稿案を生成。(投稿案リスト, ニュースURL) を返す"""
    news_items = fetch_rss_news()

    if not news_items:
        return _generate_original_ai_insight(), ""

    news_summary = "\n".join(
        f"[{i + 1}] {item.title}\n    URL: {item.url}\n    概要: {item.summary[:100]}"
        for i, item in enumerate(news_items[:6])
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースからビジネス層が最も反応しそうなトピックを1つ選び、
バズる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}
{VIRAL_EXAMPLES}

## 出力形式（必ずこの順序で）
1行目: SELECTED_URL: [選んだニュースのURL]
その後、各案を {TWEET_SEP} で区切って出力。本文のみ、250文字以内。

SELECTED_URL: [URL]
{TWEET_SEP}
（投稿案1の本文）
{TWEET_SEP}
（投稿案2の本文）
{TWEET_SEP}
（投稿案3の本文）
{TWEET_SEP}

## 今日の最新AIニュース
{news_summary}
"""
    raw = _call_claude(prompt)

    selected_url = ""
    url_match = re.search(r"SELECTED_URL:\s*(https?://\S+)", raw)
    if url_match:
        selected_url = url_match.group(1)

    posts = _parse_tweet_candidates(raw)
    return posts, selected_url


def _generate_original_ai_insight() -> list[str]:
    """RSS取得不可時のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最重要のトピックについて、
ビジネス層に刺さるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}
{VIRAL_EXAMPLES}

## 出力形式
各案を {TWEET_SEP} で区切る。本文のみ、250文字以内。

{TWEET_SEP}
（投稿案1）
{TWEET_SEP}
（投稿案2）
{TWEET_SEP}
（投稿案3）
{TWEET_SEP}
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)
