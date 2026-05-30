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
    "https://news.google.com/rss/search?q=AI+ビジネス+業務効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門知識を持ちながら読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_TWEET_STRATEGY = """
## ビジネス層に刺さるバズりAI投稿の法則

### フォーマット（いずれか1つを選ぶ）
1. 【衝撃データ型】数字で驚かせる → 「〇〇社がAI導入で工数70%削減」
2. 【逆説・反直感型】常識を崩す → 「AIが普及するほど、〇〇力が重要になる逆説」
3. 【問いかけ型】問いで終わる → 「AIに奪われる仕事より、AIを使いこなせない人の方が怖くないか？」
4. 【比較・対比型】明確な構造 → 「AIを道具として使う人 vs AIに使われる人」
5. 【予測・警告型】未来を示す → 「2年後、これを知らないビジネスパーソンは苦労する」
6. 【体験・事実型】具体性で信頼 → 「Claude Codeで〇〇を1時間で実装した」
7. 【ニュースコメント型】最新情報+独自視点

### 共通ルール
- 冒頭1行で掴む（読まれるか否かはここで決まる）
- 専門的だが難解すぎない言葉選び
- 医療・社会変革・未来への視点を自然に絡める
- 結論より「問い」で終わるとRTされやすい
- ハッシュタグは #AI #生成AI のうち1〜2個まで
- 絵文字は1〜2個まで（使いすぎない）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出する。複数行にまたがるケースも対応。"""
    tweets: list[str] = []
    current: list[str] = []

    for line in raw.splitlines():
        if re.match(r"^\d+[\.\)]\s+", line.strip()):
            if current:
                tweet = " ".join(current).strip()
                if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current = [re.sub(r"^\d+[\.\)]\s*", "", line.strip())]
        elif current and line.strip():
            current.append(line.strip())

    if current:
        tweet = " ".join(current).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets


def select_best_post(posts: list[str]) -> str:
    """Claude にバズり可能性が最も高い投稿を1つ選ばせる。"""
    if len(posts) == 1:
        return posts[0]

    candidates = "\n".join(f"{i+1}. {p}" for i, p in enumerate(posts))
    prompt = f"""以下のX投稿候補の中から、ビジネス層に最もバズりやすい1つを選んでください。
選んだ番号だけを答えてください（例: 2）。

{candidates}"""
    raw = _call_claude(prompt).strip()
    match = re.search(r"\d", raw)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(posts):
            return posts[idx]
    return posts[0]


def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
    viral_examples: list[str] | None = None,
) -> list[str]:
    """Note記事 + バズり事例 + 過去実績 から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    viral_section = ""
    if viral_examples:
        viral_section = (
            "\n## 今バズっているAIツイート（このパターンを参考に）\n"
            + "\n".join(f"- {t[:100]}" for t in viral_examples[:3])
            + "\n"
        )

    link_instruction = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力（1投稿=1行）
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}{viral_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 8) -> list[dict]:
    """RSSフィードから最新AIニュースのタイトルとURLを取得"""
    items: list[dict] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_rss(viral_examples: list[str] | None = None) -> tuple[list[str], str]:
    """最新AIニュースを元に投稿案を生成。最もバズりそうなニュースのURLも返す。"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight(viral_examples), ""

    headlines_text = "\n".join(f"- {i['title']}" for i in items)
    top_url = items[0]["url"] if items else ""

    viral_section = ""
    if viral_examples:
        viral_section = (
            "\n## 今バズっているAIツイート（このパターンを参考に）\n"
            + "\n".join(f"- {t[:100]}" for t in viral_examples[:3])
            + "\n"
        )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力（1投稿=1行）
- ハッシュタグは1〜2個まで
- 医療×AI、社会変革、ビジネス変革の視点を絡める
{viral_section}
## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    return posts, top_url


def _generate_original_ai_insight(viral_examples: list[str] | None = None) -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    viral_section = ""
    if viral_examples:
        viral_section = (
            "\n## 今バズっているAIツイート（このパターンを参考に）\n"
            + "\n".join(f"- {t[:100]}" for t in viral_examples[:3])
            + "\n"
        )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さる洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力（1投稿=1行）
- Claude、GPT-5、医療AI、AIとビジネス変革などのテーマを優先
{viral_section}"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
