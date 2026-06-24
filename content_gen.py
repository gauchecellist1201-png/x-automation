"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import requests
import anthropic
from typing import Optional
from dataclasses import dataclass, field

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 5

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+LLM+生成AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+ChatGPT+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+business+2026&hl=en&gl=US&ceid=US:en",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求し、PHR/EHRへのブロックチェーン活用を研究
- スイスの大学での研究経験、国連会議参加などグローバル視点を持つ
- Claude Codeなど最新AIツールで医療×AI×ブロックチェーンの価値創出に挑む
- 読者に「考えさせる問い」を投げかける静かに鋭いスタイル
"""

TWEET_STRATEGY = """
## ビジネス層に刺さるバズるAI投稿の戦略（実証パターン）

### 高エンゲージメントの共通要素
1. 最初の1文で「え？」「知らなかった」と思わせる衝撃フック
2. 具体的な数字・割合・時間削減を入れる（"30%改善"より"5時間→20分"）
3. 読者自身の状況に重ねやすい問いかけ or 仮説
4. Before/After構造か対比で変化を視覚化
5. 医療×AI、社会変革、未来への個人的洞察を絡める
6. ハッシュタグは #AI か #生成AI のうち最大1個（多用は逆効果）
7. URLを含む場合は価値ある情報源のみ（X内カウントは23文字）
8. 最後を問いかけで終わるとリプライ数が増える

### 実証済みのバズパターン
- 【衝撃スタート】「○○企業がAIで採用を30%削減。でも生産性は2倍になった」
- 【逆説型】「AIが"賢く"なるほど、人間に求められるスキルが変わる。医師の仕事も例外じゃない」
- 【実体験+普遍化】「先週Claudeで論文サーベイを2時間→15分にした。これが当たり前になる日が来る」
- 【データ提示型】「2026年、AI導入企業の利益率は非導入企業の2.3倍に。この差は今後さらに広がる」
- 【リスト型】「AIで変わる医師の仕事3つ\n①〜\n②〜\n③〜\nあなたはもう始めてますか？」
- 【問い型】「ChatGPT登場から3年。あなたの仕事の何%をAIに任せていますか？」
"""

VIRAL_SCORING_CRITERIA = """
## バイラルスコアリング基準
各案を以下で評価し、最も高い案を選ぶ:
- フック力: 1文目で読み続けたくなるか (0-3点)
- 具体性: 数字・事例・体験が入っているか (0-3点)
- 共感性: ビジネス層が「自分ごと」にできるか (0-3点)
- 差別化: 他のAI投稿と違う視点があるか (0-2点)
- 行動喚起: いいね・RT・返信したくなるか (0-2点)
合計13点満点
"""


@dataclass
class NewsItem:
    title: str
    url: str = ""
    summary: str = ""
    image_url: str = ""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出（複数行・280文字対応）"""
    # Split by numbered list markers at the start of a line
    blocks = re.split(r"\n(?=\d+[\.\)])", raw.strip())
    tweets: list[str] = []
    for block in blocks:
        text = re.sub(r"^\d+[\.\)]\s*", "", block.strip())
        text = text.strip()
        # Allow multi-line tweets (newlines count as 1 char each)
        if text and 10 < len(text) <= MAX_TWEET_LENGTH:
            tweets.append(text)
    return tweets


def _pick_best_tweet(candidates: list[str]) -> str:
    """Claude にスコアリングさせて最もバイラルな案を1つ返す"""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿案から、ビジネス層への訴求力・バイラルポテンシャルが最も高い1案を選んでください。

{VIRAL_SCORING_CRITERIA}

## 投稿候補
{numbered}

## 出力形式
選んだ案の番号のみ（例: 3）を出力してください。理由は不要です。"""

    raw = _call_claude(prompt).strip()
    match = re.search(r"\d+", raw)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]


def fetch_ogp_image(url: str) -> Optional[bytes]:
    """記事URLからOGP画像バイトを取得する"""
    if not url:
        return None
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; x-automation-bot/1.0)"},
        )
        # Simple OGP extraction without BeautifulSoup dependency
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)',
            resp.text,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\'](https?://[^"\']+)[^>]+property=["\']og:image["\']',
                resp.text,
            )
        if match:
            img_url = match.group(1)
            img_resp = requests.get(img_url, timeout=8)
            if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                return img_resp.content
    except Exception:
        pass
    return None


def fetch_rss_headlines(max_items: int = 10) -> list[NewsItem]:
    """複数のRSSフィードから最新AIニュースを収集する"""
    seen: set[str] = set()
    items: list[NewsItem] = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "")[:300]
                if not title or len(title) < 10:
                    continue
                key = title[:50]
                if key in seen:
                    continue
                seen.add(key)
                items.append(NewsItem(title=title, url=link, summary=summary))
                if len(items) >= max_items:
                    return items
        except Exception:
            continue

    return items


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line
            for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"
            )

    link_instruction = (
        f"\n- 文末にNoteリンクを入れてもよい（URL={note_url}、X上では23文字カウント）"
        if note_url
        else ""
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- ハッシュタグは最大1個
- 改行を効果的に使ってよい（読みやすさのため）{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:5000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], Optional[str], Optional[str]]:
    """最新AIニュースから @GAUCHE_cellist らしい意見投稿を生成。

    Returns:
        (tweet candidates, best_article_url, best_article_image_url)
    """
    news_items = fetch_rss_headlines()
    if not news_items:
        return _generate_original_ai_insight(), None, None

    headlines_text = "\n".join(
        f"- {item.title}" + (f"\n  URL: {item.url}" if item.url else "")
        for item in news_items
    )

    # Select most interesting item via Claude
    select_prompt = f"""以下のAIニュース一覧から、ビジネス層に最もインパクトがある記事を1つ選び、
その番号だけを出力してください（例: 3）。

{chr(10).join(f'{i+1}. {item.title}' for i, item in enumerate(news_items))}"""

    raw_sel = _call_claude(select_prompt).strip()
    sel_match = re.search(r"\d+", raw_sel)
    selected_item = news_items[0]
    if sel_match:
        idx = int(sel_match.group()) - 1
        if 0 <= idx < len(news_items):
            selected_item = news_items[idx]

    article_url = selected_item.url
    article_image: Optional[bytes] = None
    if article_url:
        article_image = fetch_ogp_image(article_url)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースについて、井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは最大1個
- 記事URLを入れてもよい: {article_url}

## 今日の注目AIニュース（選定済み）
タイトル: {selected_item.title}
概要: {selected_item.summary}

## その他の最新ニュース（参考）
{headlines_text}
"""
    raw = _call_claude(prompt)
    candidates = _extract_tweets(raw)

    # article_image bytes stored for caller; return URL for logging
    image_url = article_url if article_image else None
    return candidates, article_url, image_url


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- Claude、GPT-5、医療AI、AIと社会変革などのテーマを優先
- ハッシュタグは最大1個
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def pick_best(candidates: list[str]) -> str:
    """候補からバイラルポテンシャル最高の1案を返す"""
    return _pick_best_tweet(candidates)
