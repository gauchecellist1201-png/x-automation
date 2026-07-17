"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+ChatGPT&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=artificial+intelligence+business+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加、グローバル視点
- 課題解決志向、専門的知識を持ちながら読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- 2026年時点でClaude Codeなど最新AIツールを実務で活用中
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）

【バズりやすいパターン】
A) 驚き型: 「〇〇なAIが出た」「誰も教えてくれなかった〇〇」
B) 問い型: 「あなたは〇〇を知っているか？」「〇〇は本当に必要か？」
C) 数字型: 「〇〇を使う人が3倍に」「○%の企業が...」
D) 逆説型: 「AIが進化するほど、〇〇の価値が上がる」
E) 未来型: 「5年後に〇〇職は消えているかもしれない。でも〇〇は残る」
F) 実体験型: 「実際にClaude Codeを使ってみたら〇〇だった」

【共通ルール】
1. 最初の一文でスクロールを止める強いフック
2. ビジネスパーソンが「使えるネタ」と感じる情報密度
3. 医療・社会変革・未来への洞察を自然に絡める
4. 結論より「問い」で終わるとRTされやすい
5. ハッシュタグは #AI #生成AI #医療AI のうち1〜2個まで
6. URLは文末に自然に入れる（23文字換算）
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
    results = []
    for line in raw.splitlines():
        line = line.strip()
        if not re.match(r"^\d+[\.\)]\s*", line):
            continue
        tweet = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        # 引用符・括弧を除去
        tweet = tweet.strip('"\'「」')
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            results.append(tweet)
    return results


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層がバズらせたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。それ以外の説明文は不要
- ハッシュタグは1〜2個まで{link_instruction}
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
                # Google Newsの "- メディア名" 部分を除去
                title = re.sub(r"\s*-\s*[^\-]+$", "", title).strip()
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
ビジネス層に刺さりバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。それ以外の説明文は不要
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- どのパターン（A〜F）を使ったかは書かなくてよい

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層がバズらせたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。それ以外の説明文は不要
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
