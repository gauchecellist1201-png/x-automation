"""
Claude API を使った戦略的バイラル投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）— ビジネス層向けAI投稿
"""

import os
import re
import feedparser
import requests
import anthropic

# X は280文字まで（日本語も1文字=1カウント）
MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+ChatGPT+Claude+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+経営+ビジネス+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI+発表&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AIニュース（グローバル視点）
    "https://news.google.com/rss/search?q=artificial+intelligence+business+GPT+Claude+Gemini&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学研究・国連会議参加経験のあるグローバル視点
- 専門知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- ターゲット読者：AIに関心があるビジネスパーソン・経営者・医療従事者
"""

TWEET_STRATEGY = """
## バズるAIビジネス投稿の鉄則

【エンゲージメントを高める構造】
1. 最初の1〜2行でスクロールを止める「フック」
2. 専門的だが難解すぎない言葉選び（中学生でも読める）
3. 「知らなかった」「考えさせられた」と思わせる切り口
4. 結論より「問い」か「余白」で終わるとRTされやすい
5. ハッシュタグは #AI #生成AI のうち1〜2個まで（多すぎはNG）
6. 数字・データを入れると信頼感UP

【高バズパターン例】
パターンA: 逆張り系
「AIで業務効率5倍」より重要なことがある。
効率化した時間で何をするか、考えてる会社は5%以下。
ツールより「問い」が先。 #生成AI

パターンB: ニュース解説+洞察系
◆速報：[具体的ニュース]
これが意味すること：
・経営判断への影響：〇〇
・業界再編の可能性：〇〇
・今すぐすべきこと：〇〇

パターンC: 問いかけ系
「AI導入したけど成果が出ない」
こういう声を毎週聞く。
原因はほぼ同じ——「何を自動化するか」を決める前に導入してる。
先に「捨てる業務」を決めること。 #AI

パターンD: 数字フック系
マッキンゼー最新試算：AIで代替される仕事は全体の30%
でも誰も言わないのは——
「30%に含まれる医師は何%か」という問い #AI #医療

パターンE: 未来の問い系
5年後、AIを「使う側」か「使われる側」か。
分かれ目はツールの使い方じゃなく、思考の深さ。 #生成AI
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
    """=== TWEET N === / === END N === マーカーから投稿文を抽出"""
    pattern = re.compile(
        r"===\s*TWEET\s*\d+\s*===(.*?)===\s*END\s*\d+\s*===",
        re.DOTALL | re.IGNORECASE,
    )
    candidates = []
    for match in pattern.finditer(raw):
        tweet = match.group(1).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            candidates.append(tweet)
    # マーカーがない場合は番号付きリストにフォールバック
    if not candidates:
        for line in raw.splitlines():
            line = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if 10 < len(line) <= MAX_TWEET_LENGTH:
                candidates.append(line)
    return candidates[:NUM_CANDIDATES]


def fetch_rss_items(max_items: int = 10) -> list[dict]:
    """RSS から (title, link) のリストを返す"""
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
    # 重複タイトルを除去
    seen: set[str] = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def fetch_ogp_image(url: str) -> str | None:
    """記事URLからOGP画像URLを取得する"""
    if not url:
        return None
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
        )
        resp.raise_for_status()
        # 簡易OGPパース（BeautifulSoupなしでregexで取得）
        og_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text,
            re.IGNORECASE,
        )
        if og_match:
            return og_match.group(1)
        # content が先に来るパターン
        og_match2 = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            resp.text,
            re.IGNORECASE,
        )
        if og_match2:
            return og_match2.group(1)
    except Exception:
        pass
    return None


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"
            )

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

出力フォーマット（必ずこの形式で）:
=== TWEET 1 ===
[投稿文 — 改行OK、280文字以内]
=== END 1 ===

=== TWEET 2 ===
[投稿文]
=== END 2 ===

=== TWEET 3 ===
[投稿文]
=== END 3 ===

ルール:
- 各投稿は280文字以内（URLは23文字換算）
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、ビジネスパーソンにも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> tuple[list[str], str | None]:
    """最新AIトレンドニュースを元にバイラル投稿案を生成。(posts, ogp_image_url) を返す"""
    items = fetch_rss_items()
    if not items:
        posts = _generate_original_ai_insight()
        return posts, None

    headlines_text = "\n".join(f"- {it['title']}" for it in items)

    # 最も注目度の高い記事からOGP画像を取得
    ogp_url: str | None = None
    for item in items[:3]:
        ogp_url = fetch_ogp_image(item.get("link", ""))
        if ogp_url:
            break

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるバイラルX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

出力フォーマット（必ずこの形式で）:
=== TWEET 1 ===
[投稿文 — 改行OK、280文字以内]
=== END 1 ===

=== TWEET 2 ===
[投稿文]
=== END 2 ===

=== TWEET 3 ===
[投稿文]
=== END 3 ===

ルール:
- 各投稿は280文字以内
- 医療×AI、社会変革、ビジネス競争優位、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 「逆張り」「数字フック」「問いかけ」のいずれかのパターンを優先

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    return posts, ogp_url


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

出力フォーマット（必ずこの形式で）:
=== TWEET 1 ===
[投稿文 — 改行OK、280文字以内]
=== END 1 ===

=== TWEET 2 ===
[投稿文]
=== END 2 ===

=== TWEET 3 ===
[投稿文]
=== END 3 ===

ルール:
- 各投稿は280文字以内
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 「逆張り」「数字フック」「問いかけ」のいずれかのパターンを使う
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
