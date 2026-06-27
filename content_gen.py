"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+business+enterprise+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

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

VIRAL_FORMULAS = """
## バズるビジネス層向けAI投稿の公式（いずれかを使う）

【公式A：逆説・反常識】
「みんな○○と思ってるけど、実は△△」
例：「AIが仕事を奪うと思われてるが、実際に消えるのは○○という『思考の省エネ』だ」

【公式B：衝撃の数字】
具体的な数字から始まる。「40%」「3倍」「年間800時間」など
例：「CEOの67%が今年AIエージェントを導入予定——しかし成果を出せるのは準備した企業だけ」

【公式C：リスト形式フック】
「○○な人が知らない3つのこと」「2026年、勝つ企業と負ける企業の違い」

【公式D：問いかけ】
「あなたの会社のAI導入、誰が責任者ですか？」という具体的な問い。RTしやすい。

【公式E：タイムリーな洞察】
速報性のある情報に「これが意味すること」を付け加える。
例：「Claudeが○○を発表——医療現場で最初に使われるのは××という分野だと思う」

【公式F：ストーリーフック】
「医学生の私が、AIを使って○○時間節約した話」
"""

TWEET_STRATEGY = """
## 投稿戦略
- ビジネス層（経営者・医師・起業家・マネージャー）が「これは知っておかないと」と感じる内容
- 難解すぎず、でも表面的でもない——「こういう見方があるのか」と気づかせる
- ハッシュタグは #AI または #生成AI を1〜2個のみ
- URLリンクを貼る場合は文末に。URLは23文字換算なので260文字以内に本文を収める
- 絵文字は使いすぎない（1〜2個まで）
"""


@dataclass
class NewsItem:
    title: str
    link: str
    image_url: str | None = None


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出。空行区切りのブロックも対応"""
    results = []
    # 番号付きリスト（1. 2. 3.）
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^\d+[\.\)]\s*(.+)", line)
        if m:
            tweet = m.group(1).strip()
            if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                results.append(tweet)
    return results


def fetch_rss_headlines(max_items: int = 10) -> list[NewsItem]:
    """RSS各フィードからタイトル・リンク・画像を収集して重複除去"""
    items: list[NewsItem] = []
    seen: set[str] = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                if not title or len(title) < 10:
                    continue
                if title in seen:
                    continue
                seen.add(title)

                link = entry.get("link", "")

                # OG画像を探す（media_thumbnail, enclosure, media_content）
                image_url: str | None = None
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if "image" in enc.get("type", ""):
                            image_url = enc.get("href")
                            break

                items.append(NewsItem(title=title, link=link, image_url=image_url))
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line
            for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"
            )

    link_instruction = (
        f"\n- 文末にNoteリンクを入れる: {note_url}（URLは23文字換算）"
        if note_url
        else ""
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{TWEET_STRATEGY}

ルール:
- 各投稿は260文字以内（URLを貼る場合、URLは23文字換算なので本文は237文字以内）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- バズる公式のいずれかを使いビジネス層に刺さる内容に{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss(
    news_items: list[NewsItem] | None = None,
) -> tuple[list[str], NewsItem | None]:
    """
    最新AIニュースを元に投稿案を生成。
    最も注目度の高いニュースを1件選んでそのリンクを投稿に含める。
    Returns: (投稿案リスト, 使用したNewsItem)
    """
    if news_items is None:
        news_items = fetch_rss_headlines()

    if not news_items:
        posts = _generate_original_ai_insight()
        return posts, None

    headlines_text = "\n".join(
        f"- {item.title}（{item.link}）" for item in news_items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから、ビジネス層に最も刺さりそうなトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{TWEET_STRATEGY}

ルール:
- 各投稿は237文字以内（末尾にリンクを付けるため）
- 番号付きリスト（1. 2. 3.）で出力
- 選んだ記事のURLを文末に付ける（「詳細→ URL」形式）
- 医療×AI、社会変革、ビジネス変革の視点を絡める
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース（タイトル、URL）
{headlines_text}

最後に、選んだ記事のURLを「SELECTED_URL: <url>」の形式で1行で出力してください。
"""
    raw = _call_claude(prompt)

    # 選択されたURLを抽出
    selected_url_match = re.search(r"SELECTED_URL:\s*(https?://\S+)", raw)
    selected_url = selected_url_match.group(1) if selected_url_match else None

    # 使用したNewsItemを特定
    selected_item: NewsItem | None = None
    if selected_url:
        for item in news_items:
            if item.link and item.link in raw:
                selected_item = item
                break
        if not selected_item and news_items:
            selected_item = news_items[0]

    posts = _extract_tweets(raw)

    # URLがまだ含まれていない投稿にURLを追加
    if selected_item and selected_item.link:
        enriched = []
        for post in posts:
            if "http" not in post:
                candidate = f"{post}\n{selected_item.link}"
                if len(candidate) <= MAX_TWEET_LENGTH + 23:
                    enriched.append(candidate)
                else:
                    enriched.append(post)
            else:
                enriched.append(post)
        posts = enriched

    return posts, selected_item


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層（経営者・医師・起業家）に刺さる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、医療AI、AIと経営変革などのテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def select_best_post(posts: list[str]) -> str:
    """複数の候補から最もバズりそうな1件をClaudeが選ぶ"""
    if not posts:
        return ""
    if len(posts) == 1:
        return posts[0]

    candidates = "\n".join(f"{i+1}. {p}" for i, p in enumerate(posts))
    prompt = f"""以下のX投稿候補の中から、ビジネス層への拡散力が最も高い1案を選んでください。
選んだ番号だけを答えてください（例: 2）。

{candidates}"""
    raw = _call_claude(prompt).strip()
    m = re.search(r"\d+", raw)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(posts):
            return posts[idx]
    return posts[0]
