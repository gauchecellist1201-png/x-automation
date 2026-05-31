"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic
from pathlib import Path

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 AI ニュース（グローバル最新情報）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+breakthrough&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+2026&hl=en&gl=US&ceid=US:en",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
THREAD_MAX_ITEMS = 5
NUM_CANDIDATES = 3

VIRAL_PATTERNS_FILE = Path("data/viral_patterns.md")

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議参加のグローバル視点
- 課題解決志向、専門的知識を一般読者にも届けるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- 問いを投げかけることでRTを促すスタイル
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（重要度順）

### フォーマット選択（状況に応じて使い分け）
A) 衝撃事実型: 数字＋断言「〜の仕事の37%はAIで代替可能」
B) 問い投げかけ型: 答えのない問いで終わる（最もRT率高）
C) 二項対立型: A vs B の構図でエンゲージメント増
D) 秘密暴露型: 「実は〜」「意外と知られていない〜」

### 文章の鉄則
- 1文目で掴む（スクロールを止める）
- 専門的だが難解すぎない言葉選び
- 結論より「問い」で終わるとRTされやすい
- 断言→根拠→問い の3段構成が理想
- ハッシュタグは1〜2個まで、文末に置く

### ビジネス層に刺さるキーワード
生産性・競合優位・意思決定・先行者利益・AIネイティブ・自動化・リスキリング
"""


def _load_viral_patterns() -> str:
    if VIRAL_PATTERNS_FILE.exists():
        return VIRAL_PATTERNS_FILE.read_text(encoding="utf-8")
    return ""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+[\.\)]", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def _extract_thread(raw: str) -> list[str]:
    """スレッド形式（1/n〜n/n）を抽出する"""
    items: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+/\d+", stripped) or re.match(r"^【\d+】", stripped):
            items.append(stripped)
        elif re.match(r"^[-•]\s+", stripped):
            cleaned = re.sub(r"^[-•]\s+", "", stripped)
            if cleaned:
                items.append(cleaned)
    return items[:THREAD_MAX_ITEMS]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) + バイラルパターンから戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    viral_patterns = _load_viral_patterns()
    viral_section = f"\n## バズるツイートパターン（参考）\n{viral_patterns[:2000]}\n" if viral_patterns else ""

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{viral_section}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、ビジネス層・一般読者にも刺さる言葉で{link_instruction}
- 「衝撃事実型」「問い投げかけ型」「二項対立型」から最適なフォーマットを選ぶこと
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_from_notes(note_text: str) -> list[str]:
    """Note記事からスレッド形式の投稿を生成（保存率・RT率が高い）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事から、ビジネス層に刺さるXスレッド投稿を作成してください。

{AUTHOR_PROFILE}

スレッド形式ルール:
- 1/5〜5/5 の5ツイートで構成
- 1ツイート目（フック）: 驚き・数字・問いで始める（最重要）
- 2〜4ツイート目: 具体例・根拠・洞察を展開
- 5ツイート目（まとめ）: 問いかけ or 行動を促すCTA
- 各ツイートは120文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力

## Note記事本文
{note_text[:3000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)
    return tweets[:THREAD_MAX_ITEMS] if tweets else []


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSからタイトル＋URLを取得"""
    items: list[dict] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}" for it in items)
    viral_patterns = _load_viral_patterns()
    viral_section = f"\n## バズるツイートパターン（参考）\n{viral_patterns[:1500]}\n" if viral_patterns else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さる洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{viral_section}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、ビジネス×AIの切り口を優先
- 「衝撃事実型」「問い投げかけ型」「二項対立型」から最適なフォーマットを選ぶ
- ハッシュタグは1〜2個まで
- 一般読者が「シェアしたい」と思える鋭い洞察を込める

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    viral_patterns = _load_viral_patterns()
    viral_section = f"\n## バズるツイートパターン（参考）\n{viral_patterns[:1500]}\n" if viral_patterns else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さる深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{viral_section}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 「衝撃事実型」「問い投げかけ型」「二項対立型」のいずれかを使う
- ビジネス経営者・管理職・スタートアップ起業家に刺さる内容
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
