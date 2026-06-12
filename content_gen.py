"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けバズ狙いAI情報発信に特化
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI/ビジネス
    "https://news.google.com/rss/search?q=AI+生成AI+ビジネス+経営&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+自動化+スタートアップ&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルステック+人工知能&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 AI最前線（グローバル視点）
    "https://news.google.com/rss/search?q=AI+enterprise+business+ROI+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+agent+automation+startup+funding&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- スイス研究・国連会議参加など、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_PATTERNS = """
## バズるツイートの構造パターン（ビジネス層向け）

【パターン1: 衝撃データ + 意味づけ】
「[驚くべき数字・事実]。[業界/社会への意味]。[問いかけ]」
例: 「GPT-4が医師国家試験に合格した。これは医師が不要になる合図ではない。AIを使いこなせない医師が不要になる合図だ。」

【パターン2: Before/After 対比（ビジネスインパクト）】
「AI前: [旧状況] → AI後: [新状況]。[インパクト]」
例: 「3年前: 市場調査に3週間 → 今: AIで3時間。この差を活かせている企業とそうでない企業、5年後に大きな差がつく。」

【パターン3: 逆張り洞察（コントラリアン）】
「みんなが[一般論]と言っているが、本当は[真実]だ。」
例: 「"AIに仕事が奪われる"という議論は的外れ。正確には"AIを使えない人の仕事"が奪われる。今すぐ始めるべき理由。」

【パターン4: 予言・未来描写】
「[X年後]、[業界]は[変化]する。その核心は[理由]。今動く人が生き残る。」

【パターン5: スレッド起爆剤（ファーストツイート）】
「[ビッグクレーム]🧵 [具体的な価値提供の予告]」
例: 「AIで売上3倍になった事例を5社分まとめた。共通点は1つだった。🧵」

【パターン6: 共感 + 価値提供 + 驚き】
「[共通の悩み]を持つ人へ。[解決策]。実は[驚きの事実]。」

## 伸びやすい要素
- 数字を具体的に使う（%、倍、万円、時間、人数）
- 「経営者」「起業家」「ビジネスパーソン」を意識したフレーム
- 問いで終わる OR 強い断言で終わる
- 絵文字は1〜2個まで（使いすぎない）
- ハッシュタグは1〜2個（#AI か #生成AI）
- リンク（URL）は文末に自然に配置
"""

TWEET_STRATEGY = """
## 投稿戦略
1. ビジネス層（経営者・起業家・意識高い会社員）が「いいね・RT・保存」したくなる洞察
2. 「知らなかった」「考えさせられた」「使える」と思わせる切り口
3. 具体的な数字・事例・企業名を使う（信頼性UP）
4. 医療・社会変革・スタートアップ視点を絡める
5. スレッド形式（🧵）で詳しく語る導線を作る
"""

OUTPUT_FORMAT = """
## 出力形式（必ずこの形式で出力してください）
1. [ツイート本文（140文字以内）]
IMG: [この投稿に合う画像の説明（英語1文・インフォグラフィックかコンセプトビジュアル）]

2. [ツイート本文（140文字以内）]
IMG: [画像説明]

3. [ツイート本文（140文字以内）]
IMG: [画像説明]
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[dict]:
    """番号付きリストからツイートと画像プロンプトを抽出"""
    results: list[dict] = []
    current_tweet: str | None = None
    current_img = ""

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_tweet:
                results.append({"text": current_tweet, "image_prompt": current_img})
            current_tweet = re.sub(r"^\d+[\.\)]\s+", "", stripped).strip()
            current_img = ""
        elif stripped.startswith("IMG:") and current_tweet is not None:
            current_img = stripped[4:].strip()

    if current_tweet:
        results.append({"text": current_tweet, "image_prompt": current_img})

    return [r for r in results if 0 < len(r["text"]) <= MAX_TWEET_LENGTH + 30]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[dict]:
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
以下のNote記事を読み、ビジネス層がバズらせたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは1〜2個まで
- ビジネス層（経営者・起業家・意識高い会社員）が「いいね・RT・保存」したくなる内容{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def generate_thread_opener(topic: str) -> list[dict]:
    """スレッド起点ツイートを生成（ビジネス層向け高エンゲージメント狙い）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、ビジネス層がスレッドの続きを読みたくなるファーストツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

トピック: {topic}

ルール:
- 各ツイートは140文字以内
- 🧵マークを使い、続きがあることを示す
- ビジネス層が「続きを読みたい！」と思う強いフック
- 具体的な数字や実績を使う

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    posts = _extract_posts(raw)
    for p in posts:
        p["type"] = "thread"
    return posts


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """複数RSSフィードからAIニュースを取得（タイトル＋URL）"""
    results: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    results.append({"title": title, "url": link})
        except Exception:
            continue
    seen: set[str] = set()
    unique: list[dict] = []
    for item in results:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> list[dict]:
    """最新AIトレンドニュースを元に、ビジネス層向けバズ投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {i['title']}  ({i['url']})" for i in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層がバズらせたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- ハッシュタグは1〜2個まで
- 選んだニュースのURLを文末に含めてよい（URLは23文字換算）
- 医療×AI、社会変革、ビジネスインパクトを絡めると尚良い
- 経営者・起業家が「これは重要だ」と感じる切り口で

## 今日の最新AIニュース
{headlines_text}

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def _generate_original_ai_insight() -> list[dict]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層がバズらせたくなる鋭い洞察ツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- ハッシュタグは1〜2個まで
- AIエージェント、医療AI、Claude、AIと経営などのテーマを優先
- ビジネス層（経営者・起業家・意識高い会社員）が「保存・RT」したくなる内容

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)
