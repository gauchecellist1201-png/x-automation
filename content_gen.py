"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けにバズる投稿を生成
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass
from typing import Optional

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
URL_LENGTH = 23  # X上でのURL文字数換算
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- スイス大学研究経験、国連会議参加のグローバル視点
- 課題解決志向、静かに鋭い洞察を届けるスタイル
- Claude Codeなど最新AIツールを活用した医療プロダクト開発中
"""

BUSINESS_AUDIENCE = """
## ターゲット読者（ビジネス層）
- 30〜50代の経営者・管理職・ビジネスパーソン
- AI活用に関心があるが、技術的すぎる話は苦手
- 「使える情報」「ビジネスへの影響」「競合との差」を求めている
- 医療・ヘルスケア業界の意思決定者にも届けたい
"""

VIRAL_TWEET_FORMATS = """
## バズるAI投稿フォーマット（ビジネス層向け）

【フォーマット1: 数字インパクト】
例: 「ChatGPTの企業導入が1年で3倍。「検討中」の間に競合他社は先に進んでいる。 #AI」

【フォーマット2: 反直感の洞察】
例: 「AIは仕事を「奪う」のではなく「変える」——でも準備していない企業には同じ結果になる。 #生成AI」

【フォーマット3: 問いかけ（RTされやすい）】
例: 「3年後、AIを使いこなす医師と使いこなせない医師で診断精度に差が出る時代が来る。あなたは備えていますか？ #医療AI」

【フォーマット4: リスト系（続きを読ませる）】
例: 「2026年に医療AIが変える3つのこと↓\n①診断支援の精度が専門医を超える\n②電子カルテが自動要約される\n③新薬開発期間が半分になる #AI」

【フォーマット5: 速報+独自視点】
例: 「Googleが医療AI診断精度95%達成——数字より重要なのは、これが「AIが人間の仕事を代替し始めた」証拠だということ。 #生成AI」

【フォーマット6: Before/After対比】
例: 「AI導入前: 議事録作成に30分。AI導入後: 2分。この差が積み重なって1年後には競争力の差になる。 #AI」
"""

TWEET_STRATEGY = """
## 投稿戦略
1. 「知らなかった」「考えさせられた」と思わせる切り口
2. 専門的だが難解すぎない言葉選び（ビジネス層に届く）
3. 医療・社会変革・未来への問いかけを絡める
4. 具体的な数字や事例で信頼性を高める
5. 結論より「問い」で終わるとRTされやすい
6. ハッシュタグは #AI #生成AI のうち1〜2個まで
7. ニュースのURLをつける場合は文末に自然に入れる（X上で23文字換算）
"""


@dataclass
class NewsItem:
    title: str
    url: str
    source: str


def _call_claude(prompt: str, max_tokens: int = 1500) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_body_len: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数チェック"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+[\.\)]", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_body_len]


def fetch_rss_news(max_items: int = 10) -> list[NewsItem]:
    """RSSフィードからニュース記事（タイトル＋URL）を取得"""
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                source = getattr(feed.feed, "title", "")
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append(NewsItem(title=title, url=link, source=source))
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    has_url = bool(note_url)
    # URLあり: 本文は140-23-1=116文字以内
    max_body_len = (MAX_TWEET_LENGTH - URL_LENGTH - 1) if has_url else MAX_TWEET_LENGTH
    link_instruction = (
        f"\n- 本文は{max_body_len}文字以内（末尾に自動でNoteリンクが付く）"
        if has_url
        else f"\n- 各投稿は{MAX_TWEET_LENGTH}文字以内"
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:{link_instruction}
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、ビジネス層にも刺さる言葉で
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw, max_body_len=max_body_len)
    if has_url and tweets:
        return [f"{t} {note_url}" for t in tweets]
    return tweets


def generate_posts_from_rss() -> tuple[list[str], Optional[NewsItem]]:
    """最新AIニュースを元に、@GAUCHE_cellist らしい意見投稿を生成（URLも返す）"""
    news_items = fetch_rss_news()
    if not news_items:
        return _generate_original_ai_insight(), None

    headlines_text = "\n".join(
        f"{i+1}. {item.title} [{item.source}]"
        for i, item in enumerate(news_items)
    )
    # URLあり: 本文116文字以内
    max_body_len = MAX_TWEET_LENGTH - URL_LENGTH - 1

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:
- 本文は{max_body_len}文字以内（末尾に自動でニュース記事URLが付く）
- まず最初の行に「選択ニュース: [番号]」と出力してから投稿案を書く
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- 医療×AI、社会変革、ビジネス影響を絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)

    # 選択されたニュースを特定
    selected_item: Optional[NewsItem] = None
    for line in raw.splitlines():
        m = re.search(r"選択ニュース[:：]\s*(\d+)", line)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(news_items):
                selected_item = news_items[idx]
            break
    if selected_item is None and news_items:
        selected_item = news_items[0]

    tweets = _extract_tweets(raw, max_body_len=max_body_len)
    if tweets and selected_item:
        return [f"{t} {selected_item.url}" for t in tweets], selected_item
    if tweets:
        return tweets, None
    return _generate_original_ai_insight(), None


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- ビジネス層に刺さる具体的な洞察を
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def select_best_tweet(tweets: list[str]) -> str:
    """生成された投稿案からバズりやすい1つをClaudeが選択"""
    if not tweets:
        return ""
    if len(tweets) == 1:
        return tweets[0]

    candidates_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tweets))

    prompt = f"""以下のX(Twitter)投稿候補から、ビジネス層への拡散力が最も高いものを1つ選んでください。

選定基準（重要順）:
1. 「知らなかった」「考えさせられた」と感じさせる度合い
2. リツイート・引用したくなる動機の強さ
3. 専門性と読みやすさのバランス
4. 具体的な数字・問いかけ・対比の有無

投稿候補:
{candidates_text}

回答は「番号: [選んだ番号]」の形式で1行だけ出力してください。"""

    raw = _call_claude(prompt, max_tokens=50)
    m = re.search(r"番号[:：]\s*(\d+)", raw)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(tweets):
            return tweets[idx]
    return tweets[0]
