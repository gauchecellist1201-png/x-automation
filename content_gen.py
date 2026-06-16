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
    "https://news.google.com/rss/search?q=AIエージェント+自律AI+企業DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点（スイス研究、国連会議参加）
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_STRATEGIES = """
## バズる投稿の戦略（X高エンゲージメント分析より）

### 構造パターン（エンゲージメント率の高い順）
1. **逆説的オープナー**: 常識を覆す一文で始める
   例：「AIは医師を奪わない。ただしAIを使う医師に奪われる。」

2. **衝撃の数字＋問い**: 具体的数値+疑問で止まらせる
   例：「AI投資2.5兆ドル、前年比44%増。あなたの会社はどこにいる？」

3. **Before/After構造**: 変化を2行で可視化する
   例：「2023年：AIはオプション。2026年：AIは前提。乗り遅れた企業が静かに消えている。」

4. **一人称の断言**: 専門家としての独自視点で権威を出す
   例：「医学生として確信している。次の10年で医療AIは診断精度で人間を超える。」

5. **問いかけで終わる**: RTとリプライを促す最強の締め
   例：「AIが当たり前になった世界で、あなたの武器は何ですか？」

### ルール
- 最初の一文が命。スクロールを止める引力を持て
- 専門的すぎず、かつ浅くない「ちょうど良い難しさ」
- ハッシュタグは #AI #生成AI のうち最大2個
- 数字・対比・問いのうち最低1つを入れる
- 140文字以内（URLは23文字換算）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
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


def select_best_tweet(candidates: list[str]) -> tuple[str, str]:
    """Claude がバズ可能性でスコアリングして最良のツイートを選ぶ。(tweet, reason) を返す。"""
    if not candidates:
        return "", ""
    if len(candidates) == 1:
        return candidates[0], "唯一の候補"

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿案から最もバズりやすいものを1つ選んでください。

選定基準：
- スクロールを止める引力（最初の一文のインパクト）
- ビジネス層への刺さり度
- RT/いいねを促す構造
- 140文字以内の完成度

投稿案：
{numbered}

回答形式（必ずこの形式で）：
選択：<番号>
理由：<30文字以内>"""

    raw = _call_claude(prompt)
    match = re.search(r"選択[：:]\s*(\d+)", raw)
    reason_match = re.search(r"理由[：:]\s*(.+)", raw)
    reason = reason_match.group(1).strip() if reason_match else ""

    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx], reason

    return candidates[0], reason


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績から戦略的投稿案を生成"""
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
{VIRAL_STRATEGIES}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. ...）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、一般読者にも刺さる言葉で{link_instruction}
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
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に @GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGIES}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3. ...）で出力
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGIES}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3. ...）で出力
- Claude Code、AIエージェント、医療AI、AIと社会変革などのテーマを優先
- 2026年現在の最新トレンドを反映する（Anthropic $30B、Claude Code $2.5B ARR、Gemini 3.5 Flash等）
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
