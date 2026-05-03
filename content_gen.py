"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AI・テック
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AI（グローバルトレンド）
    "https://news.google.com/rss/search?q=artificial+intelligence+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+business+enterprise&hl=en&gl=US&ceid=US:en",
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求、スイス研究・国連会議参加経験
- Claude Codeなど最新AIツールを実務活用中
- 課題解決志向のグローバル視点、専門知識を平易な言葉で届ける
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

VIRAL_TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）

### バズる構造パターン
1. 【衝撃事実型】「〇〇が〇〇に。これが意味することは──」→ 現状認識を揺さぶる
2. 【数字インパクト型】「3ヶ月で〇〇が〇倍に」「知らないと損する5つの変化」
3. 【問いかけ型】読者が「自分ごと」として考えるような問いで締める
4. 【逆説型】「AIは仕事を奪わない。ただし──」→ 裏切りで続きを読ませる
5. 【解説先出し型】「結論: ○○。理由は3つ──」→ 価値を先に見せる

### ビジネス層が反応するテーマ
- 生産性・コスト削減の具体数値
- 競合他社・業界への影響
- 医療・ヘルスケア × AI（差別化軸）
- 経営判断に直結するAIトレンド
- 「今すぐ使える」実践的インサイト

### 投稿スタイルルール
- 冒頭1文で掴む（スクロールを止める）
- 専門的だが難解すぎない言葉選び
- ハッシュタグは #AI #生成AI のうち1〜2個まで
- 問いか「──」の余韻で終わるとRTされやすい
- スレッド案（1/3など）も1案含める
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=(
            "あなたはSNSマーケティングの専門家であり、"
            "@GAUCHE_cellist（井出直毅）のX投稿担当AIです。"
            "ビジネス層・経営者層に刺さる、バズりやすい投稿を作成することが得意です。"
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出"""
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        # 番号付き行を抽出
        if re.match(r"^\d+[\.\)【]", stripped):
            text = re.sub(r"^\d+[\.\)【]\s*", "", stripped).strip()
            # 【案X】形式も除去
            text = re.sub(r"^【.*?】\s*", "", text).strip()
            if text and len(text) <= MAX_TWEET_LENGTH:
                lines.append(text)
        # インデントされた続き行（スレッド案など）
        elif lines and stripped and not stripped.startswith("#") and len(stripped) > 10:
            # 前の行と結合する候補か確認（スレッド形式は別管理）
            pass
    return lines[:NUM_CANDIDATES] if lines else []


def _extract_tweets_flexible(raw: str) -> list[str]:
    """より柔軟に投稿文を抽出（140文字超えも候補として保持）"""
    results = []
    current = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                text = " ".join(current).strip()
                if 10 < len(text):
                    results.append(text[:280])  # 280文字まで許容（スレッド考慮）
                current = []
            continue

        if re.match(r"^\d+[\.\)]\s*", stripped):
            if current:
                text = " ".join(current).strip()
                if 10 < len(text):
                    results.append(text[:280])
                current = []
            text = re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()
            if text:
                current.append(text)
        elif current:
            current.append(stripped)

    if current:
        text = " ".join(current).strip()
        if 10 < len(text):
            results.append(text[:280])

    # 140文字以内を優先、超える場合は切り詰めて返す
    final = []
    for t in results[:NUM_CANDIDATES]:
        if len(t) <= MAX_TWEET_LENGTH:
            final.append(t)
        else:
            # 末尾に「…」を付けて収める
            final.append(t[:138] + "…")
    return final


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            ln for ln in feedback_text.splitlines()
            if ln.strip() and not ln.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""

    prompt = f"""以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで（#AI #生成AI #医療AI のいずれか）
- 1案はスレッド形式（「1/3」など）にして続きへの期待を持たせる
- ビジネス層・経営者が「これは使える」と感じる内容にする{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets_flexible(raw)
    return tweets if tweets else _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから最新ニュースを取得（タイトル＋リンク）"""
    items: list[dict] = []
    seen: set[str] = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue
        if len(items) >= max_items:
            break

    return items[:max_items]


def generate_posts_from_rss() -> list[dict]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成

    Returns:
        list of dicts with keys: tweet, source_title, source_link
    """
    news_items = fetch_rss_headlines()

    if not news_items:
        tweets = _generate_original_ai_insight()
        return [{"tweet": t, "source_title": "", "source_link": ""} for t in tweets]

    headlines_text = "\n".join(
        f"- [{item['title']}]({item['link']})" if item.get("link") else f"- {item['title']}"
        for item in news_items
    )

    prompt = f"""以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、ビジネス変革、未来への問いを絡める
- ハッシュタグは1〜2個まで
- 1案はスレッド形式（「1/3」など）にする
- どのニュースを元にしたか、番号付きリストの前に「📰 参照: [ニュースタイトル]」と1行書く

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)

    # 参照ニュースを抽出
    source_title = ""
    source_link = ""
    for line in raw.splitlines():
        if "📰 参照:" in line or "参照:" in line:
            ref_text = re.sub(r".*参照:\s*", "", line).strip()
            # タイトルに一致するニュースを探す
            for item in news_items:
                if any(word in ref_text for word in item["title"].split()[:3]):
                    source_title = item["title"]
                    source_link = item["link"]
                    break
            if not source_title:
                source_title = ref_text[:80]
            break

    # ニュースが見つからなければ最初のアイテムを使用
    if not source_title and news_items:
        source_title = news_items[0]["title"]
        source_link = news_items[0]["link"]

    tweets = _extract_tweets_flexible(raw)
    if not tweets:
        tweets = _extract_tweets(raw)

    return [
        {"tweet": t, "source_title": source_title, "source_link": source_link}
        for t in tweets
    ]


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIとビジネス変革などのテーマを優先
- ビジネス経営者が「これは知らなかった」と思える内容
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets_flexible(raw)
    return tweets if tweets else _extract_tweets(raw)


def generate_viral_thread(topic: str) -> list[str]:
    """バズりやすいスレッド形式の投稿を生成（1/n〜n/n）"""
    prompt = f"""「{topic}」について、
ビジネス層・経営者に刺さるXスレッド投稿（3ツイート構成）を作成してください。

{AUTHOR_PROFILE}

スレッド構成:
1/3: 衝撃的な事実or問いかけで掴む（140文字以内、「🧵」で始める）
2/3: 具体的なインサイト・データ・事例（140文字以内）
3/3: 実践的アクションor深い問いで締める（140文字以内）

番号付きリスト（1. 2. 3.）で出力。
ハッシュタグは3/3のみに #AI #生成AI のうち1つ。
"""
    raw = _call_claude(prompt)
    return _extract_tweets_flexible(raw)
