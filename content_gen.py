"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズ分析 + 最新AIニュースから高エンゲージメント投稿を生成
"""

import os
import re
import feedparser
import requests
import anthropic
from datetime import date

# ── RSS フィード（日本語・英語のAIニュースを幅広くカバー）────────────
RSS_FEEDS = [
    # 日本語：AI全般ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+業務効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+新機能+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 日本語：テック記事（人気コンテンツ）
    "https://zenn.dev/topics/ai/feed",
    "https://qiita.com/tags/ai/feed",
    # 英語：グローバルAIトレンド
    "https://news.google.com/rss/search?q=Claude+Anthropic+OpenAI+AI+breakthrough&hl=en&gl=US&ceid=US:en",
    "https://techcrunch.com/feed/",
]

TWEET_CHAR_LIMIT = 140
NUM_CANDIDATES = 3

# ── 著者プロフィール ──────────────────────────────────────────────────
_AUTHOR_PROFILE = """\
## 著者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合が最大テーマ
- スイス大学で研究、国連会議参加のグローバル視点
- PHR/EHRへのブロックチェーン活用、医療データ民主化を研究・実装中
- 「考えさせる問い」を投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- Claude Codeなど最新AIツールを実際に使い倒している実践者
"""

# ── バズる投稿パターン（ビジネス層向け分析）─────────────────────────
_VIRAL_PATTERNS = """\
## バズる投稿パターン分析（日本語ビジネス層向け）

【パターンA: 驚きの事実型】
「〇〇が△△できるようになった。これが意味することは──」
→ 知らなかった感を提供。具体的数字・事例で信頼感UP。保存・RT誘発。

【パターンB: 二項対立・逆説型】
「AIは〇〇の仕事を奪う。でも△△はむしろ増える。」
「〇〇が無くなる時代。でも本当に消えるのは△△かもしれない。」
→ 「自分はどっち？」と考えさせる。返信・RT誘発。

【パターンC: 問いかけ型】
「あなたはまだ〇〇を手作業でやっていますか？」
「これを知らずにビジネスをしていると、3年後に後悔する」
→ 当事者意識を喚起。ビジネスパーソンが反応しやすい。

【パターンD: 未来予言型】
「2027年、〇〇業界は別の姿になっている。その理由は──」
「今から3年で変わること：〇〇、△△、□□」
→ 危機感と期待を同時に喚起。保存・シェア狙い。

【パターンE: 一言洞察型（名言化）】
「AIが賢くなるほど、問いの質が人間の価値になる。」
「〇〇を効率化したAIは、△△を人間に返してくれる。」
→ 短く深い。引用RTされやすい。コメント欄が活性化。

【パターンF: 速報・解説型】
「【速報】〇〇が△△を発表。ビジネスが変わる3つのポイント──」
→ 情報価値が高く、フォロー・保存に繋がる。

【パターンG: 体験談型】
「実際に〇〇を業務に導入してみた。最も変わったのは△△だった。」
→ 具体性と体験の信頼感。「私も試したい」を生む。
"""

# ── 投稿戦略 ─────────────────────────────────────────────────────────
_TWEET_STRATEGY = """\
## 投稿戦略
- ビジネスパーソン・経営者・医療関係者が「役立つ」と感じる情報価値
- 朝7-9時・昼12時・夜21-23時の通勤・休憩時間を意識した簡潔さ
- 1ツイートに「1つの洞察」だけ。欲張らない
- 結論より「問い」で終わるとRTされやすい
- ハッシュタグは #AI #生成AI のうち1〜2個まで（多すぎると逆効果）
- 「スクショしてあとで読みたい」と思わせる内容
- 医療×AI・社会変革・未来への問いを絡めると個性が出る
"""

# キャッシュ対象のシステムプロンプト（静的テキスト）
_SYSTEM_PROMPT = f"{_AUTHOR_PROFILE}\n{_VIRAL_PATTERNS}\n{_TWEET_STRATEGY}"


def _call_claude(user_prompt: str) -> str:
    """プロンプトキャッシュを活用してClaudeを呼び出す"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出（複数行対応・140字チェック）"""
    # 番号マーカー（1. / 1) / 【1】など）で分割
    segments = re.split(r'\n\s*(?:\d+[\.\)]|【\d+】)\s*', '\n' + raw)
    tweets: list[str] = []
    for segment in segments[1:]:
        # 二重改行までを1ツイートとして取得
        tweet = segment.split('\n\n')[0].strip()
        # 前後の余分な記号を除去
        tweet = re.sub(r'^[─━\-=]+\s*', '', tweet).strip()
        if not tweet:
            continue
        if len(tweet) <= TWEET_CHAR_LIMIT:
            tweets.append(tweet)
        else:
            # 140字を超える場合、句読点で自然に切る
            truncated = tweet[:TWEET_CHAR_LIMIT]
            for punct in ['。', '！', '？', '…', '\n', '、']:
                idx = truncated.rfind(punct)
                if idx > TWEET_CHAR_LIMIT // 2:
                    truncated = truncated[:idx + 1].strip()
                    break
            if truncated:
                tweets.append(truncated)
    return tweets[:NUM_CANDIDATES]


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """複数RSSから最新見出しを収集（タイトル + URL）"""
    results: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; x-automation-bot/1.0)"}
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=headers)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    results.append({"title": title, "url": link})
        except Exception:
            continue
        if len(results) >= max_items:
            break
    return results[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + バズパターン + 過去実績から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_note = f"\n- 文末にNote URL: {note_url}" if note_url else ""
    today = date.today().strftime("%Y年%m月%d日")

    prompt = f"""今日（{today}）のX投稿を{NUM_CANDIDATES}案、番号付きリスト（1. 2. 3.）で出力してください。

以下のNote記事を元にしつつ、上記のバズるパターンを3案それぞれ異なるパターンで使ってください。

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 3案それぞれで異なるバズパターンを使う（A〜Gから選択）
- ビジネスパーソンに刺さる言葉選び{link_note}
- ハッシュタグは1〜2個まで
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュース + バズ分析から高エンゲージメント投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    today = date.today().strftime("%Y年%m月%d日")

    prompt = f"""今日（{today}）のX投稿を{NUM_CANDIDATES}案、番号付きリスト（1. 2. 3.）で出力してください。

以下の最新AIニュースから最も注目すべきトピックを1つ選び、
上記のバズるパターンを使って3案作成してください。

ルール:
- 各投稿は140文字以内
- 3案それぞれで異なるバズパターン（A〜G）を使う
- 医療×AI・社会変革・未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 選んだニュースの理由を冒頭1行で添える（投稿文とは別に）

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿を生成"""
    today = date.today().strftime("%Y年%m月%d日")
    prompt = f"""今日（{today}）のオリジナルAI洞察投稿を{NUM_CANDIDATES}案、番号付きリスト（1. 2. 3.）で出力してください。

ルール:
- 各投稿は140文字以内
- 3案それぞれで異なるバズパターン（A〜G）を使う
- Claude・GPT・医療AI・AIと社会変革などのテーマを優先
- 2026年の最新AIトレンド（エージェントAI・マルチモーダル・AI規制）を意識する
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def suggest_images(posts: list[str]) -> list[str]:
    """各投稿の内容に合ったUnsplash/Pixabay検索キーワードを提案"""
    keywords: list[str] = []
    for post in posts:
        if any(w in post for w in ["医療", "病院", "診断", "患者"]):
            keywords.append("medical AI doctor technology")
        elif any(w in post for w in ["データ", "ブロックチェーン", "セキュリティ"]):
            keywords.append("blockchain data network digital")
        elif any(w in post for w in ["未来", "変革", "革命", "2027", "3年"]):
            keywords.append("future technology innovation abstract")
        elif any(w in post for w in ["仕事", "業務", "効率", "自動化"]):
            keywords.append("AI robot automation workplace")
        elif any(w in post for w in ["問い", "哲学", "感情", "人間"]):
            keywords.append("human AI coexistence philosophy")
        else:
            keywords.append("artificial intelligence business neural network")
    return keywords
