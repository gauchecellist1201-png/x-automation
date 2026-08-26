"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+医療AI+ビジネスAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+規制+EU+AI法+日本&hl=ja&gl=JP&ceid=JP:ja",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議参加のグローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- フォロワー：ビジネスパーソン、医療従事者、AI起業家
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（必ずいずれかを使う）
A. 「数字＋驚き」型：具体的な数字で読者の常識を揺さぶる
   例）「AIエージェントへの投資が7月だけで1.8兆円。1年前の10倍だ。」
B. 「逆張り洞察」型：みんなが見ている方向と逆を鋭く突く
   例）「AIの最大の壁は技術ではなく、ガバナンスだ。」
C. 「問い」型：答えを出さず、読者に考えさせる
   例）「医師の代わりにAIが診断する時代、責任は誰が取るのか。」
D. 「今起きている変化」型：リアルタイム感でRTを誘う
   例）「EU AI法が今月施行。AIとのやりとりで開示義務が生まれた。日本企業も無関係ではない。」
E. 「二項対立」型：AかBかで思考を二分割して反応を引き出す
   例）「AIは医師の敵か、それとも最強の相棒か。」
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略
1. 上記パターンA〜Eのいずれかを必ず使う
2. 「知らなかった」「考えさせられた」と思わせる切り口
3. 医療・ビジネス変革・規制・未来への問いかけを絡める
4. 文末を「問い」か「余韻のある一文」で締めるとRTされやすい
5. ハッシュタグは #AI #生成AI #医療AI のうち1個まで（必須ではない）
6. Noteリンクをつける場合は文末に自然に入れる
7. 絵文字は使わない（知性的な印象を保つ）
8. 「ですます」調より「だ・である」調が刺さりやすい
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_best_tweet(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1個まで（なくてもよい）
- AIに関するプロレベルの洞察を、ビジネス層・医療従事者にも刺さる言葉で{link_instruction}
- 3案それぞれ異なるパターン（A〜E）を使うこと
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


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

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、ビジネス変革、規制・未来への問いを絡めると尚良い
- ハッシュタグは1個まで（なくてもよい）
- 3案それぞれ異なるパターン（A〜E）を使うこと

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- AIエージェント、医療AI、EU AI法規制、ビジネス変革などのテーマを優先
- 3案それぞれ異なるパターン（A〜E）を使うこと
- ビジネス層・医療従事者に届く言葉で書く
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
