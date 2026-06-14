"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AI/テックニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+AIエージェント&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI+DX&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AI最新情報
    "https://news.google.com/rss/search?q=Claude+Anthropic+AI+agent+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Gemini+LLM+enterprise+2026&hl=en&gl=US&ceid=US:en",
    # 専門フィード
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加──グローバル視点
- 課題解決志向、静かに鋭い洞察を届けるスタイル
- 押しつけがましくなく、専門的知識を持ちながら読者に考えさせる問いを投げかける
- ビジネス層・医療従事者・テック系起業家が主な読者層
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）

### フォーマット別に使い分ける
1. 【数字で驚かせる】具体的な統計・データを冒頭に置く
   例「医師の時間の40%がカルテ記載に費やされている。」
2. 【逆説・反常識】「みんな〇〇と思っているが、実は△△」
   例「ChatGPTのシェアが86%→64%に急落。勝者は意外なあそこ。」
3. 【問いで終わる】RTされやすい問いかけ形式
   例「AIを導入した。でも使いこなせているのは23%だけ。あなたの会社はどちら？」
4. 【ストーリー1行】起→結のミニ物語
   例「医学生がコードを書かずに医療AIを作れる時代が来た。これは革命の始まりだと思う。」
5. 【予測・警鐘】未来への洞察
   例「2026年末、企業アプリの40%にAIエージェントが組み込まれる。準備できていない企業は？」

### ビジネス層に刺さるキーワード
- コスト削減・生産性・競争優位・ROI
- 「先行者利益」「取り残されるリスク」
- 具体的な業種・職種への影響（医師・経営者・エンジニア）

### トーン・スタイル
- 短文、体言止め多用、行間で語る
- 感嘆符・絵文字は最小限（1個まで）
- 押しつけず「示唆」する
- 結論より問いで終わるとRTされやすい
- ハッシュタグは #AI #生成AI #医療DX のうち1〜2個まで
"""

HOT_TOPICS_2026 = """
## 2026年6月の最重要AIトピック
- Claude Fable 5 リリース（6/9）：100万トークン、自律エージェント特化、2倍高性能
- AIエージェント：2026年末までに企業アプリの40%に搭載（Gartner予測）
- 医師の40%の時間がカルテ記載に消えている→生成AIで自動化フェーズへ
- ChatGPTのシェア86.7%→64.5%に急落、Geminiが21.5%まで急伸
- 生成AI導入率71.3%だが「使いこなせている」企業は23%のみ
- Moonshot AI（中国・Kimi）が評価額300億ドルで$20億調達へ
- Gartner/McKinsey：AIエージェントを「スケール」できた企業が急増
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
    tweets = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 番号付きリスト行を検出
        m = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if m:
            tweet = m.group(1).strip()
            # 次の行が続きの場合（インデントや記号なし）は結合しない
            if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                tweets.append(tweet)
        i += 1
    return tweets


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    # Note本文中のNOTE_URLを抽出
    if not note_url:
        url_match = re.search(r"NOTE_URL:\s*(https?://\S+)", note_text)
        if url_match:
            note_url = url_match.group(1)

    link_instruction = f"\n- 文末にNoteリンクを自然に入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{HOT_TOPICS_2026}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、解説は不要
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、ビジネス層・一般読者にも刺さる言葉で
- 数字・データがある場合は積極的に使う{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Google Newsの「- メディア名」を除去
                title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{HOT_TOPICS_2026}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、解説は不要
- 医療×AI、社会変革、ビジネス競争優位、未来への問いを絡めると尚良い
- 具体的な数字・データを使うとエンゲージメントが上がる
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年6月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{HOT_TOPICS_2026}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、解説は不要
- 上記のホットトピックから最も刺さるものを選んで投稿案にする
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
