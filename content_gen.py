"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズ特化・ビジネス層ユーザー獲得特化版
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass
from datetime import date

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+OpenAI+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+AGI+医療AI+経営AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=人工知能+ビジネス活用+AI自動化+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+breakthrough+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_SINGLE_TWEET = 140
MAX_THREAD_TWEET = 280
NUM_CANDIDATES = 3


@dataclass
class TweetContent:
    tweets: list[str]
    is_thread: bool = False
    topic: str = ""

    @property
    def preview(self) -> str:
        t = self.tweets[0] if self.tweets else ""
        return t[:50] + "..." if len(t) > 50 else t


AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- スイス研究・国連会議参加経験、グローバル視点
- Claude Codeなど最新AIツールを日常的に実践活用
- 課題解決志向。押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

VIRAL_STRATEGY = """
## ビジネス層に刺さるバズ投稿の7パターン

**パターン1 - 衝撃数字型**
「[驚きの統計]。でも[逆説的現実]。この差が[社会的問題]を生む。」
例：「GPT-4の診断精度が放射線科医を超えた領域がある。でも日本でAIを活用している医師は数%。この格差が次の医療格差を生む。」

**パターン2 - 常識破壊型**
「[一般的な誤解]と思ってる人へ。本当は[反直感的事実]。」
例：「AIに仕事を奪われると怖がってる経営者へ。本当に怖いのはAIを使わない競合他社です。」

**パターン3 - 対比タイムライン型**
「[年]：〇〇\n[年]：〇〇\n[年]：？\n準備している人だけが[ベネフィット]を手にする。」

**パターン4 - 問いかけ型（エンゲージメント最高）**
「[ターゲットへの直接的な質問]？\nもし[No/Yes]なら、[次にすべきこと]を話す。」

**パターン5 - リスト型（保存率UP）**
「[テーマ]を変える[N]つのこと：\n①[具体例1]\n②[具体例2]\n③[具体例3]\n知ってた？」

**パターン6 - 個人ストーリー型（共感・RT狙い）**
「[個人的な転換点の一言]。\n[詳細・学び]\n[普遍的なメッセージ]」

**パターン7 - 予言・予測型（フォロー率UP）**
「[近い未来の具体的な予測]。\n今これを知っている人だけが[大きなメリット]を得る。」

## バズる投稿の共通法則
- 最初の1文で指が止まるフック（驚き・数字・逆説・強い問い）
- ビジネス層（経営者・医療従事者・テック関心層）に「自分ごと」として読ませる
- 「保存したい」「RTしたい」と思わせる情報密度
- 曖昧にしない。強い意見・断言を持つ
- ハッシュタグは1〜2個、末尾に自然に入れる
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


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


def _extract_numbered_tweets(raw: str, max_len: int = 140) -> list[str]:
    """番号付きリストから投稿文を抽出（改行を含む複数行ツイート対応）"""
    tweets: list[str] = []
    current_lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_lines:
                tweet = "\n".join(current_lines).strip()
                if 0 < len(tweet) <= max_len:
                    tweets.append(tweet)
            current_lines = [re.sub(r"^\d+[\.\)]\s+", "", stripped)]
        elif stripped and current_lines:
            current_lines.append(stripped)

    if current_lines:
        tweet = "\n".join(current_lines).strip()
        if 0 < len(tweet) <= max_len:
            tweets.append(tweet)

    return tweets


def _extract_thread_parts(raw: str) -> list[str]:
    """--- 区切りでスレッドのツイートパーツを抽出"""
    parts = re.split(r"(?:---+|\[TWEET\s*\d+\]|\[ツイート\s*\d+\])", raw, flags=re.IGNORECASE)
    result = []
    for part in parts:
        text = part.strip()
        if text and 10 < len(text) <= MAX_THREAD_TWEET:
            result.append(text)
    return result


def generate_viral_single_posts(headlines: list[str], feedback_text: str = "") -> list[TweetContent]:
    """最新AIニュースからバズ特化の単発投稿を3案生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感で）\n{examples}\n"

    headlines_text = "\n".join(f"- {h}" for h in headlines[:8])
    today = date.today().strftime("%Y/%m/%d")

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿ライターです。
今日({today})の最新AIニュースから最も注目すべきトピックを選び、
Xでバズる単発投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}
{few_shot}
## 制約
- 各投稿は**正確に140文字以内**（URLを含む場合は23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは末尾に1〜2個まで
- 医療・ビジネス・社会変革の視点を必ず絡める
- 曖昧な表現や平凡な「ですます」調の文章は禁止
- 最初の1文が全て。スクロールが止まる強いフックを必ず入れる
- 7つのパターンのうち、それぞれ異なるパターンを使うこと

## 今日の最新AIニュース
{headlines_text}

各投稿案を番号付きリストで出力してください。説明・前置き不要。投稿文のみ。
"""
    raw = _call_claude(prompt)
    tweets = _extract_numbered_tweets(raw, MAX_SINGLE_TWEET)
    return [TweetContent(tweets=[t], is_thread=False, topic="AI") for t in tweets]


def generate_viral_thread(headlines: list[str], feedback_text: str = "") -> TweetContent | None:
    """最新AIニュースから深掘りスレッドを1本生成（4〜5ツイート）"""
    if not headlines:
        return None

    headlines_text = "\n".join(f"- {h}" for h in headlines[:8])
    today = date.today().strftime("%Y/%m/%d")

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿ライターです。
今日({today})の最新AIニュースから最も重要なトピックを1つ選び、
深掘りスレッド投稿（4〜5ツイート構成）を作成してください。

{AUTHOR_PROFILE}

## スレッド構成ルール
1ツイート目：最強フック（驚き・数字・逆説で指が止まる文章）
2ツイート目：背景・現状の詳細
3ツイート目：医療×AI・社会変革の深い洞察
4ツイート目：ビジネス/医療への具体的な影響
5ツイート目：結論 + CTA（「フォローすると毎日AIの最前線情報を届けます」など）

## 制約
- 各ツイートは**280文字以内**
- ツイートの区切りは必ず「---」を使う
- ハッシュタグは最終ツイートのみに1〜2個
- 医療×AIのプロレベルの洞察をビジネス層にも刺さる言葉で
- 全体を通して一つのストーリーになるよう構成すること

## 今日の最新AIニュース
{headlines_text}

スレッド投稿を出力してください。各ツイートは「---」で区切ること。説明・前置き不要。投稿文のみ。
"""
    raw = _call_claude(prompt)
    thread_parts = _extract_thread_parts(raw)
    if len(thread_parts) >= 2:
        return TweetContent(tweets=thread_parts, is_thread=True, topic="AIスレッド")
    return None


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿ライターです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）{link_instruction}
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 7つのバズパターンのうち異なるものを使うこと
{few_shot_section}
## Note記事本文
{note_text[:4000]}

投稿文のみ出力。説明不要。
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw, MAX_SINGLE_TWEET)


def generate_posts_from_rss() -> list[str]:
    """後方互換性維持: RSS から単発投稿を生成"""
    headlines = fetch_rss_headlines()
    contents = generate_viral_single_posts(headlines)
    return [c.tweets[0] for c in contents if c.tweets]
