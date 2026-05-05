"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バイラルパターン分析 + ビジネス層ターゲティング対応版
"""

import os
import re
import json
import feedparser
import anthropic
from viral_patterns import VIRAL_FORMATS, BUSINESS_AI_TOPICS, VIRALITY_SIGNALS, ENGAGEMENT_BOOSTERS

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+エージェント+GPT+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    "https://news.google.com/rss/search?q=artificial+intelligence+business+2026&hl=ja&gl=JP&ceid=JP:ja",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5  # 5案生成→スコアリングで最良1案を選ぶ

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求、グローバル視点（スイス研究、国連参加）
- PHR/EHRへのブロックチェーン活用、非中央集権的医療データ管理を研究
- AIで医師・医学生がコードなしで医療プロダクトを作れる時代を切り開く
- 静かに鋭い洞察を届けるスタイル。押しつけがましくない
- ターゲット読者：AIに関心あるビジネスパーソン・医療関係者・経営者・スタートアップ
"""

TWEET_STRATEGY = """
## バイラル投稿戦略（実績ベース）
1. 冒頭1行が全て：数字・逆張り・「告白」「実は」が止まらせる
2. 具体的な数値・固有名詞（Claude、GPT-5、EU AI法など）を入れる
3. 「医療×AI」「社会変革」の文脈で差別化
4. 結論より「問い」で終わるとリプライ・RTが爆増
5. ハッシュタグは #AI #生成AI のうち最大2個
6. 改行を効果的に使う（壁テキストは読まれない）
7. ビジネス層が「保存したい・シェアしたい」と思う情報密度
"""

VIRAL_FORMAT_GUIDE = "\n".join(
    f"### {name}\n{meta['description']}\n例：\n{meta['example']}\n（理由：{meta['why_viral']}）"
    for name, meta in VIRAL_FORMATS.items()
)

BUSINESS_TOPICS_GUIDE = "\n".join(f"- {t}" for t in BUSINESS_AI_TOPICS)


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    client = _get_client()
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        system=(
            "あなたはXアカウント @GAUCHE_cellist（井出直毅）の専属SNSストラテジストです。"
            "バイラルSNSマーケティングと医療×AIの専門知識を持ちます。"
            "投稿はすべて日本語で、140文字以内の制約を厳守してください。"
        ),
    )
    return message.content[0].text


def _extract_tweets_and_scores(raw: str) -> list[dict]:
    """
    番号付きリストから投稿文とスコアを抽出。
    形式: 1. [投稿文] (スコア: X/10)
    """
    results = []
    # スコア付きパターン
    for match in re.finditer(
        r"^\d+[\.\)]\s*(.+?)(?:\s*[\(（]スコア[：:]\s*(\d+)[/／]10[）\)])?$",
        raw,
        re.MULTILINE,
    ):
        text = match.group(1).strip()
        score_str = match.group(2)
        score = int(score_str) if score_str else 5
        if 0 < len(text) <= MAX_TWEET_LENGTH:
            results.append({"text": text, "score": score})
    return results


def _extract_best_tweet(raw: str) -> list[str]:
    """後方互換: テキストのみのリストを返す"""
    candidates = _extract_tweets_and_scores(raw)
    if candidates:
        return [c["text"] for c in candidates]
    # フォールバック: 単純な番号付きリスト抽出
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def score_and_select_best(candidates: list[str]) -> str | None:
    """
    複数の投稿案をClaudeにバイラリティ評価させ、最高スコアを返す
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates))
    prompt = f"""以下のX投稿案を評価してください。

{VIRALITY_SIGNALS}

## 評価対象の投稿案
{numbered}

## 指示
- 各案に10点満点でスコアをつけてください
- 最後に「最優秀案: X番 (理由: ...)」と明記してください
- ターゲット：AIに関心あるビジネスパーソン・医療関係者
"""
    raw = _call_claude(prompt, max_tokens=800)

    # 最優秀案の番号を抽出
    match = re.search(r"最優秀案[：:]\s*(\d+)番", raw)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]

    # フォールバック: 最初の候補
    return candidates[0]


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

    prompt = f"""以下のNote記事を元に、X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

## バイラルフォーマット（どれか1つを選んで使う）
{VIRAL_FORMAT_GUIDE}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは最大2個
- 必ず異なるフォーマットを使って{NUM_CANDIDATES}案を多様にする
- ビジネス層が「保存・RT」したくなる情報密度{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSフィードからヘッドラインとURLを取得"""
    results: list[dict] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    results.append({"title": title, "url": link})
        except Exception:
            continue
        if len(results) >= max_items:
            break
    return results[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、バイラルな意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}" for it in items)
    top_url = items[0]["url"] if items else ""
    url_instruction = f"\n- 最も重要なニュースのURLを文末に入れてよい: {top_url}" if top_url else ""

    prompt = f"""以下の最新AIニュースから最も注目すべきトピックを1〜2つ選び、
X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

## バイラルフォーマット（どれか使う）
{VIRAL_FORMAT_GUIDE}

## ビジネス層が最も反応するAIトピック（参考）
{BUSINESS_TOPICS_GUIDE}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 異なるフォーマットで{NUM_CANDIDATES}案を多様に
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは最大2個{url_instruction}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""2026年のAI業界で最も重要なトピックについて、
@GAUCHE_cellist らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

## バイラルフォーマット（どれか使う）
{VIRAL_FORMAT_GUIDE}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 異なるフォーマットで{NUM_CANDIDATES}案を多様に
- Claude、GPT、医療AI、AIと社会変革などを優先
- ハッシュタグは最大2個
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def select_best_post(candidates: list[str]) -> str | None:
    """全候補からバイラリティ最高の1案を選ぶ"""
    return score_and_select_best(candidates)
