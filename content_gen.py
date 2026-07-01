"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
目的: ビジネス層へのAI情報発信・フォロワー獲得
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # ビジネス×AI日本語ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+企業+活用+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+業務効率化+DX+コスト削減&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業+日本&hl=ja&gl=JP&ceid=JP:ja",
    # 医療×AI
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI+診断AI&hl=ja&gl=JP&ceid=JP:ja",
    # AI専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140  # 日本語140文字 = X換算280ウェイト文字（上限）
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議参加のグローバル視点
- Claude Codeなど最新AIツールを自ら使いこなす実践者
- ターゲット読者：AIに興味を持つビジネスパーソン・経営者・スタートアップ
- スタイル：専門的だが親しみやすく、「今すぐ使える視点」を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層フォロワー獲得）

### 最強フックの型（最初の1行で勝負が決まる）
- 【数字型】「住友商事が12億円削減した方法」「生産性40%差の理由」
- 【意外性型】「AIにできないと思ってた○○が、もうできる」
- 【警告型】「AIを使わない会社が2026年末に直面すること」
- 【問いかけ型】「あなたの仕事、AIに置き換えられる側？使う側？」
- 【インサイダー型】「AI業界にいないと知らない、今週一番重要なニュース」

### 本文の5原則
1. **具体的な数字・社名・事例**を必ず1つ入れる（信頼性UP）
2. **ビジネスインパクト**（ROI・コスト・時間・競合優位）に絡める
3. **読者への問い**で終わるとRT率が上がる
4. 140文字以内に収める（URLは23文字換算）
5. ハッシュタグは #AI #生成AI #DX から1〜2個まで

### バズる構造パターン
- 事実（数字）→ 洞察（なぜ重要か）→ 問い（あなたは？）
- 驚き → 納得 → 共有したくなる締め
- 業界の常識を壊す → 新しい視点を提示

### 避けること
- 抽象的な表現（「AIが変える未来」→ NG）
- 結論のない羅列（具体例なしの「AIは便利」→ NG）
- 長すぎる説明（ツイートはコピーで勝負）
"""

AI_BUSINESS_DATA_2026 = """
## 2026年最新AI×ビジネスデータ（投稿に活用）
- 住友商事：Microsoft 365 Copilotを8,800人導入 → 年間12億円コスト削減
- パナソニック コネクト：AI「ConnectAI」 → 1年で18.6万時間の労働削減
- AI投資ROI：平均3.7倍／トップ企業は10.3倍（Google Cloud調査）
- AI活用格差：最活用企業は最低活用企業より生産性40%高い
- 横河電機×JSR：AIによる化学プラント自律制御35日間連続（世界初）
- Claude（Anthropic）：1四半期で月次訪問数4倍（2億→8.2億）成長
- AIチャットボット市場シェア：ChatGPT 54.7%、Gemini 27.4%、Claude 8.2%
- 企業のAI主要目標：業務効率化34%、社員生産性33%、新規ビジネス23%
- 2026年AI支出優先事項1位：ワークフロー最適化（企業の42%）
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感・フックを参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{AI_BUSINESS_DATA_2026}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで（#AI #生成AI #DX #医療AI から選ぶ）
- 必ずフックで始める（数字・意外性・問いかけのどれか）
- 具体的な数字や事実を含める{link_instruction}
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
    """最新AIトレンドニュースを元に、ビジネス層に刺さる意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最もビジネス層に刺さるトピックを1つ選び、
バズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{AI_BUSINESS_DATA_2026}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 必ずフックで始める（数字・意外性・問いかけのどれか）
- ビジネス層が「RT したい」「保存したい」と思う内容に
- ハッシュタグは1〜2個まで（#AI #生成AI #DX から選ぶ）
- 医療×AI、社会変革のテーマは特に優先する

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI×ビジネスで最も重要なトピックについて、
ビジネス層がRTしたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{AI_BUSINESS_DATA_2026}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 上記の「2026年最新AI×ビジネスデータ」を必ず1つ以上活用する
- 数字・具体的事例・問いかけを含める
- テーマ例：AI投資ROI、医療AI、生産性格差、Claude/GPT/Gemini競争
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
