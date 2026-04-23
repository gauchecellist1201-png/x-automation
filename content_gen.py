"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層・経営者・起業家
"""

import os
import re
import feedparser
import anthropic
from typing import TypedDict

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+企業DX+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AI最新動向
    "https://news.google.com/rss/search?q=AI+agent+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学研究経験、国連会議参加 → グローバル視点
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- ターゲット読者: ビジネス層・経営者・起業家・医療従事者
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（このいずれかを必ず使う）

1. 【逆張り・意外性】「〇〇だと思われているが、実は△△だ」
   例: AIは医師を代替しない。でも、AIを使えない医師は代替される。

2. 【数字で刺す】具体的な数字・コスト・時間・割合を入れる
   例: 医療診断AIの精度が専門医を超えた分野が、今や47領域。

3. 【FOMO（取り残される恐怖）】「今知らないと〇〇になる」
   例: 競合がAIを使い始めた今、意思決定のスピードで3倍の差がつく。

4. 【問いかけで終わる】読者に考えさせる問いで締める → RTされやすい
   例: AIが変えた。あなたのビジネスはまだ昨日のやり方？

5. 【未来予測・断言】5年後・10年後の具体的変化を断言する
   例: 2030年、医療診断の初期判断は99%AIが担う。医師の価値は共感力に移る。

6. 【before/after対比】AIがある世界とない世界を対比させる
   例: 昔：論文1本読むのに3時間 → 今：AIが要約して3分。この3時間で何をするか。

7. 【業界の不都合な真実】タブーや暗黙の了解に切り込む
   例: 医師が電子カルテに費やす時間は1日平均2時間。これ、AIが全部やれる。
"""

TWEET_STRATEGY = """
## 投稿戦略
- ビジネス層への訴求: ROI・競争優位・生産性向上を絡める
- 医療×AI: 具体的な変革事例で拡散されやすい
- ハッシュタグ: #AI #生成AI #医療AI のうち1〜2個
- URLリンク: 文末に自然に配置（文字数は23文字換算）
- 感嘆符（！）は1投稿に最大1つまで
"""

OUTPUT_FORMAT = """
## 出力形式（必ずこの形式で）
---投稿案1---
本文: [140文字以内の投稿本文]
パターン: [使用したバズパターン名]
スコア: [バイラル予測スコア 1〜10の整数]
画像: [添付すると効果的な画像の説明（Midjourney/DALL-E風に）]
---投稿案2---
本文: ...
パターン: ...
スコア: ...
画像: ...
---投稿案3---
本文: ...
パターン: ...
スコア: ...
画像: ...
"""


class TweetCandidate(TypedDict):
    text: str
    pattern: str
    virality_score: int
    image_prompt: str


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_candidates(raw: str) -> list[TweetCandidate]:
    """区切り形式の出力からTweetCandidateリストを抽出する"""
    candidates: list[TweetCandidate] = []
    blocks = re.split(r"---投稿案\d+---", raw)
    for block in blocks:
        text_match = re.search(r"本文[：:]\s*(.+?)(?=\nパターン|\nスコア|\n画像|$)", block, re.DOTALL)
        pattern_match = re.search(r"パターン[：:]\s*(.+?)(?=\n|$)", block)
        score_match = re.search(r"スコア[：:]\s*(\d+)", block)
        image_match = re.search(r"画像[：:]\s*(.+?)(?=\n|$)", block)
        if not text_match:
            continue
        text = text_match.group(1).strip()
        if not (0 < len(text) <= MAX_TWEET_LENGTH):
            continue
        candidates.append(TweetCandidate(
            text=text,
            pattern=pattern_match.group(1).strip() if pattern_match else "",
            virality_score=min(10, max(1, int(score_match.group(1)))) if score_match else 5,
            image_prompt=image_match.group(1).strip() if image_match else "",
        ))
    # フォールバック: シンプルな番号付きリスト抽出
    if not candidates:
        for line in raw.splitlines():
            line = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if 0 < len(line) <= MAX_TWEET_LENGTH:
                candidates.append(TweetCandidate(text=line, pattern="", virality_score=5, image_prompt=""))
    return candidates[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[TweetCandidate]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
{OUTPUT_FORMAT}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_candidates(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    items: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "link": link})
        except Exception:
            continue
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> list[TweetCandidate]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- ハッシュタグは1〜2個まで
- 医療×AI、社会変革、ビジネスインパクトを絡めると尚良い

{OUTPUT_FORMAT}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _parse_candidates(raw)


def generate_thread(topic: str, note_url: str = "") -> list[str]:
    """スレッド形式の投稿を生成（フック→本論→CTA の4ツイート構成）"""
    link_line = f"詳細: {note_url}" if note_url else "フォローで最新AI情報をお届けします。"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のテーマについて、Xスレッド形式の投稿を作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

テーマ: {topic}

スレッド構成（全4ツイート、各140文字以内）:
1. フックツイート: 最もバズる冒頭。問いか驚き。「🧵スレッドで解説」と入れる。
2. 本論1: 具体的な事例・データ・医療への応用。
3. 本論2: ビジネスへのインパクト・経営者がとるべきアクション。
4. 締め: 読者への問いかけ + {link_line}

番号付きリスト（1. 2. 3. 4.）で出力してください。各ツイートは140文字以内。
"""
    raw = _call_claude(prompt)
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH][:4]


def _generate_original_ai_insight() -> list[TweetCandidate]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

優先テーマ: Claude 4 / GPT-5 / AIエージェント / 医療AI / AIと雇用 / AI規制

{OUTPUT_FORMAT}
"""
    raw = _call_claude(prompt)
    return _parse_candidates(raw)
