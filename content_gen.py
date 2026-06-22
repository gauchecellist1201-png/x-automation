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
    "https://news.google.com/rss/search?q=AIエージェント+企業+自動化&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス研究・国連会議参加、グローバル視点
- 課題解決志向、専門知識を持ちながら読者に考えさせる問いを投げかける
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（2026年最新版）

### 最重要：最初の7語でスクロールを止める
バイラルフックの型：
A) 数字・具体性型：「OpenAIが$1,500億円を投じた理由」
B) 逆張り・反常識型：「AIに仕事を奪われる心配より、AIを使えない人が消える」
C) 好奇心ギャップ型：「医師がAIを怖れている本当の理由を誰も言わない」
D) 体験・告白型：「医学生がコードを書かずにアプリを作れた日のこと」

### エンゲージメント構造
1. 最初の30分で10以上のエンゲージメントが必要 → 刺さる人が即リプするフック
2. 「知らなかった」「考えさせられた」「シェアしたい」を狙う
3. 問いで終わると返信・RTが増える
4. 医療・社会変革・未来への視点を入れると拡散しやすい
5. 数字（$、%、倍）を入れると信頼性と注目度が上がる

### フォーマット
- 140文字以内（URLは23文字換算）
- ハッシュタグは #AI #生成AI #医療DX のうち最大2個
- 改行を使って視覚的に読みやすく（スマホ最適化）
- Noteリンクは文末に自然に
"""

LATEST_AI_CONTEXT = """
## 2026年6月 最新AIトレンド（投稿に活用せよ）
- OpenAI がパートナーネットワーク立ち上げ（$1.5億投資、30万人認定コンサルタント目標）
- Salesforce が AIエージェント企業「Fin」を$36億で買収 → 企業AIエージェント時代の本格到来
- AI は「デモ段階」から「実ビジネス実装」へ移行 → 使える企業と使えない企業の格差が加速
- AI活用企業は非活用企業の1.7倍の成長率 → ビジネスの二極化が始まっている
- 医療AI：診断精度が専門医レベルを超える領域が拡大
- AIエージェントが自律的に業務を実行する時代が来た
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
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感・フック構造を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{LATEST_AI_CONTEXT}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは最大2個
- 必ず強いフックから始める（最初の7語でスクロールを止める）
- AIに関するプロレベルの洞察を、ビジネス層・医療関係者にも刺さる言葉で{link_instruction}
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
以下の最新AIニュースから最も注目すべきトピックを1〜2個選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{LATEST_AI_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 必ず強いフックから始める（最初の7語でスクロールを止める）
- 医療×AI、社会変革、ビジネスインパクト、未来への問いを絡める
- ハッシュタグは最大2個
- 具体的な数字や事実を入れると信頼性が増す

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年6月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{LATEST_AI_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 必ず強いフックから始める（最初の7語でスクロールを止める）
- AIエージェント、医療AI、企業のAI格差、AIと社会変革などのテーマを優先
- 具体的な数字（$36億、1.7倍など）を使い信頼性を高める
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
