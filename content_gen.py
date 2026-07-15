"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic
from datetime import date

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+医療AI+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議参加のグローバル視点
- 課題解決志向、専門知識を持ちながら読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（2026年版）

### フックの鉄則（最重要）
- 1行目（フック）が成功の80〜90%を決める
- 「え、そうなの？」「これは知らなかった」と3秒で止まらせる
- 数字・反常識・対比・固有名詞を使う
- 例: 「医師がコードを1行も書かずにAIを作った」

### 構造（3〜5行がベスト）
- 改行でテンポを作る（1改行＝1アイデア）
- 結論より「問い」で終わる → リプライが激増
  ※2026年Xアルゴリズム: リプライ1件 ≈ いいね150件相当
- 空行を使って視覚的にテンポを作る

### トーン
- 医師×AI起業家らしい専門×洞察のバランス
- 驚き・危機感・問いを静かに込める
- ビジネス層に刺さる言語感覚（難解でなく深い）

### タグ・リンク
- ハッシュタグは1〜2個まで（#AI #生成AI #医療DX から選択）
- NoteリンクはURL換算23文字として文末に入れる
"""

TRENDING_CONTEXT = f"""
## {date.today().strftime("%Y年%m月%d日")}の最重要AIトレンド（積極的に活用する）
- Claude Sonnet 5リリース済み：Opus 4.8に迫る性能・低価格・エージェント特化（最注目）
- AIエージェントのコスト問題が解消 → 企業採用が一気に加速
- Five Eyes諜報同盟「フロンティアAIは数ヶ月内に業界予想を超える」と正式警告
- 中国AIラボ急成長：DeepSeekが技術的リーダーとしてグローバルにリスペクトされる存在に
- 医師がコードを書かずに医療AIを構築できる時代（Claude Code等で現実化）
- AIエージェントによる医療ワークフロー自動化（書類・データ確認・例外処理）が商用化
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_best_tweet(raw: str) -> list[str]:
    """番号付きブロックから投稿文を抽出（改行含む複数行対応）"""
    parts = re.split(r"(?m)^(\d+[\.\)]\s*)", raw.strip())
    tweets = []
    for i in range(2, len(parts), 2):
        text = parts[i].strip()
        # 空行区切りのブロック先頭だけ取る（次の候補が混入しないよう）
        text = re.split(r"\n{3,}", text)[0].strip()
        if text and len(text) <= MAX_TWEET_LENGTH:
            tweets.append(text)
    return tweets[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感・改行スタイルを再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい（URL換算23文字）: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。
バズりやすさ順（1番目が最もバズる）で出力すること。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TRENDING_CONTEXT}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 改行を活用して読みやすいフォーマットにする
- 1行目のフックを最重要視する{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
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
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。
バズりやすさ順（1番目が最もバズる）で出力すること。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TRENDING_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 改行でテンポを作る
- 1行目のフックを最重要視する
- 医療×AI・社会変革・未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。
バズりやすさ順（1番目が最もバズる）で出力すること。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TRENDING_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 改行でテンポを作る
- 1行目のフックを最重要視する
- Claude Sonnet 5・AIエージェント・医療AI・社会変革のテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
