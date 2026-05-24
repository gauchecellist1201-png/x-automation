"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズ分析 + ビジネス層向け最適化版
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース（幅広いトレンド）
    "https://news.google.com/rss/search?q=AI+人工知能+生成AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=Claude+OpenAI+ChatGPT+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=LLM+AIエージェント+2026&hl=ja&gl=JP&ceid=JP:ja",
    # ビジネス層向け
    "https://news.google.com/rss/search?q=AI+ビジネス+DX+経営+生産性&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+スタートアップ+投資+調達&hl=ja&gl=JP&ceid=JP:ja",
    # 医療×AI
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+診断&hl=ja&gl=JP&ceid=JP:ja",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHRへのブロックチェーン活用・非中央集権的医療データ管理を研究
- スイス大学研究・国連会議参加のグローバル視点
- Claude Codeなど最新AIをフル活用中
- 専門的知識を読者に刺さる言葉で届けるスタイル
- 押しつけがましくなく、静かに鋭い洞察を発信
"""

BUZZ_PATTERNS = """
## バズりやすい投稿パターン（これらを参考に作成すること）

【パターン1: 数字インパクト型】
AIは1秒で医師100人分の論文を読む。
でもまだ「感じる」ことはできない。
医療AIが補えるのは「知識」。「判断」はまだ人間にしかできない。 #AI #医療

【パターン2: 逆説・驚愕型】
AIに仕事を奪われると怖がる人ほど、AIを全く使っていない。
変わるのは、AIをフル活用している側の仕事。
先行者利益は今がピーク。 #生成AI

【パターン3: 問いかけ型（RTされやすい）】
あなたの医療データ、誰が管理すべきだと思いますか？
今は病院のサーバーに眠っている。
患者主権の医療へ—ブロックチェーンが鍵かもしれない。 #医療DX

【パターン4: ビジネス数字型】
GPT活用で業務効率40%向上—McKinseyの試算。
日本企業の導入率はまだ15%以下。
格差は今、急速に広がっている。 #AI #DX

【パターン5: 予言・未来型】
5年後、医師の診断支援AIは聴診器と同じくらい当たり前になる。
問題は技術ではなく、信頼と規制。
誰が制度設計するかで医療の未来が変わる。 #AI

【パターン6: リスト型（保存されやすい）】
今すぐ使うべきAIツール3選：
①Claude—深い思考・文書作成
②Perplexity—最新情報検索
③Gamma—プレゼン自動生成
これだけで月20時間取り戻せる。 #生成AI

【パターン7: 格差・危機感型】
AIを使える人と使えない人の生産性差は、2026年で3倍を超えた。
これはスマホ普及期と同じ構造。
あの時乗り遅れた人の後悔を、今AI で繰り返していないか。 #生成AI
"""

TWEET_STRATEGY = """
## 投稿戦略（ビジネス層向けバズ最大化）
1. 最初の15文字でスクロールを止める（数字、驚愕、問い、格差）
2. 具体的な数字・パーセント・企業名で信頼性を上げる
3. ビジネスインパクト（コスト・時間・競争優位・格差）に言及する
4. 医療・社会変革という独自ポジションを絡める
5. 「問い」で終わるとRTされやすい、「リスト」は保存されやすい
6. ハッシュタグは #AI #生成AI #医療DX #DX から1〜2個まで
7. ネガティブより「可能性」「未来」「チャンス」で締める
"""

THREAD_STRATEGY = """
## スレッド投稿の戦略
- [1/3]: 驚愕の事実・問いでフックを作る
- [2/3]: データ・背景・深掘りで価値を届ける
- [3/3]: 自分の洞察・問いかけ・行動喚起で締める
- スレッドは通常ツイートより3〜5倍エンゲージメントが高い
"""


def _call_claude(prompt: str, system: str = "") -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    message = client.messages.create(**kwargs)
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きブロックから投稿文を抽出（複数行ツイート対応）"""
    # 番号区切りでブロック分割
    blocks = re.split(r"\n(?=\d+[\.\)][\s　])", raw.strip())
    tweets: list[str] = []
    for block in blocks:
        text = re.sub(r"^\d+[\.\)]\s*", "", block).strip()
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # markdown 除去
        if text and 0 < len(text) <= MAX_TWEET_LENGTH:
            tweets.append(text)
    # fallback: 行単位抽出
    if not tweets:
        for line in raw.splitlines():
            clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if clean and 0 < len(clean) <= MAX_TWEET_LENGTH:
                tweets.append(clean)
    return tweets[:NUM_CANDIDATES]


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS から最新AIニュースを取得（タイトル＋URL）"""
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


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 上記バズパターンのいずれかを参考に{link_instruction}
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドから戦略的投稿案を生成。(投稿案リスト, 参考URL) を返す"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {h['title']}" for h in headlines)
    top_url = headlines[0]["url"] if headlines else ""

    prompt = f"""以下の最新AIニュースから最も注目すべきトピックを1つ選び、
@GAUCHE_cellist らしいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI・社会変革・ビジネスインパクトを絡めると尚良い
- ハッシュタグは1〜2個まで
- 上記バズパターンのいずれかを参考にすること

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    if not posts:
        posts, top_url = _generate_original_ai_insight(), ""
    return posts, top_url


def generate_thread_post(topic_hint: str = "") -> list[str]:
    """スレッド形式の投稿案（[1/3][2/3][3/3]）を生成して返す"""
    if not topic_hint:
        headlines = fetch_rss_headlines(max_items=3)
        topic_hint = headlines[0]["title"] if headlines else "AIが変えるビジネスの未来"

    prompt = f"""@GAUCHE_cellist として、以下のテーマでXのスレッド投稿（3連続ツイート）を作成してください。

テーマ: {topic_hint}

{AUTHOR_PROFILE}
{THREAD_STRATEGY}

ルール:
- 各ツイートは140文字以内
- 必ず [1/3] [2/3] [3/3] の形式で番号をつける
- [1/3] は驚愕の事実や問いでフック、[2/3] はデータ・洞察、[3/3] は締めの問いかけ
- ハッシュタグは [3/3] にのみ1〜2個
- 医療×AI・社会変革の視点を必ず入れる
"""
    raw = _call_claude(prompt)

    # [1/3] [2/3] [3/3] 形式で抽出
    parts = re.findall(r"\[\d+/\d+\]\s*(.+?)(?=\[\d+/\d+\]|$)", raw, re.DOTALL)
    thread = [p.strip() for p in parts if p.strip()]
    if not thread:
        # fallback: 行単位抽出
        thread = [
            l.strip() for l in raw.splitlines()
            if l.strip() and not l.startswith("#") and len(l.strip()) > 10
        ]
    return thread[:3]


def _generate_original_ai_insight() -> tuple[list[str], str]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""2026年のAI業界で最も重要なトピックについて、
@GAUCHE_cellist らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUZZ_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude・GPT・医療AI・AIと社会変革などのテーマを優先
- 上記バズパターンのいずれかを参考にすること
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw), ""
