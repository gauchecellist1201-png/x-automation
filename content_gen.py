"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層（経営者・管理職・スタートアップ）
"""

import os
import re
import feedparser
import anthropic

# ─────────────────────────────────────────────
# RSS ソース（日本語 + 英語ビジネス AI メディア）
# ─────────────────────────────────────────────
RSS_FEEDS = [
    # 日本語
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    "https://ainow.ai/feed/",
    # 英語（信頼性高いビジネス AI メディア）
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/feed/",
    "https://www.theverge.com/rss/index.xml",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス研究経験・国連会議参加のグローバル視点
- Claude Codeなど最新AIツールを実務活用
- 専門知識を持ちながら「読者に問いを投げかける」スタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

# ─────────────────────────────────────────────
# バイラル投稿パターン（分析済みフォーマット）
# ─────────────────────────────────────────────
VIRAL_PATTERNS = """
## バズりやすい投稿フォーマット（優先的に使用）

### パターン1: 数値ショック型
「○○企業の△△%がAIで□□を削減」→ 驚きの数字で止める
例: AIを導入した企業の87%が「6ヶ月以内にROIを回収」している。まだ検討中の人は競合に3年遅れる。

### パターン2: 逆張り洞察型
「みんながAを信じているが、実はB」→ 常識を覆す
例: ChatGPTを「使っている」と「活用できている」は全然違う。前者は90%。後者は10%未満。

### パターン3: 未来予言型
「2年後にはXになる。今のうちに△△を」→ 緊迫感と行動促進
例: 2027年、AIを使いこなせない医師は「AIに使われる医師」になる。これは脅しでなく予測だ。

### パターン4: 問いかけ型（RTされやすい）
「あなたは○○できますか？」→ 自己投影させる
例: あなたの会社のCEOは「AIで何を変えるか」を答えられるか。答えられない経営者がいる会社には投資しない。

### パターン5: ビフォーアフター型
「1年前の私と今の私」→ 共感と変化を見せる
例: 1年前: レポート作成に4時間。今: AIで30分＋人間がレビュー30分。残り3時間で戦略思考に使う。

### パターン6: リスト型（保存されやすい）
「知らないと損な○○つ」→ 情報価値が高い
例: AIで月30時間削減できる業務3つ①議事録②メール下書き③データ集計。やってない人はすぐやれ。

### パターン7: スレッド予告型
「○○について話す🧵」→ クリックを誘う
例: 医療AIの「本当のリスク」について話す🧵
誰も言わないけど、これが一番重要だと思う。
"""

TWEET_STRATEGY = """
## ビジネス層向けバイラル戦略
1. 最初の一文でスクロールを止める（フック必須）
2. 数字・具体例を必ず入れる（抽象論はスルーされる）
3. ビジネスパーソンの「痛み・焦り・FOMO」に刺さる言葉を選ぶ
4. 医療×AI×社会変革の交差点で独自の視点を出す
5. 「問い」で終わると引用リポストが増える
6. ハッシュタグは #AI #生成AI のうち1〜2個まで（多すぎると逆効果）
7. 140文字の圧縮で密度を上げる（無駄な敬語・接続詞を削る）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    tweets: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        # 番号付きリスト行を抽出
        m = re.match(r"^\d+[\.\)]\s*(.+)", line)
        if m:
            tweet = m.group(1).strip()
            if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                tweets.append(tweet)
    return tweets[:NUM_CANDIDATES]


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
以下のNote記事を読み、ビジネス層（経営者・管理職・スタートアップ創業者）に刺さる
バイラル投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力（投稿文のみ、説明不要）
- ハッシュタグは1〜2個まで
- 上記バイラルパターンを必ず1つ使用{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_opener(topic: str) -> list[str]:
    """スレッド形式の冒頭ツイートを生成（エンゲージメント向上）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、スレッド予告型の冒頭ツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}

スレッド冒頭のルール:
- 最初の一文で強烈なフック（「誰も言わない」「実は」「○年後には」系）
- 「🧵」か「(1/n)」を含める
- 続きを読みたくなる終わり方
- 140文字以内
- 番号付きリスト（1. 2. 3.）で出力

## トピック
{topic}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 12) -> list[dict]:
    """RSSからタイトル＋リンクを取得"""
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
        if len(items) >= max_items:
            break
    return items[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースから、ビジネス層向けバイラル投稿を生成。
    Returns (posts, source_url) — source_url はリンク埋め込み用"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {it['title']}" for it in items)
    # 最も関連度が高そうな記事のリンクを候補として渡す
    source_url = items[0]["link"] if items else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースの中から、ビジネス層が最も反応しそうなトピックを1つ選び、
@GAUCHE_celllistらしい鋭い洞察をバイラル投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（投稿文のみ、説明不要）
- 医療×AI、社会変革、ビジネス競争力の観点を絡める
- ハッシュタグは1〜2個まで
- 上記バイラルパターンのどれか1つを使用

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw), source_url


def _generate_original_ai_insight() -> list[str]:
    """RSS取得不可時のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最もビジネス層が知るべきトピックについて、
鋭い洞察を持つバイラル投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、経営×AI、AIと社会変革などを優先
- 上記バイラルパターンのどれか1つを使用
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def select_best_post(posts: list[str]) -> str:
    """生成された候補から最もバイラルになりそうな1つをClaudeに選ばせる"""
    if not posts:
        return ""
    if len(posts) == 1:
        return posts[0]

    candidates = "\n".join(f"{i+1}. {p}" for i, p in enumerate(posts))
    prompt = f"""以下のX投稿候補から、ビジネス層向けに最もバイラルになりそうな1つを選んでください。

選定基準:
- フックの強さ（最初の一文で止まるか）
- 数字・具体性
- ビジネスパーソンの「痛み・焦り・FOMO」への刺さり方
- 引用リポスト・いいねを誘発する構造

候補:
{candidates}

回答は「番号」だけ返してください（例: 2）
"""
    raw = _call_claude(prompt).strip()
    m = re.search(r"\d+", raw)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(posts):
            return posts[idx]
    return posts[0]
