"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import random
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Copilot+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_FORMATS = """
## バズりやすい投稿フォーマット（いずれか1つを使う）

【数字・統計型】
例: 「AIを導入した企業の73%が〇〇を経験している。残り27%との違いは1つだった。」
→ 具体的な数字で信頼性UP、続きが気になるフック

【逆説・意外性型】
例: 「AIを使えば使うほど、ある能力が失われていく。医学的に確認された事実。」
→ 「えっ？」と思わせて即エンゲージ

【問いかけ型】
例: 「5年後、あなたの職場にAIが100台導入されたとき、あなたは何をしていますか？」
→ リプ・RT誘発率が最も高いフォーマット

【リスト型】
例: 「経営者が今すぐ使うべきAIツール3選\n① ○○ → 〇〇が自動化\n② ○○ → 〇〇が効率化\n③ ○○ → 〇〇が可能に」
→ 保存率・RT率が高い

【実体験・告白型】
例: 「正直に言います。AIに医療診断を1週間任せてみた結果、想像と全然違いました。」
→ 一人称で親近感、続きが気になる

【未来予測型】
例: 「2030年の医療AIはこうなる。現場医師として言えること。」
→ 権威性 × 未来感でシェアされやすい
"""

TWEET_STRATEGY = """
## 投稿戦略

構成ルール:
1. 最初の1行が全て——スクロールを止める「フック」を必ず入れる
2. 専門的だが難解すぎない言葉選び（中学生でも読める）
3. 医療・社会変革・未来への問いかけを絡める
4. 感情（驚き、共感、危機感、希望）のどれか1つを刺激する
5. ハッシュタグは #AI #生成AI #医療AI のうち1〜2個まで、末尾に
6. 改行を積極的に使い、視認性を上げる
7. 絵文字は1〜2個まで（使いすぎない）

禁止事項:
- 「〜だと思います」「〜かもしれません」などの曖昧表現
- 長すぎる前置き
- 広告っぽいセールストーク
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
    """番号付きリストからツイート文を抽出（280文字以内）"""
    lines = [
        re.sub(r"^\d+[\.\)【】]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def _extract_thread(raw: str) -> list[str]:
    """スレッド形式（--- 区切り）から各ツイートを抽出"""
    parts = re.split(r"\n---+\n", raw)
    tweets: list[str] = []
    for part in parts:
        clean = part.strip()
        # ヘッダー行（【スレッド1/N】など）を除去
        clean = re.sub(r"^【.{0,20}】\s*\n?", "", clean).strip()
        if clean and len(clean) <= MAX_TWEET_LENGTH:
            tweets.append(clean)
    return tweets


def generate_single_tweet(topic: str, context: str = "", feedback: str = "") -> list[str]:
    """1つのトピックからバズりやすい単発ツイートを3案生成"""
    few_shot = ""
    if feedback.strip():
        examples = "\n".join(
            l for l in feedback.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を参考にする）\n{examples}\n"

    context_section = f"\n## コンテキスト\n{context[:3000]}" if context else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、Xでバズる投稿文を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_STRATEGY}
{few_shot}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力、各案を1行で
- 3案それぞれ異なるフォーマット（数字型・逆説型・問いかけ型など）を使う
- ビジネス層・経営者・医療従事者に刺さる内容

## トピック
{topic}
{context_section}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread(topic: str, context: str = "") -> list[str]:
    """5ツイートのスレッドを生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、Xでシェアされやすい5ツイートのスレッドを作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッド構成:
1/ フック（驚き・逆説・数字で読者を止める。140文字以内）
2/ 問題提起・背景（140文字以内）
3/ 核心の洞察・データ（140文字以内）
4/ 解決策・未来像（140文字以内）
5/ まとめ + 「RTで広めてください」（140文字以内）

出力形式: 各ツイートを --- で区切る（他の文字は不要）

## トピック
{topic}

{"## コンテキスト" + chr(10) + context[:2000] if context else ""}
"""
    raw = _call_claude(prompt)
    return _extract_thread(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """複数RSSから最新AIヘッドラインを取得"""
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
    # 重複除去
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースから投稿案を生成。(tweets, source_title) を返す"""
    items = fetch_rss_headlines()

    if not items:
        tweets = _generate_original_ai_insight()
        return tweets, "AI洞察（独自）"

    headlines_text = "\n".join(f"- {h['title']}" for h in items)
    # 最も注目トピックを1つ選ばせてから生成
    prompt_select = f"""以下のAIニュース一覧から、ビジネス層・経営者・医療従事者に最も刺さりそうな
トピックを1つ選び、そのタイトルだけを出力してください。

{headlines_text}
"""
    selected_title = _call_claude(prompt_select).strip().split("\n")[0]

    # 選んだトピックで単発ツイートを生成
    tweets = generate_single_tweet(
        topic=selected_title,
        context=headlines_text,
    )
    return tweets, selected_title


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績から戦略的投稿案を生成"""
    topic = note_text[:200]  # 記事の冒頭をトピックとして使用
    context = note_text
    if note_url:
        context += f"\n\n投稿末尾にNoteリンクを含める: {note_url}"
    return generate_single_tweet(topic, context, feedback_text)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    topics = [
        "2026年の医療AIと診断精度の現実",
        "AIエージェントがビジネスを変える具体的なポイント",
        "Claude・GPT・Geminiの使い分けでできること",
        "AIで医師・医学生がコードなしにプロダクトを作れる時代",
        "ブロックチェーンと医療データ主権の未来",
    ]
    topic = random.choice(topics)
    return generate_single_tweet(topic)
