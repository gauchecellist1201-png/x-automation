"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import time
import requests
import feedparser
import anthropic

# ─── RSS / ニュースソース ───────────────────────────────────────────────────────
RSS_FEEDS = [
    # 日本語AI情報
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス+活用+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+AIエージェント+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+革命&hl=ja&gl=JP&ceid=JP:ja",
    # ビジネス向け英語AI情報
    "https://news.google.com/rss/search?q=AI+enterprise+business+ROI+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+disruption+industry&hl=en&gl=US&ceid=US:en",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

# ─── アカウントプロフィール ────────────────────────────────────────────────────
AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHR へのブロックチェーン活用、非中央集権的医療データ管理を研究・実装
- スイスの大学での研究経験、国連会議参加などグローバルな視点を持つ
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける文体
- ターゲット読者：ビジネスパーソン、経営者、スタートアップ創業者、医療従事者
"""

# ─── バズる型テンプレート ──────────────────────────────────────────────────────
VIRAL_PATTERNS = """
## 【実証済み】バズるAI投稿の型

【型1：衝撃数字フック】
例：「McKinseyの最新調査、AIを導入した企業の生産性が平均40%向上。しかし活用できている経営者は12%だけ。」
理由：数字×意外性のギャップが読み止める力を生む

【型2：逆張り洞察型】
例：「ChatGPTより賢いAIが出るたびに騒ぐ。でも本質はそこじゃない。使いこなせない組織が問題だ。」
理由：「言いにくいことを言ってくれた」感がRT/いいねを誘発

【型3：業界変革宣言型】
例：「AIが医師の診断精度を超えた分野がある。が、医師が消えるのではなく"問診の質"で差がつく時代が来た。」
理由：危機感×新たな生存戦略の提示がビジネス層に刺さる

【型4：具体的行動価値型】
例：「AIエージェントで週20時間の資料作成をゼロにした。具体的な手順は→」
理由：再現性×実用性でブックマーク急増。リンク先誘導にも最適

【型5：問いかけ型（エンゲージメント最大化）】
例：「あなたの会社のAI活用状況は？①まだ様子見 ②試験導入中 ③全社展開済み ——驚いたのは多数派が○だったこと。」
理由：読者を当事者にする設計でリプライ・RT連鎖

【型6：タイムリー速報反応型】
例：「[速報]○○がAI新機能発表。ビジネスへの影響を3点で整理→」
理由：速報性×要約×独自洞察の三重効果

【型7：医療×AI専門型（このアカウントの差別化）】
例：「AIが論文50万本を10秒で解析。医師が20年かけて学ぶことを、AIは1日で処理できる。医療の常識が変わる。」
理由：専門性×社会インパクトが被RT層（医療・IT・ビジネス）に広く届く
"""

TWEET_STRATEGY = """
## 投稿戦略
1. 「知らなかった」「考えさせられた」と思わせる切り口
2. 専門的だが難解すぎない言葉選び（中学生でも読めるが深さがある）
3. 医療・社会変革・ビジネスインパクトへの問いかけを絡める
4. 結論より「問い」で終わるとRTされやすい
5. ハッシュタグは #AI #生成AI #AIビジネス のうち1〜2個まで（多用は逆効果）
6. 数字・%・固有名詞を積極的に使う（抽象より具体）
7. 一文目に命をかける——最初の30文字でスクロールを止める
"""


# ─── Claude API呼び出し ────────────────────────────────────────────────────────
def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)【】]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    # URLは23文字換算。簡易チェック（日本語も英語も1文字=1カウント）
    def effective_len(t: str) -> int:
        url_count = len(re.findall(r"https?://\S+", t))
        text_without_urls = re.sub(r"https?://\S+", "", t)
        return len(text_without_urls.strip()) + url_count * 23

    return [t for t in lines if 0 < effective_len(t) <= MAX_TWEET_LENGTH]


# ─── データ取得 ────────────────────────────────────────────────────────────────
def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから最新ニュースのタイトルとURLを取得"""
    results: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    results.append({"title": title, "url": link})
        except Exception:
            continue
    # タイトルで重複除去
    seen: set[str] = set()
    unique = []
    for item in results:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def fetch_hn_ai_stories(max_items: int = 5) -> list[dict]:
    """Hacker News からトレンドのAI記事を取得"""
    try:
        resp = requests.get(HN_TOP_URL, timeout=8)
        story_ids = resp.json()[:200]
    except Exception:
        return []

    ai_stories: list[dict] = []
    ai_keywords = {
        "ai", "gpt", "llm", "claude", "openai", "gemini", "anthropic",
        "neural", "machine learning", "artificial intelligence", "model",
        "agent", "deepmind", "language model", "copilot",
    }
    for sid in story_ids[:80]:
        try:
            item = requests.get(HN_ITEM_URL.format(sid), timeout=5).json()
            title = item.get("title", "").lower()
            if any(kw in title for kw in ai_keywords):
                ai_stories.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "score": item.get("score", 0),
                    "comments": item.get("descendants", 0),
                })
                if len(ai_stories) >= max_items:
                    break
            time.sleep(0.1)
        except Exception:
            continue
    # スコア順でソート（注目度順）
    return sorted(ai_stories, key=lambda x: x["score"], reverse=True)


# ─── コンテンツ生成 ────────────────────────────────────────────────────────────
def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、一般読者にも刺さる言葉で{link_instruction}
- 上記「バズるAI投稿の型」の中から最適な型を選んで使う
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], list[dict]]:
    """
    RSS + HackerNews から最新AIトレンドを取得し、バズ型に沿った投稿案を生成。
    Returns: (投稿案リスト, 参考ニュースリスト)
    """
    # HN トレンド（注目度が高い）
    hn_stories = fetch_hn_ai_stories(max_items=5)
    # RSS ヘッドライン
    rss_items = fetch_rss_headlines(max_items=8)

    if not hn_stories and not rss_items:
        posts = _generate_original_ai_insight()
        return posts, []

    # HNを優先、なければRSSで補完
    news_section = ""
    source_items: list[dict] = []

    if hn_stories:
        news_section += "## HackerNews トレンドAI記事（スコア・注目度順）\n"
        for s in hn_stories:
            news_section += f"- [{s['score']}pt] {s['title']} ({s['url']})\n"
            source_items.append(s)

    if rss_items:
        news_section += "\n## 最新AIニュース（RSS）\n"
        for item in rss_items[:6]:
            news_section += f"- {item['title']}\n"
            source_items.append(item)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層（経営者・スタートアップ・医療従事者）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 上記「バズるAI投稿の型」の中から最適な型を選んで使う（型名をコメントしなくてよい）
- 医療×AI、社会変革、ビジネスインパクトを絡めると尚良い
- ハッシュタグは1〜2個まで
- 具体的な数字・企業名・パーセンテージを積極的に使う

{news_section}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    return posts, source_items


def _generate_original_ai_insight() -> list[str]:
    """RSSもHNも取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層（経営者・スタートアップ・医療従事者）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 上記「バズるAI投稿の型」の中から最適な型を選んで使う
- Claude、AIエージェント、医療AI、AIとビジネス変革などのテーマを優先
- 具体的な数字や固有名詞を必ず入れる
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
