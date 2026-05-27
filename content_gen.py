"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）

バズる投稿を生成するための高度な戦略を実装:
- 7種類の実証済みバズパターン
- ビジネス層向けフック（数字・競合優位・危機感）
- スレッド形式サポート
- ツイートスコアリング
- 画像タイプ提案
"""

import os
import re
import unicodedata
import feedparser
import anthropic
from datetime import date

RSS_FEEDS = [
    # 日本語AIニュース（複数テーマ）
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用+企業+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+診断+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+最新情報&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（トレンド先行キャッチ）
    "https://news.google.com/rss/search?q=AI+breakthrough+2026+business+enterprise&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+healthcare+medical+2026&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大テーマに活動
- スイス研究・国連会議参加のグローバル視点
- Claude Code等の最新AIツールを実務活用中
- 洞察を「問い」の形で静かに届けるスタイル
"""

VIRAL_TWEET_FORMATS = """
## バズるX投稿の7パターン（必ずいずれか1つを選んで使うこと）

【P1: 衝撃スタット】数字で驚かせ、意味を問う
例:「AIが医師の診断ミスを34%削減したデータが出た。日本の医療訴訟が年4000件という現実と重ねると、何が見えてくるか。 #医療AI」

【P2: 逆張り洞察】常識をひっくり返す一言
例:「AIは仕事を奪わない。AIを使いこなす人間が、使いこなせない人間の仕事を奪う。この差は2年で顕在化する。 #生成AI」

【P3: 問いかけフック】核心的な問いで読者を引き込む
例:「なぜ一流の経営者ほどAIを自分で触っているのか。答えは"意思決定の質"にある。 #AI」

【P4: 箇条書きリスト】価値を凝縮、保存されやすい
例:「AIで変わる医師の仕事↓
①診断→精度+34%
②論文検索→秒速
③カルテ→音声で自動化
残るのは「判断」と「共感」だけ。 #医療AI」

【P5: ストーリー型】体験談で共感を生む
例:「Claude Codeで3時間の作業が15分になった。コードを書けない医学生の私が言うのだから、これは本物だと思う。 #生成AI」

【P6: スレッド起点】深い洞察へ誘う
例:「医療×AIで起きていること、誰も教えてくれないのでまとめます🧵(1/5)」

【P7: 未来予測】不安と期待を同時に刺激
例:「2027年、AI診断が保険適用になる国が出る。その時、医師という職業の定義は変わる。日本はどこにいるか。 #AI」
"""

BUSINESS_FOCUS = """
## ビジネス層（経営者・管理職・起業家）に刺さる要素（1つ以上必ず含める）
- 具体的な数字・比率：「○%向上」「○倍速」「○分の1」「○円削減」
- 競合優位性：「導入企業と非導入企業の差」「早期採用者の優位」
- タイムプレッシャー：「今動かないと○年後に」「2年以内に差がつく」
- 行動喚起：「今すぐできること」「知っておくべきAI知識」
- リスク認識：「知らないと損するAI活用法」
"""

TWEET_RULES = """
## 必須ルール（厳守）
- 最初の20文字で読者を掴む（これが最重要）
- 各ツイートは140文字以内（改行・ハッシュタグ・URL含む）
- URLは23文字換算
- ハッシュタグは #AI #生成AI #医療AI #医療DX のうち最大2個（文末のみ）
- 文末を「。」で終わらせず余韻を残す
- 改行で読みやすくする（リスト投稿は特に有効）
- 感情を動かす：驚き・危機感・希望・好奇心のいずれかを狙う
"""


# ─────────────────────────────────────────────────
# Core Claude API call
# ─────────────────────────────────────────────────

def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ─────────────────────────────────────────────────
# Tweet parsing
# ─────────────────────────────────────────────────

def _parse_delimited_tweets(raw: str) -> list[str]:
    """---TWEETn--- デリミタ形式でツイートを抽出（多行対応）"""
    pattern = r"---TWEET\d+---\s*(.*?)(?=---TWEET\d+---|$)"
    matches = re.findall(pattern, raw, re.DOTALL)
    tweets = [m.strip() for m in matches if m.strip()]
    return tweets[:NUM_CANDIDATES] if tweets else _fallback_extract(raw)


def _fallback_extract(raw: str) -> list[str]:
    """デリミタなし時のフォールバック（空行区切りブロック）"""
    blocks = re.split(r"\n\s*\n", raw.strip())
    tweets = []
    for block in blocks:
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", block.strip())
        if cleaned and 10 < len(cleaned) <= MAX_TWEET_LENGTH * 1.4:
            tweets.append(cleaned)
    return tweets[:NUM_CANDIDATES]


def _parse_thread(raw: str) -> list[str]:
    """スレッド形式の出力を解析"""
    return _parse_delimited_tweets(raw)


# ─────────────────────────────────────────────────
# Tweet scoring & image suggestion
# ─────────────────────────────────────────────────

def score_tweet(tweet: str) -> int:
    """ツイートのバズりやすさスコア（0〜100）"""
    score = 50

    # 数字・単位があると+15（ビジネス訴求）
    if re.search(r'\d+\s*[%倍円億万分秒件個人社]', tweet):
        score += 15

    # 疑問符 or 「か」で終わる+10（読者を考えさせる）
    if re.search(r'[？?]', tweet) or tweet.rstrip('　 \n').endswith('か'):
        score += 10

    # 改行あり+8（リスト型・読みやすさ）
    if '\n' in tweet:
        score += 8

    # 絵文字+5（最大10）
    emoji_count = sum(
        1 for c in tweet
        if unicodedata.category(c) == 'So' or 0x1F300 <= ord(c) <= 0x1FAFF
    )
    score += min(emoji_count * 5, 10)

    # ハッシュタグ1〜2個で+5
    ht_count = tweet.count('#')
    if 1 <= ht_count <= 2:
        score += 5

    # 80〜135文字でボーナス+7
    if 80 <= len(tweet) <= 135:
        score += 7

    # 「。」で終わらない余韻+5
    if not tweet.rstrip('　 \n').endswith('。'):
        score += 5

    return min(score, 100)


def suggest_image(tweet: str) -> str:
    """投稿に適した画像タイプを提案"""
    if re.search(r'\d+[%倍]', tweet):
        return "📊 グラフ・インフォグラフィック（数字を視覚化）"
    if any(w in tweet for w in ['医療', '診断', 'ヘルスケア', '患者', '医師']):
        return "🏥 医療×AIビジュアル（白衣+タブレット等）"
    if any(w in tweet for w in ['未来', '予測', '変わる', '2027', '2028', '2029']):
        return "🔮 近未来×AIのビジュアル"
    if any(w in tweet for w in ['企業', '経営', 'ビジネス', '投資', '生産性', 'ROI']):
        return "💼 ビジネス×AI図解・チャート"
    if any(w in tweet for w in ['コード', '開発', 'Claude Code', 'エンジニア']):
        return "💻 コーディング×AI画面キャプチャ"
    return "🤖 AIテーマのニュートラルビジュアル"


# ─────────────────────────────────────────────────
# RSS fetching
# ─────────────────────────────────────────────────

def fetch_rss_headlines(max_items: int = 12) -> list[tuple[str, str]]:
    """RSSから (タイトル, URL) のリストを取得・重複排除"""
    items: list[tuple[str, str]] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if title and len(title) > 10:
                    items.append((title, link))
        except Exception:
            continue
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for title, link in items:
        if title not in seen:
            seen.add(title)
            unique.append((title, link))
    return unique[:max_items]


# ─────────────────────────────────────────────────
# Post generation
# ─────────────────────────────────────────────────

def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
) -> list[str]:
    """Note記事からバイラルX投稿案を3案生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    url_note = f"\n- 記事リンクを文末に自然に入れてよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_FORMATS}
{BUSINESS_FOCUS}
{TWEET_RULES}
{url_note}
{few_shot}
【出力形式（厳守）】
---TWEET1---
[1案目のツイート全文]
---TWEET2---
[2案目のツイート全文]
---TWEET3---
[3案目のツイート全文]

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_delimited_tweets(raw)


def generate_posts_from_rss() -> list[str]:
    """最新RSSニュースからビジネス層向けX投稿案を3案生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {title}" for title, _ in items[:8])
    best_url = items[0][1] if items else ""
    url_note = f"\n- 参考記事URL（文末に入れてもよい）: {best_url}" if best_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も重要・バズりやすいトピックを1つ選び、X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_FORMATS}
{BUSINESS_FOCUS}
{TWEET_RULES}
{url_note}

【出力形式（厳守）】
---TWEET1---
[1案目のツイート全文]
---TWEET2---
[2案目のツイート全文]
---TWEET3---
[3案目のツイート全文]

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _parse_delimited_tweets(raw)


def generate_thread_from_rss() -> list[str]:
    """スレッド形式（4ツイート）を生成してリストで返す"""
    items = fetch_rss_headlines()
    topic = items[0][0] if items else "2026年AIトレンド最前線"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックでXスレッド（4ツイート）を作成してください。

{AUTHOR_PROFILE}
{BUSINESS_FOCUS}
{TWEET_RULES}

スレッド構成（厳守）:
ツイート1: フック（続きを読みたくなる冒頭 + 「🧵(1/4)」を末尾に）
ツイート2: 核心的な洞察・データ（末尾に「(2/4)」）
ツイート3: ビジネス・社会への影響（末尾に「(3/4)」）
ツイート4: まとめ + 行動喚起（末尾に「(4/4)」）

各ツイートは140文字以内。

【出力形式（厳守）】
---TWEET1---
[1/4ツイート]
---TWEET2---
[2/4ツイート]
---TWEET3---
[3/4ツイート]
---TWEET4---
[4/4ツイート]

トピック: {topic}
"""
    raw = _call_claude(prompt)
    return _parse_thread(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSS取得失敗時のオリジナル投稿生成（曜日テーマ制）"""
    themes = [
        "企業のAI活用とROI・生産性向上（月曜: ビジネス×AI）",
        "医療×AIの最前線と医師の未来（火曜: 医療×AI）",
        "最新AIモデルが変えるワークフロー（水曜: テクノロジー最前線）",
        "AI時代の雇用・教育・社会変革（木曜: 社会変革）",
        "今日から使えるAIツール活用術（金曜: 実践・活用）",
        "AIの本質・哲学と長期トレンド（土曜: 深掘り洞察）",
        "今週のAI総括と来週の注目動向（日曜: 週まとめ）",
    ]
    theme = themes[date.today().weekday()]

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
本日のテーマ「{theme}」について、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_FORMATS}
{BUSINESS_FOCUS}
{TWEET_RULES}

【出力形式（厳守）】
---TWEET1---
[1案目のツイート全文]
---TWEET2---
[2案目のツイート全文]
---TWEET3---
[3案目のツイート全文]
"""
    raw = _call_claude(prompt)
    return _parse_delimited_tweets(raw)
