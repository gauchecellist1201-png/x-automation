"""
Claude API を使った戦略的投稿文生成モジュール
ターゲット: ビジネス層（経営者・マネージャー・DX担当）へのAI情報発信
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    ("https://news.google.com/rss/search?q=AI+活用+ビジネス+DX+生産性&hl=ja&gl=JP&ceid=JP:ja", "ja"),
    ("https://news.google.com/rss/search?q=生成AI+LLM+企業+導入+2026&hl=ja&gl=JP&ceid=JP:ja", "ja"),
    ("https://news.google.com/rss/search?q=AI+productivity+business+ROI+2026&hl=en&gl=US&ceid=US:en", "en"),
    ("https://feeds.feedburner.com/ledge-ai", "ja"),
    ("https://techcrunch.com/feed/", "en"),
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合を追求、グローバル視点
- ビジネス層にAIの本質的価値を伝えることに注力
- 深い洞察を、誰もが理解できる言葉で届けるスタイル
"""

BUSINESS_TWEET_STRATEGY = """
## ビジネス層向けバズAI投稿戦略

### ターゲット読者
- 経営者、役員、マネージャー、DX推進担当者
- AI活用の意思決定者・情報収集層
- 生産性向上・競合優位性を追求するビジネスパーソン

### バズる投稿の型（必ずどれかを使う）
1. 数字インパクト型：「〇〇社がAI導入でコスト40%削減」「週10時間→30分に」
2. 逆説・意外性型：「AIを使わないことが最大のリスクになっている」
3. 問いかけ型：「あなたの会社はAIを〇〇に使えていますか？」（RTされやすい）
4. リスト型：「今すぐ使えるAI活用法3選 👇」（保存・シェアされやすい）
5. ストーリー型：「月100時間の作業が3時間に。変えたのは〇〇だった」
6. 予言・警告型：「2026年末、AI非対応の〇〇企業は〜になる」

### 必須要素
- 冒頭15文字で読者を掴む強いフック（ここで勝負が決まる）
- 具体的な数字・企業名・事例を入れる（抽象論より3倍伸びる）
- 行動を促すCTA（保存して/RTして/あなたの場合は？）
- ハッシュタグ: #AI #生成AI #DX のうち1〜2個のみ

### 禁止事項
- 「AIは重要です」「未来が変わります」などの抽象的表現
- 過度に詩的・感動的な表現（ビジネス層には刺さらない）
- ハッシュタグの多用（3個以上はリーチを下げる）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出（複数行ブロック対応）"""
    posts: list[str] = []
    current_lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_lines:
                post = " ".join(current_lines).strip()
                if 10 < len(post) <= MAX_TWEET_LENGTH:
                    posts.append(post)
            current_lines = [re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()]
        elif stripped and current_lines:
            current_lines.append(stripped)

    if current_lines:
        post = " ".join(current_lines).strip()
        if 10 < len(post) <= MAX_TWEET_LENGTH:
            posts.append(post)

    return posts[:NUM_CANDIDATES]


def _format_viral_examples(viral_tweets: list) -> str:
    """バズツイートをプロンプト用テキストに整形"""
    if not viral_tweets:
        return ""
    lines = ["\n## 参考：今バズっているAI投稿の実例（エンゲージメント順）"]
    for i, t in enumerate(viral_tweets[:5], 1):
        score = getattr(t, "engagement_score", 0)
        text = getattr(t, "text", str(t))
        # 長すぎるツイートは省略
        display = text[:120] + "…" if len(text) > 120 else text
        lines.append(f"{i}. [{score}pt] {display}")
    lines.append("\n→ 上記のフック・構造・トーンを参考に、オリジナルの内容で作成してください。")
    return "\n".join(lines)


def fetch_rss_news(max_items: int = 8) -> list[dict]:
    """RSSから最新AIニュース（タイトル + URL）を取得"""
    items: list[dict] = []
    for url, lang in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "url": link, "lang": lang})
        except Exception:
            continue
    # 重複除去（タイトル先頭30文字で判定）
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
    viral_tweets: list | None = None,
) -> list[str]:
    """Note記事 + バズパターン + 過去実績からビジネス層向け投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    viral_section = _format_viral_examples(viral_tweets) if viral_tweets else ""
    link_note = f"\n- URLを含める場合: {note_url}（URLは23文字換算）" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）のバイラルコンテンツ担当AIです。
以下のNote記事を読み、ビジネス層に最もリーチするX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）{link_note}
- 番号付きリスト（1. 2. 3.）で出力。1投稿1行
- ハッシュタグは1〜2個まで
{viral_section}
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def generate_posts_from_rss(
    viral_tweets: list | None = None,
    news_items: list[dict] | None = None,
) -> list[str]:
    """最新AIニュース + バズパターンからビジネス層向け投稿を生成"""
    if news_items is None:
        news_items = fetch_rss_news()
    if not news_items:
        return _generate_original_ai_insight(viral_tweets)

    # 日本語ニュースを優先、なければ英語
    ja_items = [i for i in news_items if i["lang"] == "ja"]
    display_items = (ja_items or news_items)[:6]

    news_text = "\n".join(
        f"- {item['title']} | {item['url']}" for item in display_items
    )
    viral_section = _format_viral_examples(viral_tweets) if viral_tweets else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）のバイラルコンテンツ担当AIです。
以下の最新AIニュースから最もビジネスインパクトが大きいトピックを1つ選び、
意思決定者・ビジネスパーソンに最もリーチするX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。1投稿1行
- 関連ニュースのURL（上記の「|」以降）を文末に自然に含めること（拡散率向上）
- ハッシュタグは1〜2個まで
{viral_section}

## 今日の最新AIニュース（タイトル | URL）
{news_text}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def _generate_original_ai_insight(viral_tweets: list | None = None) -> list[str]:
    """ニュース取得失敗時のオリジナル洞察投稿生成"""
    viral_section = _format_viral_examples(viral_tweets) if viral_tweets else ""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）のバイラルコンテンツ担当AIです。
2026年のAI業界で最も重要なビジネストピックについて、
経営者・DX担当者の心を掴むX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力。1投稿1行
- ハッシュタグは1〜2個まで
{viral_section}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)
