"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    "https://news.google.com/rss/search?q=artificial+intelligence+business+productivity&hl=en-US&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学研究経験、国連会議参加などグローバル視点
- 課題解決志向、専門知識を持ちながら一般読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層ターゲット）

### 伸びやすいフォーマット（優先順）
1. 【数字フック】「〇〇が▲▲%向上」「たった3ステップで〇〇が自動化」
2. 【リスト型】「今すぐ試せるAIツール3選」「知らないと損する〇つの事実」
3. 【カウンター直感】常識を覆す意外な切り口から入る（「実は」「盲点」「誤解」）
4. 【before/after】「以前は〇時間→今は△分」の変化を具体的に示す
5. 【問い型】ビジネスパーソンが「自分ごと」として考えさせる問いで締める

### ビジネス層に刺さるテーマ
- 業務自動化・生産性向上の具体例
- AI活用の競合優位性・格差
- 意思決定を変えるAIの使い方
- 規制・リスク・倫理の最前線
- 医療×AI（差別化ポイント）

### 文体・構成ルール
- 冒頭3〜5文字で興味を引く（「実は」「盲点：」「衝撃」「今日から」）
- 情報密度を140文字ギリギリまで高める
- ハッシュタグは #AI #生成AI のうち1〜2個まで（末尾に置く）
- URLがある場合は文末に自然に入れる（23文字換算）
- 結論より「問い」や「余白」で終わるとエンゲージメントが上がる
"""

THREAD_STRATEGY = """
## バズるスレッド構成（ビジネス層ターゲット）

スレッド4ツイート構成：
- ツイート1（フック）：驚き・数字・問いで読者を引き込む（140文字以内）
- ツイート2（文脈）：なぜ今重要か、背景データを示す（140文字以内）
- ツイート3（洞察）：業界への影響・実務への示唆（140文字以内）
- ツイート4（CTA）：行動喚起または深い問いかけ、URLを含めてもよい（140文字以内）

フォーマット: 各ツイートを「---」で区切って出力すること。
"""


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
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def _extract_thread(raw: str) -> list[str]:
    """「---」区切りからスレッドツイートを抽出し140文字以内に絞る"""
    parts = [p.strip() for p in raw.split("---")]
    return [p for p in parts if 0 < len(p) <= MAX_TWEET_LENGTH]


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

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、ビジネスパーソンにも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 8) -> list[dict]:
    """RSSフィードからヘッドラインを取得。{title, url} のリストを返す。"""
    headlines: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    headlines.append({"title": title, "url": link})
        except Exception:
            continue
    seen: set[str] = set()
    unique: list[dict] = []
    for h in headlines:
        if h["title"] not in seen:
            seen.add(h["title"])
            unique.append(h)
    return unique[:max_items]


def generate_posts_from_rss(viral_examples: list[str] | None = None) -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight(viral_examples)

    headlines_text = "\n".join(f"- {h['title']}  {h['url']}" for h in headlines)

    viral_section = ""
    if viral_examples:
        examples_text = "\n".join(f"- {t}" for t in viral_examples[:5])
        viral_section = f"""
## 参考：最近バズっているAIツイートのパターン（文体・構成を参考に）
{examples_text}
"""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{viral_section}
ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、ビジネス変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 元記事URLを文末に自然に含めてもよい（23文字換算）

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_from_rss(viral_examples: list[str] | None = None) -> list[str]:
    """最新AIニュースを元に4ツイートのスレッドを生成する"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return []

    headlines_text = "\n".join(f"- {h['title']}  {h['url']}" for h in headlines)

    viral_section = ""
    if viral_examples:
        examples_text = "\n".join(f"- {t}" for t in viral_examples[:5])
        viral_section = f"""
## 参考：最近バズっているAIツイートのパターン
{examples_text}
"""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に届く4ツイートのスレッドを作成してください。

{AUTHOR_PROFILE}
{THREAD_STRATEGY}
{viral_section}
## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_thread(raw)


def _generate_original_ai_insight(viral_examples: list[str] | None = None) -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    viral_section = ""
    if viral_examples:
        examples_text = "\n".join(f"- {t}" for t in viral_examples[:5])
        viral_section = f"""
## 参考：最近バズっているAIツイートのパターン
{examples_text}
"""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{viral_section}
ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- AIエージェント、医療AI、ビジネス変革、AIと社会などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
