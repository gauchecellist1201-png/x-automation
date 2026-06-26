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
    "https://news.google.com/rss/search?q=AI+ビジネス+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加などグローバル視点
- 課題解決志向で、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）

### バイラルパターン（どれか1つを使う）
A) データ・数字で驚かせる
   例：「AI導入企業の87%が○○という問題を抱えている。でも対策している会社は3%未満。」

B) 「知らないと損」型の啓発
   例：「ほとんどの経営者が見落としているAIの○○リスク。把握していれば10分で対策できる。」

C) 逆張り・反論型
   例：「AIは仕事を奪う——という議論は的外れだと思っている。本当の問いは○○だから。」

D) ストーリー型（医療×AI）
   例：「医学生として実感した。AIが診断を変えるより先に、○○を変えている。」

E) 予測・未来洞察型
   例：「2027年にはAIが○○する。今からその準備をしている企業とそうでない企業で、格差が生まれる。」

### 投稿ルール
1. 冒頭の1行で止まらせる（スクロールを止めるフック）
2. 専門的だが難解すぎない言葉選び
3. ビジネスへの実害・実益を具体的に示す
4. 「問い」か「続きが気になる構造」で締める
5. ハッシュタグは #AI #生成AI #ビジネス のうち1〜2個まで
6. URLリンクは文末に自然に入れる（URLは23文字換算）
7. 絵文字は1〜2個まで（使いすぎない）
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
    """番号付きリストから投稿文を抽出し280文字以内に絞る"""
    tweets = []
    current = []
    for line in raw.splitlines():
        line = line.rstrip()
        if re.match(r"^\d+[\.\)]\s+", line):
            if current:
                tweet = "\n".join(current).strip()
                if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current = [re.sub(r"^\d+[\.\)]\s*", "", line).strip()]
        elif current and line:
            current.append(line)
    if current:
        tweet = "\n".join(current).strip()
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)
    return tweets


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

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ書く（解説不要）
- ハッシュタグは1〜2個まで
- ビジネス層（経営者・スタートアップ・投資家）が「RT・引用したい」と思う内容に{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS フィードからタイトルとリンクを取得"""
    items: list[dict] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue
    return items[:max_items]


def select_best_headline(items: list[dict]) -> dict | None:
    """最もバズりそうなニュースをClaudeが1件選択"""
    if not items:
        return None
    headlines_text = "\n".join(f"{i+1}. {it['title']}" for i, it in enumerate(items))
    prompt = f"""以下のAIニュース見出しから、ビジネス層（経営者・スタートアップ・投資家）が
最も関心を持ちそうな1件を選び、その番号だけ返してください（例: 3）。

{headlines_text}

番号のみ回答:"""
    raw = _call_claude(prompt).strip()
    m = re.search(r"\d+", raw)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(items):
            return items[idx]
    return items[0]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成。
    (投稿案リスト, 記事URL) を返す"""
    items = fetch_rss_headlines()
    best = select_best_headline(items) if items else None

    if best:
        headline = best["title"]
        article_url = best["link"]
        headlines_text = f"注目ニュース: {headline}"
    else:
        headline = ""
        article_url = ""
        headlines_text = "最新AIトレンド全般"

    link_note = f"\n- 文末にニュースリンクを自然に入れる: {article_url}" if article_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースに基づき、井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ書く（解説不要）
- 医療×AI、ビジネス変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで{link_note}

## 今日の注目AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    return posts, article_url


def _generate_original_ai_insight() -> tuple[list[str], str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ書く（解説不要）
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw), ""
