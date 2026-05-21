"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import json
import os
import re
from dataclasses import dataclass, field

import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+医療AI+ヘルスケア&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+automation+business+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学研究経験・国連会議参加のグローバル視点
- 専門知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_PATTERNS = """
## バズる投稿の型（ビジネス層向け AI × 実証済みパターン）

【型1: 数字フック】
「GPT-4oで業務時間が63%削減。でも本当の問題はそこじゃない。」
「AIに仕事を奪われる前に、AIで仕事を作れる人だけが生き残る。」

【型2: 逆説・反直感】
「AIが賢くなるほど、人間の"判断力"が価値を持つ。逆説に聞こえるが本当だ。」
「自動化が進むと、最後に残るのは"感情"を扱う仕事だった。」

【型3: Before/After 時代対比】
「2020年：コードが書けないと医療DXに関われなかった
2026年：医師がプロンプトだけでプロダクトを作る時代になった」

【型4: 鋭い問いかけ（拡散されやすい）】
「AIが診断の90%を担う病院で、医師は何をすべきか。
誰もまだ答えを持っていない。」

【型5: 独占情報・先行者感】
「まだあまり話題になっていないが、これはAI業界を根本から変えると思っている。」

【型6: データ引用 + 独自解釈】
「Nature誌：AIの診断精度が放射線科医を超えた。
でも患者が選ぶのは人間の医師。なぜか？」

【型7: リスト形式（スクリーンショットされやすい）】
「今週のAI動向で見落とせない3つ↓
①〇〇  ②〇〇  ③〇〇
ビジネスへの影響はこう読む。」

【型8: 体験ベースの共感】
「医学生として毎日感じること。
AIは医師を助けるのか、置き換えるのか。
答えより問いの方が重要かもしれない。」
"""

TWEET_STRATEGY = """
## 投稿戦略ルール
- ハッシュタグは #AI #生成AI #医療AI から最大1〜2個、文末に
- 改行を使って縦に読みやすく（スマホ表示を意識）
- 「。」より「。」+改行+短い問いで終わると拡散される
- 引用・データ → 自分の解釈 の構造が最も拡散される
- URLは文末に自然に配置（Twitterカードが立つ）
- 「考えさせられた」「知らなかった」「保存した」と思わせることが最優先
"""


@dataclass
class NewsItem:
    title: str
    url: str
    summary: str = ""


@dataclass
class PostCandidate:
    tweet: str
    source_url: str = ""
    source_title: str = ""
    hashtags: list[str] = field(default_factory=list)


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_tweet_response(raw: str) -> list[str]:
    """JSON 形式を優先してパース、失敗時は番号付きリストにフォールバック"""
    # JSON 配列を試みる
    json_match = re.search(r'\[[\s\S]*?\]', raw)
    if json_match:
        try:
            data = json.loads(json_match.group())
            tweets = []
            for item in data:
                if isinstance(item, str):
                    tweets.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("tweet", item.get("text", "")).strip()
                    if text:
                        tweets.append(text)
            if tweets:
                return [t for t in tweets if 10 < len(t) <= MAX_TWEET_LENGTH]
        except (json.JSONDecodeError, TypeError):
            pass

    # 番号付きブロックに分割（"1." や "1)" で始まる行を区切りとする）
    blocks = re.split(r'(?m)^(?=\d+[.\)][ \t])', raw.strip())
    tweets = []
    for block in blocks:
        text = re.sub(r'^\d+[.\)]\s*', '', block).strip()
        if text:
            tweets.append(text)

    return [t for t in tweets if 10 < len(t) <= MAX_TWEET_LENGTH]


def fetch_rss_news(max_items: int = 10) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:300]
                    items.append(NewsItem(title=title, url=url, summary=summary))
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[PostCandidate]:
    """Note記事 + 過去実績から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    url_instruction = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 改行を活用してスマホで読みやすく
- ハッシュタグは1〜2個まで{url_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}

## 出力形式
JSON配列で出力してください:
[
  "1つ目の投稿文（改行を含む場合は\\nを使用）",
  "2つ目の投稿文",
  "3つ目の投稿文"
]
"""
    raw = _call_claude(prompt)
    tweets = _parse_tweet_response(raw)
    return [PostCandidate(tweet=t, source_url=note_url) for t in tweets]


def generate_posts_from_rss() -> list[PostCandidate]:
    """最新AIニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    news_items = fetch_rss_news()
    if not news_items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(
        f"- {item.title}（{item.url}）" for item in news_items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 改行を活用してスマホで読みやすく
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 選んだ記事のURLを文末に含める（23文字換算）

## 今日の最新AIニュース
{headlines_text}

## 出力形式
まず選んだ記事URL（1行目）、次にJSON配列を出力:
SELECTED_URL: <選んだ記事のURL>
[
  "1つ目の投稿文（改行は\\nで表現）",
  "2つ目の投稿文",
  "3つ目の投稿文"
]
"""
    raw = _call_claude(prompt)

    # 選択した記事URLを抽出
    selected_url = ""
    url_match = re.search(r'SELECTED_URL:\s*(https?://\S+)', raw)
    if url_match:
        selected_url = url_match.group(1)
        # 対応する NewsItem を探す
    selected_title = next(
        (item.title for item in news_items if selected_url and item.url == selected_url),
        news_items[0].title if news_items else "",
    )

    tweets = _parse_tweet_response(raw)
    return [
        PostCandidate(tweet=t, source_url=selected_url, source_title=selected_title)
        for t in tweets
    ]


def _generate_original_ai_insight() -> list[PostCandidate]:
    """RSS が取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 改行を活用してスマホで読みやすく
- Claude、GPT、医療AI、AIと社会変革などを優先テーマとする
- ハッシュタグは1〜2個まで

## 出力形式
JSON配列で出力:
[
  "1つ目の投稿文",
  "2つ目の投稿文",
  "3つ目の投稿文"
]
"""
    raw = _call_claude(prompt)
    tweets = _parse_tweet_response(raw)
    return [PostCandidate(tweet=t) for t in tweets]
