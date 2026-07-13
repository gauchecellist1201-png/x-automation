"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+エージェント&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI+AIエージェント&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

# X(Twitter)の文字数上限。日本語1文字=1カウント。URLは23文字換算。
MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層・ユーザー獲得最優先）

### 冒頭フック（最初の1文が命）
- 「AIの戦場が変わった」「〇〇が終わった」など転換点を示す
- 「知らなかった人は損してる」「これ見た瞬間ゾッとした」感のある驚き
- 具体的な数字から始める（例：「5% → 40%。たった1年で。」）

### 本文の型
- 具体的な数値・統計・固有名詞を必ず1つ入れる
- 反直感的な洞察（「モデルサイズ競争は終わった」等）
- 医療・社会変革・ビジネスへの実践的含意を絡める
- 短い文を重ねてリズムを作る（句読点で改行イメージ）

### 末尾パターン（どれかを選ぶ）
A. 問いかけ：「あなたの会社はどう動く？」→ RTされやすい
B. 宣言：「これが2026年のスタンダードになる」→ 保存されやすい
C. 逆張り：「まだ〇〇してる人は置いていかれる」→ 共感×危機感

### ハッシュタグ
- #AI #生成AI #AIエージェント のうち最大2個
- ビジネス系は #DX #医療AI も効果的
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
    """番号付きリストまたはブロック形式から投稿文を抽出してMAX_TWEET_LENGTH以内に絞る"""
    tweets: list[str] = []

    # パターン1: 番号付き（「1.」「1)」「【案1】」「案1:」形式）
    numbered = [
        re.sub(r"^\d+[\.\)]\s*|^【案\d+】\s*|^案\d+[:：]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\s*(\d+[\.\)]|【案\d+】|案\d+)", l.strip())
    ]
    tweets.extend(t for t in numbered if 0 < len(t) <= MAX_TWEET_LENGTH)

    # パターン2: 「---」区切りブロック形式のフォールバック
    if not tweets:
        blocks = re.split(r"-{3,}|\n{2,}", raw)
        for block in blocks:
            text = re.sub(r"^(案\d+|【.*?】|投稿\d+)[:：]?\s*", "", block.strip(), flags=re.MULTILINE)
            text = text.strip()
            if 10 < len(text) <= MAX_TWEET_LENGTH:
                tweets.append(text)

    return tweets[:NUM_CANDIDATES]


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
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で各案を出力
- ハッシュタグは1〜2個まで
- 冒頭の1文で読者を引き込む強いフックを必ず入れること
- 具体的な数字や企業名を使ってリアリティを出す
- AIに関するプロレベルの洞察を、ビジネスパーソンにも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}

重要: 出力は「1. [ツイート本文]」の形式で、各案を1行で書いてください。
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
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力し、各案は1行で書く
- 冒頭フックで「え、知らなかった」と思わせること
- 具体的な数字・社名・モデル名を必ず入れる
- 医療×AI、社会変革、ビジネス実践への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}

重要: 出力は「1. [ツイート本文]」の形式で、各案を1行で書いてください。
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力し、各案は1行で書く
- 冒頭フックで「え、知らなかった」と思わせること
- 具体的な数字・社名・モデル名を必ず入れる
- AIエージェント、Claude Sonnet 5、医療AI、AIと社会変革などのテーマを優先
- 2026年7月時点の最新トレンド（エージェントAIの台頭、コスト競争の終焉）を反映

重要: 出力は「1. [ツイート本文]」の形式で、各案を1行で書いてください。
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
