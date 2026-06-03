"""
Claude API を使った戦略的AI投稿生成モジュール
ターゲット: ビジネス層（経営者・起業家・投資家・テックリーダー）
戦略: バズ投稿によるユーザー獲得
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass

# RSS フィード（AI × ビジネスニュース）
RSS_FEEDS = [
    # 日本語: AI × ビジネス
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+自動化+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+Claude+Gemini+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+スタートアップ+DX+資金調達+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=人工知能+医療+ヘルスケア+活用&hl=ja&gl=JP&ceid=JP:ja",
    # 英語: グローバル最前線
    "https://news.google.com/rss/search?q=AI+enterprise+productivity+breakthrough&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+DeepMind+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+agent+automation+business+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 発信者: @GAUCHE_cellist（井出直毅）
- 医学生 × AI/ブロックチェーン起業家（グローバル視点）
- 医療×テクノロジー融合を追求
- 読者層: 経営者・起業家・VC・テックリーダー（ビジネス層）
- 文体の特徴: 鋭い洞察を平易な言葉で。問いを投げかけ読者に考えさせる。押しつけがましくない
"""

VIRAL_STRATEGY = """
## バズる投稿戦略（ビジネス層・ユーザー獲得目的）

### エンゲージメント最大化フォーマット（優先順位順）
1. **数字インパクト型**: 具体的な数字で即座に価値を伝える
   例: 「議事録作成を週5h→20分に短縮したAI活用法」「導入後3ヶ月でコスト40%削減」

2. **警告・FOMO型**: 乗り遅れへの危機感・競争意識を刺激
   例: 「競合は既にこれをやっている」「5年後に後悔する〇〇をしていない経営者の特徴」

3. **逆説・反直感型**: 意外な真実でシェアを誘発
   例: 「AIで最もコスト削減できているのは大企業ではなく〇〇だった理由」

4. **リスト型**: 保存・ブックマーク・RTを誘発
   例: 「今すぐ使えるAI活用術5選」「ビジネスに革命を起こすAIツール2026年版」

5. **ニュース解説型**: 最新ニュース＋独自ビジネス視点で権威性を付加
   例: 「[ニュース] をビジネス視点で読み解くと: 〇〇と〇〇に注目」

6. **問いかけ型**: リプライ・コメントを誘発
   例: 「あなたの会社でAI導入を阻んでいる本当の障壁は何？」

### 構造テンプレート（効果的な順）
[Hook 1文: スクロールを止める] → [本体: 洞察/データ/具体例] → [締め: 問いかけ or CTA]

### ビジネス層に刺さるキーワード
コスト削減・時間短縮・自動化・競合優位性・ROI・DX・採用・売上向上・意思決定

### ルール
- 280文字以内（URLは23文字換算）
- ハッシュタグは1〜2個のみ: #AI #生成AI #DX から選ぶ
- 絵文字は0〜2個（🔥💡⚠️は効果的）
- 「〜してみました」「〜でした」日記調は厳禁
- 結論より「問い」で終わると拡散しやすい
- 記事URLがある場合は文末に自然に組み込む
"""


@dataclass
class NewsItem:
    title: str
    url: str


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し280文字以内のものを返す"""
    parts = re.split(r'\n\s*\d+[.)]\s+', '\n' + raw)
    tweets = []
    for part in parts[1:]:
        # 最初の段落（二重改行まで）を取得
        text = part.split('\n\n')[0].strip()
        # 内部の改行・連続空白を1スペースに統一
        text = re.sub(r'\s+', ' ', text).strip()
        if 10 < len(text) <= MAX_TWEET_LENGTH:
            tweets.append(text)
    return tweets[:NUM_CANDIDATES]


def fetch_rss_news(max_items: int = 12) -> list[NewsItem]:
    """RSSフィードから最新AIニュースを取得"""
    items: list[NewsItem] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)"}
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url, request_headers=headers)
            for entry in feed.entries[:4]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if title and len(title) > 10 and url:
                    items.append(NewsItem(title=title, url=url))
        except Exception:
            continue
    seen_titles: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        if item.title not in seen_titles:
            seen_titles.add(item.title)
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            ln for ln in feedback_text.splitlines() if ln.strip() and not ln.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_note = f"\n- 文末にNoteリンクを含めること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist の投稿担当AIです。
以下のNote記事を読み、ビジネス層がバズる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は280文字以内（URLは23文字換算）{link_note}
- 番号付きリスト（1. 2. 3.）で1案1行ずつ出力してください
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    return _extract_tweets(_call_claude(prompt))


def generate_posts_from_rss() -> list[str]:
    """最新AIニュースからビジネス層向けバズ投稿を生成"""
    news = fetch_rss_news()
    if not news:
        return _generate_original_ai_insight()

    news_text = "\n".join(f"- {item.title}\n  URL: {item.url}" for item in news)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層が「これは見逃せない」と思うバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で1案1行ずつ出力
- 選んだ記事のURLを文末に含めること（信頼性と誘導のため）
- 英語ニュースの場合でも投稿文は日本語で書くこと

## 今日の最新AIニュース
{news_text}
"""
    return _extract_tweets(_call_claude(prompt))


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿を生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層が「これは見逃せない」と感じるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で1案1行ずつ出力
- テーマ候補: エージェントAI・医療AI・AI×経営判断・LLMのビジネス活用・AIと雇用変革
"""
    return _extract_tweets(_call_claude(prompt))
