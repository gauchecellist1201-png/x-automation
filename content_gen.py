"""
Claude API を使ったビジネス層向けバズ投稿生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: 経営者・マネージャー・スタートアップ創業者
"""

import os
import re
import requests
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語: AIビジネス活用系
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+活用+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+Claude+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI+最新+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語: グローバルAIビジネス動向
    "https://venturebeat.com/category/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
]

MAX_TWEET_LENGTH = 200  # URL含まず200文字（URL=23文字換算で合計280以内を確保）
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 発信者: @GAUCHE_cellist（井出直毅）
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求するビジネス視点のAIコメンテーター
- 最新AI動向をビジネスに直結した洞察で解説
- 専門的知識 × 経営的視点 × グローバル経験（スイス・国連会議等）
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

BUSINESS_VIRAL_STRATEGY = """
## ビジネス層向けバズ投稿戦略（ユーザー獲得特化）

### ターゲット読者
経営者・マネージャー・スタートアップ創業者・ビジネス意識の高い30〜50代

### 必須フック（最初の1文で読者を止める）
以下のどれか1つを必ず最初の1文に使う:

1. **数字フック** — 具体的な数字・割合・時間で驚かせる
   例: 「AI活用企業の生産性は非活用企業の2.3倍（McKinsey 2025）」
   例: 「週20時間かかっていた作業がAI導入で3時間に」

2. **逆説フック** — 常識を覆す視点
   例: 「AIを使うより使わない判断の方が難しい時代が来た」
   例: 「AIは仕事を奪わない。AIを使う競合が奪う」

3. **緊急性フック** — 乗り遅れへの危機感
   例: 「今AIに投資しない経営者は、3年後に後悔する」
   例: 「競合がAIを導入している間、あなたの会社は何をしている？」

4. **速報フック** — 最新ニュースをビジネス視点で解説
   例: 「【速報】○○社がAIで○○を達成→ビジネスへの影響はこう読む」

5. **問いかけフック** — RT・いいねを最大化する問い
   例: 「あなたの会社のAI戦略、本当に機能していますか？」

### 投稿構成
- 1文目: 最強フック（スクロールを止める）
- 2〜3文: 具体的内容・洞察・データ・医療/社会変革との接点
- 最後: 問いかけ or リンク + ハッシュタグ（#AI #生成AI #ビジネス から1〜2個）

### 禁止事項
- 弱い表現（「〜かもしれません」「〜と思います」）
- 抽象的すぎる言葉
- ハッシュタグ3個以上
- 200文字を超える本文（URL別途23文字で合計280文字以内を守る）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_length: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きリストから投稿文を抽出してmax_length文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_length]


def _fetch_og_image(url: str) -> str | None:
    """記事URLからog:image / twitter:image を取得する"""
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        text = resp.text[:8000]
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def fetch_rss_items(max_items: int = 10) -> list[dict]:
    """RSSフィードから記事リストを取得（タイトル・URL・サマリー付き）"""
    items: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()[:300]
                if title and len(title) > 10 and link:
                    items.append({"title": title, "url": link, "summary": summary})
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績（few-shot）から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを自然に含める: {note_url}" if note_url else ""

    prompt = f"""あなたは @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_VIRAL_STRATEGY}

ルール:
- 各投稿は200文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], dict | None]:
    """最新AIニュースからビジネス層向け投稿案を生成。(posts, best_article) を返す"""
    items = fetch_rss_items()

    if not items:
        return _generate_original_ai_insight(), None

    headlines_text = "\n".join(f"{i+1}. {item['title']}" for i, item in enumerate(items))

    # Claudeに最もビジネス層に刺さる記事を選ばせる
    selection_prompt = f"""以下のAIニュース一覧から、ビジネスパーソン（経営者・マネージャー）が
最も「知りたい・シェアしたい」と思うトピックを1つ選び、その番号だけ答えてください（数字のみ）。

{headlines_text}
"""
    raw_selection = _call_claude(selection_prompt).strip()
    selected_idx = 0
    try:
        match = re.search(r"\d+", raw_selection)
        if match:
            selected_idx = max(0, min(int(match.group()) - 1, len(items) - 1))
    except Exception:
        selected_idx = 0

    best_item = items[selected_idx]

    prompt = f"""あなたは @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースをビジネス層向けに解説するX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_VIRAL_STRATEGY}

ルール:
- 各投稿は200文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 少なくとも1案はニュースリンク（{best_item['url']}）を文末に含める

## 今日の注目AIニュース
タイトル: {best_item['title']}
URL: {best_item['url']}
内容: {best_item.get('summary', '')}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)

    # og:image取得
    best_item["image_url"] = _fetch_og_image(best_item["url"])

    return posts, best_item


def generate_evening_thread(items: list[dict] | None = None) -> list[str]:
    """夜用：ビジネス層に刺さる深い洞察スレッドを生成（3〜4ツイート）"""
    context = ""
    if items:
        top = "\n".join(f"- {item['title']}" for item in items[:3])
        context = f"\n## 今日のAIトピック参考\n{top}\n"

    prompt = f"""あなたは @GAUCHE_cellist（井出直毅）の投稿担当AIです。
ビジネス層（経営者・マネージャー）に刺さるAI洞察スレッドを作成してください。

{AUTHOR_PROFILE}
{BUSINESS_VIRAL_STRATEGY}

スレッド構成（3〜4ツイート）:
1ツイート目: 強烈なフック + 「↓」で続きを促す（フォロー・RTを狙う）
2ツイート目: 具体的な内容・データ・事例
3ツイート目: ビジネスへの示唆 or 医療×AIの視点
4ツイート目: 読者への問いかけ（エンゲージメント最大化）

ルール:
- 各ツイートは140文字以内
- 各ツイートを「---」で区切って出力
- ハッシュタグは最終ツイートのみ（1〜2個）
- 番号やラベルは不要、ツイート本文のみ出力
{context}
"""
    raw = _call_claude(prompt)
    tweets = [t.strip() for t in raw.split("---") if t.strip() and len(t.strip()) >= 10]
    return [t for t in tweets if 0 < len(t) <= 140]


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿を生成"""
    prompt = f"""あなたは @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なビジネストレンドについて、
経営者・マネージャーが「これは見落とせない」と感じる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_VIRAL_STRATEGY}

ルール:
- 各投稿は200文字以内
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- テーマ候補: AIエージェント、医療AI、AI規制動向、組織変革、生産性革命、日本企業のAI遅れ
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
