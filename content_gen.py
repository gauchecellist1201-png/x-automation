"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層ターゲット・バズ特化版
"""

import os
import re
import feedparser
import anthropic

# X の日本語ツイートでの実効文字数上限
# 日本語は1文字=2weight、URLは固定23weight、上限280weight
# 120文字(=240weight) + URL(23weight) + ハッシュタグ等 ≒ 280weight
MAX_TWEET_LENGTH = 120
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求（PHR/EHR、ブロックチェーン医療記録）
- グローバル視点（スイス留学、国連会議参加経験）
- 専門的知識をわかりやすく、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿戦略（ビジネス層ターゲット）

【型1: データ衝撃型】
具体的な数字・パーセンテージで驚かせる。
例：「AI導入企業は競合比3倍の生産性。まだ手動でやっている理由は？」

【型2: FOMO（乗り遅れ恐怖）型】
「乗り遅れたら終わり」という危機感を与える。
例：「2026年末、AI使えないビジネスマンの市場価値は？残り6ヶ月で準備を」

【型3: 逆張り洞察型】
主流と反対の視点で差別化する。
例：「みんながChatGPTに熱狂している間、賢い経営者は○○を準備している」

【型4: 問いかけ型】
答えが気になる問いでリプライを誘発する。
例：「あなたの会社でまだ人間がやっている作業、AIに任せたら何時間浮きますか？」

【型5: ランキング・リスト型】
スキャンしやすく保存されやすい。
例：「AIで最初に変わるビジネス職種TOP3：1. ○○ 2. ○○ 3. ○○」

## 共通ルール
- 具体的な数字・データを必ず入れる（「3倍」「70%」「6ヶ月」等）
- ビジネスへの直接インパクトを語る（コスト・時間・競争優位）
- 最後を問いかけで締めるとRT・リプが増える
- ハッシュタグは #AI #生成AI #DX から1〜2個まで
- URLリンクがあれば文末に自然に添付（文字数に含めない）
"""

# RSS フィード（ビジネス文脈強化版）
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+企業活用+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+最新ニュース&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]


def _call_claude(prompt: str, max_tokens: int = 1024) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数制限内に絞る。"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+[\.\)]\s*", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_viral_posts(trend_context: dict) -> list[str]:
    """
    トレンド分析結果をもとに、ビジネス層に刺さるバイラル投稿を生成する。
    これがメインの生成関数。
    """
    news = trend_context.get("news", [])
    buzz_analysis = trend_context.get("buzz_analysis", "")
    top_news = trend_context.get("top_news")

    headlines_text = "\n".join(f"- {n['title']}" for n in news[:10])
    link_hint = f"\n- 記事URL（文末に添付可能）: {top_news['url']}" if top_news else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
今日のAIビジネストレンドを元に、ビジネス層（経営者・マネージャー・IT担当）に刺さる
バイラル投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

## 今日のトレンド分析
{buzz_analysis}

## 今日の最新AIニュース
{headlines_text}

出力ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内（URLは別途添付するため含めない）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで文末に含める
- 3案それぞれ異なる「型」を使う{link_hint}
- 医療×AI・社会変革・未来への洞察を絡めると尚良い
- 具体的な数字を必ず1つ以上含める
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績（few-shot）から戦略的投稿案を生成する。"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{few_shot_section}
出力ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 具体的な数字を必ず1つ以上含める{link_instruction}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSからAIビジネスニュースをURL付きで取得する。"""
    items: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss(trend_context: dict | None = None) -> list[str]:
    """最新AIニュースを元に投稿案を生成する（フォールバック用）。"""
    news = fetch_rss_headlines()
    if not news:
        return _generate_original_ai_insight()

    if trend_context:
        return generate_viral_posts(trend_context)

    headlines_text = "\n".join(f"- {n['title']}" for n in news)
    top_url = news[0]["url"] if news else ""
    link_hint = f"\n- 参考URL（文末に添付可能）: {top_url}" if top_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 3案それぞれ異なる「型」を使う
- 具体的な数字を必ず含める{link_hint}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSS取得失敗時のオリジナル洞察ツイート生成。"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最もビジネスインパクトの大きいトピックについて、
経営者・マネージャー・IT担当が「保存したい」と思う投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 3案それぞれ異なる「型」を使う
- 具体的な数字を必ず含める
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def select_best_post(posts: list[str]) -> str | None:
    """複数の候補から最もバイラルしそうな1案をClaudeが選ぶ。"""
    if not posts:
        return None
    if len(posts) == 1:
        return posts[0]

    candidates = "\n".join(f"{i+1}. {p}" for i, p in enumerate(posts))
    prompt = f"""以下のX投稿候補から、ビジネス層に最もバイラルしやすい1案を選び、
その番号だけを答えてください（数字のみ）。

{candidates}
"""
    raw = _call_claude(prompt, max_tokens=10).strip()
    try:
        idx = int(re.search(r"\d+", raw).group()) - 1
        if 0 <= idx < len(posts):
            return posts[idx]
    except Exception:
        pass
    return posts[0]
