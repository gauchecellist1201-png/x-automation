"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+AGI+マルチモーダル&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（最前線情報）
    "https://news.google.com/rss/search?q=AI+LLM+Claude+OpenAI+Gemini+2026&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大テーマに活動
- スイス大学研究・国連会議参加などグローバル視点を持つ
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- Claude Codeなど最新AIツールを実際に業務活用している
"""

VIRAL_PATTERNS = """
## バイラルツイートの型（ビジネス層に刺さる6パターン）

【型1】数字インパクト型 ─ 具体的な数値・割合・期間で止まらせる
例: 「ChatGPT活用企業の42%が業務コスト30%削減。残り58%との差は使い方でなく"問い方"だった。」

【型2】逆張り洞察型 ─ 常識を静かにひっくり返す
例: 「AIに仕事を奪われる、は正確ではない。正確には"AIを使いこなす人に奪われる"。その差は今この瞬間も開いている。」

【型3】問いかけ型 ─ 答えでなく「問い」で終わり、RTを誘発
例: 「AIが診断を下す時代、医師の価値は何に移るのか。技術でも知識でもなく──」

【型4】最速解説型 ─ 今日の重大ニュースを自分の言葉で3行要約
例: 「Anthropicが○○を発表。医療への影響を一言で言うと── [具体的洞察]。#AI」

【型5】リスト型 ─ 明日から使える知識を箇条書きで届ける
例: 「AIで差がつく3点：①問いの解像度 ②出力の検証習慣 ③人間にしかできない判断の見極め。保存推奨」

【型6】ストーリー型 ─ 個人体験から普遍的教訓へ昇華
例: 「医学部の勉強にAIを使い始めて気づいた。驚いたのは答えの質ではなく、問い方そのものが変わったこと。」
"""

TWEET_STRATEGY = """
## 投稿戦略ルール
- 80〜140文字が理想（短すぎても長すぎても伸びない）
- 数字・固有名詞・「〜だった」「〜になる」などの断言がスクロールを止める
- ハッシュタグは #AI または #生成AI のうち1個だけ（スペース節約）
- リンクは文末に付ける（URLは23文字換算）
- 「保存推奨」は書かない（それでも保存されるように書く）
- ビジネス層（経営者・スタートアップ・医療従事者）が「これは知っておくべき」と思える内容
"""


def _call_claude(prompt: str, max_tokens: int = 1024) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出する（複数行ツイートも対応）"""
    tweets: list[str] = []
    current_lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_lines:
                tweet = " ".join(current_lines).strip()
                tweet = re.sub(r"^\d+[\.\)]\s*", "", tweet)
                if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current_lines = [stripped]
        elif stripped and current_lines:
            current_lines.append(stripped)

    if current_lines:
        tweet = " ".join(current_lines).strip()
        tweet = re.sub(r"^\d+[\.\)]\s*", "", tweet)
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets[:NUM_CANDIDATES]


def select_best_tweet(candidates: list[str]) -> str:
    """Claude に3案を評価させ、最もバズりそうな1案を返す"""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下はXの投稿候補です。ビジネス層（経営者・スタートアップ・医療従事者）への
バイラル効果が最も高いと予測される案を1つだけ選んでください。

{numbered}

判断基準:
- スクロールを止める力（冒頭の引力）
- 「知らなかった」「考えさせられた」感
- RT・いいねされやすいか
- 140文字以内に収まっているか

出力形式: 選んだ番号（1か2か3）だけを答えてください。理由は不要です。
"""
    result = _call_claude(prompt, max_tokens=8).strip()
    match = re.search(r"[123]", result)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    link_note = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}
{few_shot_section}
追加ルール:
- 各投稿は140文字以内（URLは23文字換算）{link_note}
- 番号付きリスト（1. 2. 3.）で出力
- 説明・解説は不要。番号と投稿本文だけを出力してください

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS から headline + link を取得"""
    items: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "link": link})
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層にバズる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

追加ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、ビジネスへの影響の視点を積極的に入れる
- 単なるニュース紹介でなく「だから何が変わるのか」という洞察を入れる
- 説明・解説は不要。番号と投稿本文だけを出力してください

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界の最前線をテーマに、ビジネス層にバズる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

優先テーマ（どれか1つを深掘り）:
- AIエージェントが業務を自律実行する時代の到来
- Claude・GPT・Geminiの使い分け論
- 医療AIが臨床判断を変える瞬間
- AI民主化と職種格差
- 生成AI活用で生産性3倍になった具体例

説明・解説は不要。番号と投稿本文だけを出力してください。
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
