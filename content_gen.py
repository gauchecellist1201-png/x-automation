"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向け・バズ最適化版 v2
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass, field

RSS_FEEDS = [
    # 日本語AI系
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AI系（主要メディア）
    "https://venturebeat.com/category/ai/feed/",
    "https://www.technologyreview.com/feed/",
    "https://news.google.com/rss/search?q=AI+agents+Claude+GPT+Gemini+2026&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3


@dataclass
class PostCandidate:
    tweet: str
    buzz_reason: str = ""
    image_hint: str = ""
    thread_hook: str = ""
    source_url: str = ""
    source_title: str = ""


AUTHOR_PROFILE = """
## 著者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合が最大テーマ
- スイス研究・国連会議参加のグローバル視点
- ターゲット読者：ビジネスパーソン、経営者、医療従事者、テック業界人
"""

BUZZ_PATTERNS = """
## バズる投稿の黄金パターン（実績分析）
1. 【数字型】「〜の73%が知らない」「〜で生産性40%UP」→ 具体数字でFOMO刺激
2. 【衝撃型】「3年後、〜が変わる。あなたは準備できている？」→ 危機感
3. 【逆説型】「AIが進化するほど医師の価値が上がる理由」→ 意外性・反論誘発
4. 【リスト型】「今すぐ使えるAIツール3選」→ 保存・シェア率が高い
5. 【問いかけ型】「まだ〜してないんですか？」→ エンゲージメント誘発
6. 【未来予測型】「2027年、〜業界はこう変わる」→ 専門家権威の確立
7. 【比較型】「AI活用の経営者 vs 未活用の経営者の5年後」→ 対比で行動促進
8. 【当事者型】「医学生の私が実際に〜して分かったこと」→ 信頼性・親近感
"""

BUSINESS_ANGLE = """
## ビジネス層への訴求軸（必ず1つ以上絡める）
- 生産性・時間削減（「週〇時間削減」「〇倍速く」など具体数字があれば尚良）
- コスト削減・ROI（「導入費用の〇倍のリターン」など）
- 競合優位性（「乗り遅れると〜になる」「先行者利益」）
- キャリアリスク・スキルアップ（「5年後に後悔しないために」）
- 意思決定の質向上（「データドリブン」「根拠ある判断」）
"""

TWEET_RULES = """
## 投稿ルール
- 140文字以内（URLは23文字換算で含む）
- 最初の1文で「続きを読みたい」と思わせるhookを必ず入れる
- ハッシュタグは1〜2個（#AI #生成AI #医療AI から選ぶ）
- 専門用語は使わず、誰でも分かる言葉で深い洞察を
- 結論より問いで終わるとRT・いいねが増える
"""

OUTPUT_FORMAT = """
## 必須出力形式（この形式を厳守すること）

【案1】
本文: （ツイート本文、140文字以内）
理由: （なぜ伸びるか、どのパターンか、1行で）
画像: （効果的な画像・グラフ・ビジュアル案、1行で）
スレッド: （続きを展開するなら何を書くか、1行で）

【案2】
本文: ...
理由: ...
画像: ...
スレッド: ...

【案3】
本文: ...
理由: ...
画像: ...
スレッド: ...
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_candidates(
    raw: str, source_url: str = "", source_title: str = ""
) -> list[PostCandidate]:
    """【案N】形式のレスポンスをPostCandidateリストにパース"""
    candidates: list[PostCandidate] = []
    blocks = re.split(r"【案\d+】", raw)

    for block in blocks:
        if not block.strip():
            continue

        tweet = buzz_reason = image_hint = thread_hook = ""

        for line in block.splitlines():
            line = line.strip()
            if re.match(r"^本文[:：]", line):
                tweet = re.sub(r"^本文[:：]\s*", "", line).strip()
            elif re.match(r"^理由[:：]", line):
                buzz_reason = re.sub(r"^理由[:：]\s*", "", line).strip()
            elif re.match(r"^画像[:：]", line):
                image_hint = re.sub(r"^画像[:：]\s*", "", line).strip()
            elif re.match(r"^スレッド[:：]", line):
                thread_hook = re.sub(r"^スレッド[:：]\s*", "", line).strip()

        if tweet:
            candidates.append(
                PostCandidate(
                    tweet=tweet,
                    buzz_reason=buzz_reason,
                    image_hint=image_hint,
                    thread_hook=thread_hook,
                    source_url=source_url,
                    source_title=source_title,
                )
            )

    return candidates[:NUM_CANDIDATES]


def fetch_rss_items(max_items: int = 10) -> list[tuple[str, str]]:
    """(title, url) のリストを返す"""
    items: list[tuple[str, str]] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append((title, link))
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for title, link in items:
        if title not in seen:
            seen.add(title)
            unique.append((title, link))
    return unique[:max_items]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[PostCandidate]:
    """Note記事から戦略的・バズ最適化された投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l
            for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"
            )

    link_note = f"\n- 必ず文末にNoteリンクを含めること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿戦略家です。
以下のNote記事を読み、爆発的に伸びるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{BUSINESS_ANGLE}
{TWEET_RULES}{link_note}
{few_shot}
{OUTPUT_FORMAT}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_candidates(raw, source_url=note_url)


def generate_posts_from_rss() -> list[PostCandidate]:
    """最新AIニュースから爆発的に伸びる投稿案を生成"""
    items = fetch_rss_items()
    if not items:
        return _generate_original_insight()

    headlines_text = "\n".join(f"- {title}" for title, _ in items[:8])
    top_title, top_url = items[0]

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿戦略家です。
以下の最新AIニュースから最もインパクトのあるトピックを選び、
ビジネス層に刺さり爆発的に伸びるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{BUSINESS_ANGLE}
{TWEET_RULES}

追加ルール:
- 記事リンクをつける場合は文末に自然に入れる（URLは23文字換算）
- ニュースの内容に医療・社会変革・ビジネス視点を絡めること
- 少なくとも1案にはニュース元のリンクを含めること

{OUTPUT_FORMAT}

## 今日の最新AIニュース
{headlines_text}

参考リンク（最も注目のニュース）: {top_url}
"""
    raw = _call_claude(prompt)
    candidates = _parse_candidates(raw, source_url=top_url, source_title=top_title)
    return candidates


def _generate_original_insight() -> list[PostCandidate]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿戦略家です。
2026年のAI業界で最も重要なトレンドについて、
ビジネス層に刺さり爆発的に伸びるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{BUSINESS_ANGLE}
{TWEET_RULES}

優先テーマ: AI Agents・Claude/GPT最新動向・医療AI・AIと雇用・働き方改革

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _parse_candidates(raw)
