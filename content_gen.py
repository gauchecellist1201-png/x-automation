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
    "https://news.google.com/rss/search?q=AI+business+enterprise+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_TWEET_STRATEGY = """
## バズるAIビジネス投稿の戦略（ビジネス層ユーザー獲得重視）

### 構造パターン（どれか1つを選ぶ）
A) 【数字フック型】「〇〇が△△%増加」→ 驚きの事実 → ビジネス示唆
B) 【逆説型】「〇〇は間違い」「実は△△」→ 意外な真実 → 洞察
C) 【問い型】深い問いを投げかけ → 短い考察 → 読者に考えさせる
D) 【未来予測型】「2026年、〇〇が変わる」→ 具体例 → 行動示唆
E) 【格言型】鋭い一文 → 根拠 → 問い

### バズ要素チェックリスト
- 冒頭3文字でスクロールを止める（数字・カギカッコ・感嘆符など）
- ビジネス層が「これは知らなかった」と感じる情報格差
- 医療×AI、社会変革、意思決定の変化テーマ
- 読んだ人が「引用RTしたくなる」洞察
- ハッシュタグは #AI #生成AI のうち1個のみ（スペース節約）

### 避けるもの
- 「〇〇がすごい」という単純な称賛
- ポジティブすぎる未来予測
- 専門用語の羅列
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def _select_best_tweet(tweets: list[str]) -> str | None:
    """Claude に最もバズりそうな投稿を1本選ばせる"""
    if not tweets:
        return None
    if len(tweets) == 1:
        return tweets[0]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tweets))
    prompt = f"""以下のX投稿候補から、ビジネス層への拡散力が最も高い1つを選んでください。
選んだ番号のみ（数字1文字）を返してください。

{numbered}"""
    raw = _call_claude(prompt).strip()
    match = re.search(r"\d", raw)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(tweets):
            return tweets[idx]
    return tweets[0]


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
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1個まで
- ビジネス層が思わず保存・RTしたくなる洞察{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
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
ビジネス層に刺さる洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- ビジネス経営者・投資家・医療関係者が「保存したくなる」内容
- ハッシュタグは1個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層が思わず保存・RTしたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 自律型AIエージェント、医療AI、AIと雇用、企業のAI内製化などを優先テーマに
- ハッシュタグは1個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def pick_best_post(posts: list[str]) -> str | None:
    """候補投稿の中からバズ期待度が最高の1本を返す"""
    return _select_best_tweet(posts)
