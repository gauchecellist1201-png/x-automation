"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語：AIビジネスニュース
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+Claude+ビジネス+経営&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=人工知能+DX+日本企業+コスト削減&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI+発表&hl=ja&gl=JP&ceid=JP:ja",
    # 英語：最新海外AIニュース（速報）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=LLM+GPT+Claude+business+productivity&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
URL_CHAR_COUNT = 23  # X はURLを23文字として計算
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け・X最適化）

### 強力なフックパターン（最初の50文字が命）
1. 数字インパクト型: 「〇〇%削減」「〇〇万円の差」「〇倍の生産性」で始める
2. 逆張り型: 「多くの人が誤解している」「実は逆効果」「知られていない真実」
3. 緊急性型: 「今すぐ知るべき」「2年後には手遅れ」「気づいていない人が多い」
4. 問い型: 「あなたの会社は大丈夫か？」「なぜ日本企業だけが〇〇？」
5. 速報型: 「【速報】」「〇〇が明らかに」「新研究で判明」
6. 体験型: 「医学部でAIを使ったら」「実際に試した結果」「プロが驚いた理由」

### ビジネス層が最も反応するテーマ（優先度順）
★★★: AI×業務効率化、AI×コスト削減、AI×雇用・キャリア、競合他社のAI活用
★★: 日本企業のAI活用実態、AI規制・法律動向、医療AI革命
★: AIの哲学的問い（月に一度くらい入れると深みが出る）

### バズるツイート構造（どれか1つを選ぶ）
A) 衝撃数字フック → 具体内容1-2行 → 「あなたの会社はどう動く？」
B) 問いかけ → 鋭い洞察2行 → ハッシュタグ
C) 速報フック → 内容 → 医療・ビジネスへの独自示唆
D) 逆張り主張 → 根拠 → 締め・問い

### 文体・形式ルール
- 断言する（「〜かもしれない」→「〜だ」「〜になる」「〜は変わった」）
- 改行を効果的に使う（2〜4行が理想）
- ハッシュタグは #AI #生成AI #DX のうち1〜2個まで
- URLは含めない（自動で追加される）
- 最後は問いかけ or 強いメッセージで締める
- 静かな熱量、押しつけがましくない洞察
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_chars: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きブロックからツイートを抽出（複数行対応）"""
    lines = raw.strip().splitlines()

    # 番号付き行の開始位置を検出
    tweet_starts: list[int] = []
    for i, line in enumerate(lines):
        if re.match(r'^\d+[\.\)]\s+\S', line.strip()):
            tweet_starts.append(i)

    if tweet_starts:
        tweets = []
        for idx, start in enumerate(tweet_starts):
            end = tweet_starts[idx + 1] if idx + 1 < len(tweet_starts) else len(lines)
            block = "\n".join(lines[start:end]).strip()
            text = re.sub(r'^\d+[\.\)]\s*', '', block).strip()
            # 末尾の空行を除去
            text = "\n".join(l for l in text.splitlines()).rstrip()
            if text and len(text) <= max_chars:
                tweets.append(text)
        return tweets[:NUM_CANDIDATES]

    # フォールバック: 単一行パターン
    fallback = []
    for line in lines:
        text = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
        if text and len(text) <= max_chars and re.match(r'^\d+', line.strip()):
            fallback.append(text)
    return fallback[:NUM_CANDIDATES]


def fetch_rss_items(max_items: int = 10) -> list[dict]:
    """RSSからニュースタイトルとURLを取得"""
    items: list[dict] = []
    seen_titles: set[str] = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[dict]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    max_body = MAX_TWEET_LENGTH - URL_CHAR_COUNT - 2 if note_url else MAX_TWEET_LENGTH

    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は{max_body}文字以内（URLは含めない、後で自動追加）
- 番号付きリスト（1. 2. 3.）で出力。各ツイートは独立したブロック
- AIに関するビジネス層への洞察を、刺さる言葉で
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    texts = _extract_tweets(raw, max_body)
    return [{"text": t, "url": note_url} for t in texts]


def generate_posts_from_rss() -> list[dict]:
    """最新AIニュースから戦略的ツイートを生成。{text, url} のリストを返す。"""
    items = fetch_rss_items()
    if not items:
        texts = _generate_original_ai_insight()
        return [{"text": t, "url": ""} for t in texts]

    max_body = MAX_TWEET_LENGTH - URL_CHAR_COUNT - 2
    headlines_text = "\n".join(f"{i+1}. {item['title']}" for i, item in enumerate(items[:6]))
    top_url = items[0]["url"]

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は{max_body}文字以内（URLは後で自動追加されるため含めない）
- 番号付きリスト（1. 2. 3.）で出力。各ツイートは独立したブロックに
- 医療×AI×ビジネスの視点を絡めると尚良い
- ビジネスパーソンが「これは知らなかった」「シェアしたい」と感じる内容に
- 3案それぞれ異なるフックパターンを使う

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    texts = _extract_tweets(raw, max_body)
    return [{"text": t, "url": top_url} for t in texts]


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は{MAX_TWEET_LENGTH}文字以内
- 番号付きリスト（1. 2. 3.）で出力。各ツイートは独立したブロック
- Claude・GPT・医療AI・AIと社会変革などのテーマを優先
- 2026年現在の最新AI動向・ビジネス環境を踏まえること
- 3案それぞれ異なるフックパターンを使う
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
