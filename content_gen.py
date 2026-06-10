"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語：AI×ビジネス
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+企業活用&hl=ja&gl=JP&ceid=JP:ja",
    # 日本語：最新モデル・サービス発表
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+Grok+最新+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 日本語：AI×医療・DX
    "https://news.google.com/rss/search?q=AI+医療+DX+ヘルスケア&hl=ja&gl=JP&ceid=JP:ja",
    # 日本語：生成AI活用事例
    "https://news.google.com/rss/search?q=生成AI+活用事例+自動化+効率化&hl=ja&gl=JP&ceid=JP:ja",
    # LedgeAI（日本語AI専門メディア）
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280  # X現行制限（日本語も280文字）
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大テーマ
- スイス大学研究・国連会議参加のグローバル視点
- Claude Codeなど最先端AIツールを実務で活用
- 専門知識を「問い」として届けるスタイル
- 押しつけず、静かに鋭い洞察を放つ
"""

TWEET_STRATEGY = """
## ビジネス層にバズるAI投稿の型（この順で各案を作れ）

### 型1：数字インパクト型
具体的な%・時間・コストで現実感を出す。
例：「AI導入企業の72%が6ヶ月でROIを回収。未導入企業との差は3年後に決定的になる。」

### 型2：逆張り・反常識型
常識を疑わせてリプ・RTを誘発する。
例：「AIで一番危ないのは『使いすぎ企業』ではなく、いまだ『検討中企業』だ。」

### 型3：FOMO型（競合への恐怖）
「競合はもうやっている」で危機感を刺激する。
例：「あなたの業界の上位20%はもうAIで○○を自動化している。気づいていますか？」

### 型4：問いかけ型（コメント誘発）
答えたくなる開かれた問いで滞在時間を伸ばす。
例：「5年後、あなたの仕事の何%がAIに置き換わると思いますか？」

### 型5：最新情報＋独自解説型
速報性＋著者の視点で差別化する。
例：「今日発表された○○、表面的な機能より『なぜこのタイミングか』が本質。医療で考えると——」

## 文体ルール
- 体言止め多用でテンポよく
- 改行でリズムを作る（ただし1ツイートは1行で出力）
- ハッシュタグは末尾に1〜2個（#AI #生成AI #医療AI #DX から選択）
- 絵文字は0〜1個（なくてもよい）
- 各投稿は280文字以内（URLは23文字換算）
"""

VIRAL_EXAMPLES = """
## 参考：実際に高エンゲージメントを記録した日本語AIツイートの型

「ChatGPTが登場してから、AIに仕事を奪われる恐怖より、AIを使いこなせない人間が仕事を失う現実の方が遥かにリアルになってきた。」

「AI導入した企業と、様子見を続けた企業の差は5年後に見えてくる。でも5年後では手遅れかもしれない。」

「医師の仕事でAIが最初に変えるのは診断精度ではなく、カルテを書く時間だ。浮いた時間で何をするか、それが医師の価値を決める。」

「生成AIで真っ先に変わるのは『誰でもできる仕事』ではなく、『誰もやりたくない仕事』だと思う。」

「経営者がAIを使わない理由No.1は『まだ様子を見ている』。競合も同じことを言っていた1年前を思い出してほしい。」
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し280文字以内に絞る"""
    tweets = []
    # 番号付きブロックに分割（1. / 1) / 【案1】 形式に対応）
    blocks = re.split(r"\n(?=(?:\d+[\.\)]|\【案\d+\】))", raw)
    for block in blocks:
        text = re.sub(r"^(?:\d+[\.\)]|\【案\d+.*?\】)\s*", "", block.strip())
        text = text.strip()
        if text and 10 < len(text) <= MAX_TWEET_LENGTH:
            tweets.append(text)

    # フォールバック：単純な行ごと抽出
    if not tweets:
        for line in raw.splitlines():
            line = line.strip()
            cleaned = re.sub(r"^(?:\d+[\.\)]|\【.*?\】)\s*", "", line).strip()
            if cleaned and 10 < len(cleaned) <= MAX_TWEET_LENGTH:
                tweets.append(cleaned)

    return tweets


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 投稿末尾にNoteリンクを1案で入れてよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を元に、ビジネス層に刺さる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

## 出力フォーマット
各案を以下の形式で出力してください（必ず1案1行、番号付き）:
1. [ツイート本文（280文字以内）]
2. [ツイート本文（280文字以内）]
...

制約:
- 各案は各型（数字・逆張り・FOMO・問いかけ・最新情報）を1つずつ使う
- 1案は必ず1行に収める（改行禁止）
- ハッシュタグは各案の末尾に1〜2個{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから最新ニュースをタイトル＋リンク付きで取得"""
    items: list[dict] = []
    seen_titles: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue
    return items[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースから投稿案を生成。(投稿リスト, 選択ニュースタイトル) を返す"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースの中から最もビジネス層に刺さるトピックを1つ選び、
{NUM_CANDIDATES}案のX投稿を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

## 出力フォーマット
まず選んだニュースを「選択ニュース:」で1行示し、その後に:
1. [ツイート本文（280文字以内）]  # 数字インパクト型
2. [ツイート本文（280文字以内）]  # 逆張り・反常識型
3. [ツイート本文（280文字以内）]  # FOMO型
4. [ツイート本文（280文字以内）]  # 問いかけ型
5. [ツイート本文（280文字以内）]  # 最新情報＋独自解説型

制約:
- 医療・社会変革・未来への洞察を絡めると尚よい
- 1案は必ず1行に収める（改行禁止）

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)

    # 選択ニュースタイトルを抽出
    selected_news = ""
    for line in raw.splitlines():
        if line.startswith("選択ニュース:"):
            selected_news = line.replace("選択ニュース:", "").strip()
            break

    tweets = _extract_tweets(raw)
    return tweets, selected_news


def _generate_original_ai_insight() -> tuple[list[str], str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトレンドについて、
ビジネス層に刺さる{NUM_CANDIDATES}案のX投稿を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

## 出力フォーマット
1. [ツイート本文（280文字以内）]  # 数字インパクト型
2. [ツイート本文（280文字以内）]  # 逆張り・反常識型
3. [ツイート本文（280文字以内）]  # FOMO型
4. [ツイート本文（280文字以内）]  # 問いかけ型
5. [ツイート本文（280文字以内）]  # 最新情報＋独自解説型

優先テーマ: AI×医療変革、AGIへの道筋、AI×経営戦略、エージェントAI
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw), "オリジナル洞察"


def suggest_image(tweet: str) -> str:
    """ツイート内容から添付画像のアイデアを提案"""
    keywords = {
        "医療": "医療AIのデータビジュアル or 病院×テクノロジーのイメージ",
        "数字": "グラフ・統計データのスクリーンショット",
        "競合": "市場シェアグラフ or 企業比較チャート",
        "経営": "ビジネスインフォグラフィック",
        "GPT|Claude|Gemini|Grok": "AIモデル比較スクリーンショット",
        "自動化": "ワークフロー自動化のフロー図",
    }
    for kw_pattern, suggestion in keywords.items():
        if re.search(kw_pattern, tweet):
            return suggestion
    return "AI×ビジネスの抽象的なビジュアル（Unsplash: ai technology business）"
