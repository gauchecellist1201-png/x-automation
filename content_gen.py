"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 — 国内AIトレンド
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ChatGPT&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+企業+導入+生産性&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 — グローバルビジネス×AIトレンド
    "https://news.google.com/rss/search?q=AI+business+enterprise+productivity+2026&hl=en&gl=US&ceid=US:en",
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

# ─── プロンプトキャッシュ対象のシステム指示（変更頻度が低い部分）──────────────────
_CACHED_SYSTEM = """あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
医学生×AI起業家という独自の視点から、ビジネス層に刺さるAI関連投稿を生成します。

## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス研究経験・国連会議参加のグローバル視点
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- 専門的知識を持ちながら、読者に考えさせる問いを投げかける

## ターゲット：ビジネス層
- 経営者・マネージャー・スタートアップ創業者
- AI導入を検討している企業人
- 生産性・ROI・競争優位に敏感
- 難解な専門用語より「使える知識」「明日から使える視点」を好む

## バズるXツイート構造パターン（ビジネス×AI特化）

### 数字インパクト型
「AIを使った企業の生産性が平均○○%向上」「○分でできた」「○億円削減」

### 驚き×事実型
「AIが○○した。これが現実になった」「実はもう○○はAIが全部やっている」

### 問いかけ型（エンゲージメント最高）
「あなたの会社、まだ○○してますか？」「なぜ勝ち組企業だけがAIを使いこなせるのか」

### 知らないと損型
「99%のビジネスパーソンが知らないAIの使い方」「これを知らないと2年後に後悔する」

### 対比・格差型
「AIを使う人と使わない人の差が、1年で取り返せないレベルになってきた」

### 未来予言型
「2027年には○○の仕事の○%がAIに置き換わる。今から準備するなら何をすべきか」

### 洞察×問い型（RTされやすい）
「AIが仕事を奪うのではなく、AIを使いこなせない人が仕事を奪われる」

### 具体事例型
「実際にClaude Codeで医療プロダクトを1週間で作ってみた」

## 投稿ルール
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで（#AI #生成AI #ChatGPT から選択）
- 最初の1文でスクロールを止めること（フックが命）
- 医療・社会変革・ビジネス変革の文脈を絡めると尚良い
- 「問い」で終わるとRTされやすい
- 結論より問いで終わる方がシェアされやすい"""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _call_claude_cached(user_prompt: str) -> str:
    """システムプロンプトをキャッシュしてClaudeを呼び出す"""
    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _CACHED_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _call_claude_simple(user_prompt: str) -> str:
    """軽量タスク用（haiku）"""
    client = _get_client()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    posts = []
    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s*", stripped):
            text = re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()
            if 0 < len(text) <= MAX_TWEET_LENGTH:
                posts.append(text)
    return posts


def generate_image_prompt(tweet_text: str, topic: str = "") -> str:
    """ツイートに合ったDALL-E用英語プロンプトをhaiku経由で生成"""
    prompt = (
        "Generate a single English image prompt for DALL-E 3 that matches this Japanese tweet.\n"
        "Requirements: professional, business/tech aesthetic, NO text or letters in image, "
        "cinematic lighting, 4K quality.\n\n"
        f"Tweet: {tweet_text}\n"
        f"{'Topic: ' + topic if topic else ''}\n\n"
        'Reply with ONE English prompt starting with "A professional...":'
    )
    return _call_claude_simple(prompt).strip()


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから最新AIニュースを取得（タイトル＋リンク）"""
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
                    items.append({"title": title, "link": link})
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事＋過去実績(few-shot)から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_inst = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""以下のNote記事を読み、上記のバズりパターンを使ってビジネス層に刺さる投稿を{NUM_CANDIDATES}案作成してください。{link_inst}
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude_cached(prompt)
    return _extract_posts(raw)


def generate_posts_from_rss() -> tuple[list[str], str, str]:
    """
    最新AIニュースから投稿案を生成。
    戻り値: (投稿リスト, 選択記事タイトル, 選択記事URL)
    """
    items = fetch_rss_headlines()

    if not items:
        return _generate_original_ai_insight(), "", ""

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""以下の最新AIニュースから最もバズりそうなトピックを1つ選び、ビジネス層に刺さる投稿を{NUM_CANDIDATES}案作成してください。
上記の「バズるXツイート構造パターン」を必ず1つ以上活用してください。

## 今日の最新AIニュース
{headlines_text}

※ 選んだトピックのニュースタイトルを最初に「選択: 【記事タイトル】」と書いてから投稿案を列挙してください。
"""
    raw = _call_claude_cached(prompt)
    posts = _extract_posts(raw)

    # 選択された記事のタイトル・URLを特定
    selected_title, selected_url = "", ""
    for line in raw.splitlines():
        if re.search(r"選択[：:]", line):
            title_raw = re.sub(r".*選択[：:][\s【]*", "", line).strip().rstrip("】")
            for item in items:
                if title_raw[:15] in item["title"] or item["title"][:15] in title_raw:
                    selected_title = item["title"]
                    selected_url = item["link"]
                    break
            break

    return posts, selected_title, selected_url


def _generate_original_ai_insight() -> list[str]:
    """RSS取得失敗時のフォールバック：オリジナル洞察ツイート"""
    prompt = f"""2026年のAI業界で最も注目すべきトピックについて、
バズりやすい投稿を{NUM_CANDIDATES}案作成してください。
「バズるXツイート構造パターン」を必ず活用し、ビジネス層が思わずRTしたくなる内容にしてください。
Claude、GPT-5、医療AI、AIと社会変革などのテーマを優先してください。"""
    raw = _call_claude_cached(prompt)
    return _extract_posts(raw)
