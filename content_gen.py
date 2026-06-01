"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けバイラルコンテンツに特化
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
import anthropic
from viral_patterns import VIRAL_HOOKS, PROVEN_VIRAL_EXAMPLES, BUSINESS_ANGLES, HASHTAG_SETS

RSS_FEEDS = [
    # 日本語AI・テクノロジーニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+ChatGPT&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+AIエージェント+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+Healthcare+人工知能+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AGI+Claude+Gemini+GPT-5+最新&hl=ja&gl=JP&ceid=JP:ja",
    # 英語ソース（最先端情報）
    "https://news.google.com/rss/search?q=AI+agents+Claude+OpenAI+business+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求（PHR/EHRへのブロックチェーン活用）
- スイス大学での研究経験、国連会議参加のグローバル視点
- Claude Codeなど最新AIツールを実務で活用中
- 「医師がコードを書かずに医療プロダクトを作れる時代」を体現中
- 静かに鋭い洞察を届けるスタイル。押しつけがましくない。
"""

TWEET_STRATEGY = """
## バイラルAI投稿の戦略（ビジネス層向け）

### 冒頭フック（最重要）
最初の1〜2行でスクロールを止める。以下のパターンが有効：
- FOMO系：「これを知らないと5年後に詰みます」
- 数字系：「AIで月200時間を自動化した方法」
- 逆張り系：「AIは仕事を奪わない。AIを使える人間が奪う」
- 問いかけ系：「あなたの会社でAIを業務に使っている人は何%？」

### フォーマット（伸びやすい順）
1. 番号付きリスト（①②③）→ 最も保存・RTされやすい
2. 問い→答え構造 → リプライを誘発
3. Before/After → 共感を生む
4. 1つの鋭い洞察 → RT・いいねされやすい

### ビジネス層に刺さる切り口
- 生産性・ROI（数字で示す）
- 競合優位（先行者利益）
- リスク認識（使わないリスク）
- 医療×AI（専門性の掛け算）

### ルール
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは1〜2個まで（#AI #生成AI を優先）
- 絵文字は1〜2個まで（使いすぎ厳禁）
- 「〇〇します！」「〇〇ですね！」などの軽い表現は避ける
- 問いで終わると RTされやすい
"""

VIRAL_EXAMPLES_SECTION = f"""
## 実際にバズったX投稿の例（この文体・温度感・構造を学ぶ）

{chr(10).join(f"---{chr(10)}{ex}" for ex in PROVEN_VIRAL_EXAMPLES)}
---
"""


def _call_claude(prompt: str, max_tokens: int = 1500) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_numbered_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    tweets = []
    current_lines: list[str] = []
    in_tweet = False

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^[1-9][\.\)]\s+", stripped):
            if current_lines:
                tweet = "\n".join(current_lines).strip()
                if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current_lines = [re.sub(r"^[1-9][\.\)]\s+", "", stripped)]
            in_tweet = True
        elif in_tweet and stripped and not re.match(r"^[1-9][\.\)]\s+", stripped):
            # 複数行ツイートのサポート
            combined = "\n".join(current_lines + [stripped])
            if len(combined) <= MAX_TWEET_LENGTH:
                current_lines.append(stripped)
            # 行が長くなったら現在のものを確定
        elif not stripped and in_tweet:
            pass

    if current_lines:
        tweet = "\n".join(current_lines).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets[:NUM_CANDIDATES]


def _extract_tweets_flexible(raw: str) -> list[str]:
    """柔軟なツイート抽出（番号なしブロックも対応）"""
    tweets = _extract_numbered_tweets(raw)
    if len(tweets) >= NUM_CANDIDATES:
        return tweets

    # 番号付きリストで取れなかった場合、段落で分割
    blocks = [b.strip() for b in re.split(r"\n{2,}", raw) if b.strip()]
    for block in blocks:
        # ヘッダー行を除去
        cleaned = re.sub(r"^[#\*]+.*\n?", "", block).strip()
        if 10 < len(cleaned) <= MAX_TWEET_LENGTH and cleaned not in tweets:
            tweets.append(cleaned)
        if len(tweets) >= NUM_CANDIDATES:
            break

    return tweets[:NUM_CANDIDATES]


def generate_thread(topic: str, news_context: str = "") -> list[str]:
    """スレッド投稿（複数ツイートの連続投稿）を生成"""
    context_section = f"\n## 参考ニュース\n{news_context}" if news_context else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のテーマについて、Xスレッド（連続投稿）を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

## スレッド構成（3〜4ツイート）
1ツイート目：フック（スクロールを止める冒頭。必ず「🧵」か「👇」で続きを示す）
2ツイート目：具体的な内容・データ・洞察
3ツイート目：ビジネス・医療への示唆
4ツイート目（任意）：問いかけ or CTA（フォロー・リプライ誘発）

各ツイートを「===」で区切って出力してください。
各ツイートは140文字以内。

## テーマ
{topic}
{context_section}
"""
    raw = _call_claude(prompt, max_tokens=1000)
    threads = [t.strip() for t in raw.split("===") if t.strip()]
    return [t for t in threads if 10 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            ln for ln in feedback_text.splitlines()
            if ln.strip() and not ln.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを自然に入れる（URLは23文字換算）: {note_url}" if note_url else ""

    hooks_sample = "\n".join(f"- {h}" for h in VIRAL_HOOKS[:6])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{VIRAL_EXAMPLES_SECTION}

## 使えるフックパターン例（冒頭に活用）
{hooks_sample}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- ビジネス層・医療関係者に強く刺さる切り口を選ぶ{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets_flexible(raw)


def _parse_rss_xml(xml_text: str) -> list[dict]:
    """RSS/Atom XMLからタイトルとURLを抽出"""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        # RSS 2.0
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is not None and title_el.text:
                title = re.sub(r"\s+", " ", title_el.text).strip()
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                # Google News のリダイレクト URL をそのまま使用
                items.append({"title": title, "url": link})
        # Atom
        if not items:
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                if title_el is not None and title_el.text:
                    title = re.sub(r"\s+", " ", title_el.text).strip()
                    link = link_el.get("href", "") if link_el is not None else ""
                    items.append({"title": title, "url": link})
    except ET.ParseError:
        pass
    return items


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS から最新ヘッドラインをタイトル・URL付きで取得"""
    headlines: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)"}

    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            for item in _parse_rss_xml(resp.text):
                title = item["title"]
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    headlines.append(item)
        except Exception:
            continue

    return headlines[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成。
    Returns: (投稿候補リスト, 採用したニュースのURL)
    """
    items = fetch_rss_headlines()

    if not items:
        posts = _generate_original_ai_insight()
        return posts, ""

    headlines_text = "\n".join(f"- {it['title']}" for it in items)
    hooks_sample = "\n".join(f"- {h}" for h in VIRAL_HOOKS[:8])
    business_angles = "\n".join(f"- {a}" for a in BUSINESS_ANGLES)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{VIRAL_EXAMPLES_SECTION}

## 使えるフックパターン（冒頭に活用）
{hooks_sample}

## ビジネス層への切り口（どれか1つを選んで使う）
{business_angles}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、ビジネス競争優位の視点を優先
- ハッシュタグは1〜2個まで
- 単なるニュース要約ではなく、井出直毅の「洞察・意見」として書く

## 今日の最新AIニュース（最も重要なものを選ぶ）
{headlines_text}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets_flexible(raw)

    # 採用ニュースのURLを返す（最初のものを代表として使用）
    top_url = items[0]["url"] if items else ""
    return tweets, top_url


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    hooks_sample = "\n".join(f"- {h}" for h in VIRAL_HOOKS[:5])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さる深い洞察のX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

{VIRAL_EXAMPLES_SECTION}

## 使えるフックパターン
{hooks_sample}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- AIエージェント、医療AI、AIと雇用、日本企業のAI対応などのテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets_flexible(raw)


def generate_image_prompt(tweet_text: str) -> str:
    """ツイートに添付する画像のDALL-Eプロンプトを生成（オプション機能）"""
    prompt = f"""以下のX投稿に添付する画像のプロンプト（英語）を1文で生成してください。
スタイル：ミニマル、プロフェッショナル、ビジネス向け、グラデーション背景

投稿文：{tweet_text}

出力：英語の画像生成プロンプト1文のみ"""
    return _call_claude(prompt, max_tokens=100)
