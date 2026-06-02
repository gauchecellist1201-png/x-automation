"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層・経営者・スタートアップ関係者
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ChatGPT&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+経営+ビジネス+自動化&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語 AI ニュース（信頼性高・速報性あり）
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/ai/feed/",
]

MAX_TWEET_LENGTH = 280
# URL は Twitter 上で23文字換算
URL_CHAR_COUNT = 23
NUM_CANDIDATES = 3

TWEET_DELIMITER = "<<<TWEET>>>"
TWEET_END = "<<<END>>>"

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合を追求
- スイスでの研究経験・国連会議参加のグローバル視点
- 専門的知識を持ちながら、静かに鋭い洞察を届けるスタイル
- 押しつけがましくなく、読者に考えさせる問いを投げかける
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（ビジネス層向け・実証済み）
1. 【衝撃の数字冒頭】「〇〇%の企業が〜」「〇兆円市場が〜」で始まる
2. 【FOMO訴求】「今対応しないと差がつく」「先行者優位は今年中」
3. 【問題提起型】「あなたの会社はまだ〇〇ですか？」
4. 【箇条書きリスト】改行+「•」や「①②③」で読みやすく
5. 【対比・変化型】「〇ヶ月前→今：〇〇が〇分→〇秒に変わった」
6. 【問いで締める】「〜だと思いませんか？」「あなたはどう思いますか？」
7. 【速報性フレーム】「【速報】」「今日から〜」を冒頭に
8. 【改行を多用】スマホで読みやすく、1文ごとに改行
"""

BUSINESS_HOOKS = """
## ビジネス層に刺さる切り口
- コスト削減・ROI・生産性向上の具体数字
- 「経営者が知るべき〇点」「CxOが注目する〜」
- 競合他社との差別化・先行者優位
- リスク・規制・コンプライアンスへの影響
- 実際の導入事例・成功事例への言及
- 医療×AI など専門分野からの独自視点
"""

TWEET_RULES = f"""
## 出力ルール（厳守）
- 各投稿は {TWEET_DELIMITER} で始まり {TWEET_END} で終わること
- 文字数は最大{MAX_TWEET_LENGTH}文字（URLを含む場合はURL={URL_CHAR_COUNT}文字換算）
- 改行を多用してスマホで読みやすく
- ハッシュタグは #AI #生成AI #経営AI のうち1〜2個まで、文末に置く
- 絵文字は1〜2個まで、多用しない
- 出力は投稿文のみ（解説や前置きは不要）
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


def _extract_tweets(raw: str) -> list[str]:
    """<<<TWEET>>>...<<<END>>> 区切りでツイートを抽出する。フォールバックあり。"""
    pattern = rf"{re.escape(TWEET_DELIMITER)}(.*?){re.escape(TWEET_END)}"
    matches = re.findall(pattern, raw, re.DOTALL)
    if matches:
        result = []
        for m in matches:
            tweet = m.strip()
            # URL含む場合の文字数推定（URLは23文字換算）
            text_without_url = re.sub(r"https?://\S+", "", tweet)
            url_count = len(re.findall(r"https?://\S+", tweet))
            estimated_len = len(text_without_url.replace(" ", "")) + url_count * URL_CHAR_COUNT
            if tweet and estimated_len <= MAX_TWEET_LENGTH:
                result.append(tweet)
        if result:
            return result

    # フォールバック：番号付きリスト（1行）
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+[\.\)]", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def fetch_rss_news(max_items: int = 8) -> list[NewsItem]:
    """RSS フィードから最新 AI ニュースを取得する。"""
    seen_titles: set[str] = set()
    items: list[NewsItem] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()[:200]
                if not title or len(title) < 10:
                    continue
                # Google News の重複タイトルを除去
                key = title[:30]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                items.append(NewsItem(title=title, url=link, summary=summary))
                if len(items) >= max_items:
                    return items
        except Exception:
            continue

    return items


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note 記事 + 過去実績 (few-shot) から戦略的投稿案を生成する。"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を踏襲）\n{examples}\n"

    url_note = f"\n- 文末にNoteリンクを自然に組み込む: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層・経営者・スタートアップ関係者に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_HOOKS}
{TWEET_RULES}
{url_note}
{few_shot}
## Note記事本文
{note_text[:4000]}

{NUM_CANDIDATES}案を必ず {TWEET_DELIMITER}〜{TWEET_END} で囲んで出力してください。
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新 AI ニュースから投稿案を生成する。選んだ記事の URL も返す。"""
    news_items = fetch_rss_news()
    if not news_items:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(
        f"- {item.title}（{item.url}）" for item in news_items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースの中から「最もビジネス層にインパクトある」トピックを1つ選び、
その記事URLを文末に含めたX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_HOOKS}
{TWEET_RULES}
- 選んだ記事のURLを文末に「詳細→ [URL]」の形で必ず入れること

## 今日の最新AIニュース（タイトル + URL）
{headlines_text}

{NUM_CANDIDATES}案を必ず {TWEET_DELIMITER}〜{TWEET_END} で囲んで出力してください。
選んだ記事URLを各案の文末に入れること。
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)

    # 選ばれた記事URLを抽出（ログ用）
    selected_url = ""
    for item in news_items:
        if any(item.url in t for t in tweets):
            selected_url = item.url
            break

    return tweets, selected_url


def _generate_original_ai_insight() -> list[str]:
    """RSS 取得不可時のオリジナル洞察投稿を生成する。"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年の AI 業界で最も重要なトピックについて、
ビジネス層・経営者に刺さる洞察投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_HOOKS}
{TWEET_RULES}

テーマ例：Claude/GPT の最新動向・医療AI・AI経営戦略・生成AI規制・AI採用

{NUM_CANDIDATES}案を必ず {TWEET_DELIMITER}〜{TWEET_END} で囲んで出力してください。
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
