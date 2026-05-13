"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

# 日本語・英語のAIニュース上質ソース（英語ソースは速報性が高い）
RSS_FEEDS = [
    # 日本語ソース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIビジネス+AI活用+企業DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語ソース（日本語より数時間〜数日早く情報が出る）
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+AI+release&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+business+productivity+enterprise+2026&hl=en&gl=US&ceid=US:en",
]

NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大テーマに活動
- スイス大学研究経験・国連会議参加のグローバル視点
- Claude Codeなど最前線AIツールを日常業務に活用
- 読者に問いを投げかける「静かに鋭い洞察」スタイル
- 押しつけがましくなく、専門知識を平易な言葉で届ける
"""

VIRAL_PATTERNS = """
## バズるビジネス×AIツイートの7つの型（必ずいずれかを使う）

型1【衝撃の数字型】
  例：「GPT-4oでレポート作成が8時間→20分になった。これ、ほぼ全業種で起きてる」
  → 具体的な数字で読者の感覚を揺さぶる。コメント・保存を誘発。

型2【逆張り・反直感型】
  例：「AIは仕事を奪わない。でもAIを使う人間が、使わない人の仕事を奪う」
  → 常識を覆す一言でRTを誘発。引用RTしやすい構造。

型3【問いかけ締め型】
  例：「あなたの会社の競合、もうAIで〇〇を自動化してるかもしれない。対策してますか?」
  → 問いで終わるとコメントが来やすい。エンゲージメント最大化。

型4【ビフォーアフター型】
  例：「2年前: 企画書に3日 / 今: AIと30分で完成。差はツールじゃなく思考法にある」
  → 変化の劇的さが保存・RTされる。数字で落差を見せる。

型5【速報＋独自洞察型】
  例：「【今日のAIニュース】Claudeが〇〇発表。これが意味すること→ 医療×AIで〇〇が変わる」
  → 情報提供＋独自視点のセットで差別化。リツイートされやすい。

型6【FOMO（置いてかれる恐怖）型】
  例：「これを知らないまま2026年を過ごすのは正直もったいない」
  → 保存・ブックマークを強烈に誘発。

型7【リスト型】
  例：「今週のAI業界重要ニュース3選:\n①〇〇\n②〇〇\n③〇〇\n詳細は→」
  → スキャンしやすく、保存される。インプレが伸びやすい。
"""

TWEET_STRATEGY = """
## 投稿の共通ルール
1. ビジネス層（経営者・管理職・起業家）に刺さる言葉選び
2. 専門的だが難解すぎない。中学生でも意味が分かる平易さ
3. 医療・社会変革・未来への問いを絡めると差別化できる
4. ハッシュタグは #AI #生成AI のうち0〜2個（多用しない）
5. 結論より「問い」か「余白」で終わると拡散されやすい
6. URLは文末に自然に入れる（23文字として計算）
"""

OUTPUT_FORMAT = """
## 出力フォーマット（厳守）
各投稿案を以下の形式で出力すること:

<tweet>
投稿文をここに書く（改行OK、140文字目安）
</tweet>

<tweet>
投稿文をここに書く
</tweet>

<tweet>
投稿文をここに書く
</tweet>

※ XMLタグの外に解説や前置きを書かない
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """<tweet>...</tweet> タグから投稿文を抽出する"""
    matches = re.findall(r"<tweet>(.*?)</tweet>", raw, re.DOTALL)
    tweets = [m.strip() for m in matches if m.strip()]
    # フォールバック: タグが無い場合は旧来の番号付きリスト抽出を試みる
    if not tweets:
        lines = [
            re.sub(r"^\d+[\.\)]\s*", "", l).strip()
            for l in raw.splitlines()
            if re.match(r"^\d+", l.strip())
        ]
        tweets = [t for t in lines if 10 < len(t) <= 280]
    return tweets[:NUM_CANDIDATES]


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
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

追加ルール:
- 各投稿は140文字目安（URLは23文字換算）{link_instruction}
- 上記7つの型のいずれかを必ず使う
{few_shot_section}
## Note記事本文
{note_text[:4000]}

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_items(max_items: int = 8) -> list[dict]:
    """RSSフィードから記事情報（タイトル・URL・要約）を取得"""
    items: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()[:200]
                if title and len(title) > 10:
                    items.append({"title": title, "url": link, "summary": summary})
        except Exception:
            continue

    # タイトルで重複除去
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースを元にバズりやすい投稿案を生成。(投稿案リスト, 元記事URL) を返す"""
    items = fetch_rss_items()
    if not items:
        posts = _generate_original_ai_insight()
        return posts, ""

    headlines_text = "\n".join(
        f"- {item['title']}" + (f"（{item['summary']}）" if item["summary"] else "")
        for item in items
    )
    # 最も注目度が高そうな記事のURLを元記事として返す
    top_url = items[0]["url"] if items else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースの中から最も注目すべきトピックを1つ選び、
ビジネス層（経営者・起業家・管理職）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

追加ルール:
- 各投稿は140文字目安
- 上記7つの型のいずれかを必ず使う
- 医療×AI・社会変革・未来への問いを絡めると差別化できる

## 今日の最新AIニュース
{headlines_text}

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw), top_url


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトレンドについて、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

追加ルール:
- 各投稿は140文字目安
- 上記7つの型のいずれかを必ず使う
- Claude・GPT・医療AI・AIと社会変革を優先テーマに

{OUTPUT_FORMAT}"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
