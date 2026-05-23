"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+OpenAI+生成AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+大規模言語モデル+LLM+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+業務効率化+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（最前線）
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点（スイス研究・国連会議参加）
- PHR/EHRへのブロックチェーン活用を研究・実装中
- Claude Codeなど最新AIツールを実践活用
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）
1. 「知らなかった」「考えさせられた」「使ってみたい」と思わせる切り口
2. 専門的だが難解すぎない言葉選び、ビジネスパーソンに刺さる表現
3. 医療・社会変革・未来への問いかけを絡める
4. 結論より「問い」で終わるとRTされやすい
5. ハッシュタグは #AI #生成AI のうち1〜2個まで
6. リンクをつける場合は文末に自然に入れる
"""

VIRAL_PATTERNS = """
## バズるX投稿の型（必ずこの中から選んで使う）

【衝撃スタッツ型】
「ChatGPTが〇〇の診断を2秒で実行。専門医が20分かけていた作業が…
これを"脅威"と見るか"武器"と見るかで、5年後が変わる。 #AI」

【逆説・反論型】
「「AIに仕事を奪われる」は間違い。
正確には「AIを使う人に仕事を奪われる」。
違いは小さいようで、対策が180度変わる。 #生成AI」

【予言・警告型】
「3年後、AIを使いこなせないビジネスパーソンは
スマホを持てなかった90年代の経営者と同じ立場になる。
今が"普通に使い始める"最後のチャンスかもしれない。 #AI」

【体験談・実績型】
「Claude Codeで医療系MVPを1人・3日で作った。
1年前なら10人・3ヶ月かかっていた作業。
AIは能力を「増幅」するのではなく、「次元」を変える。 #生成AI」

【問いかけ型】
「AIが医師の診断を超える日は来るのか。
現役医学生として毎日この問いと向き合っている。
答えよりも、"正しい問い"を持てるかが重要な気がする。 #AI」

【リスト・スレッド誘導型】
「AIで変わるビジネスの常識、2026年版🧵
(1/5) まず一番驚いたのは採用領域。
履歴書選考を任せた企業が続出し、HR担当の仕事が…」

【ニュース解説型】
「〔今日のAIニュース〕
〇〇がついに〇〇を発表。
注目点は2つ——
① コスト：従来比10分の1
② 精度：医師レベルを超えた領域も
ビジネス層がいちばん知るべきニュースだと思う。 #AI」
"""


@dataclass
class PostCandidate:
    text: str
    source_url: str = ""
    image_hint: str = ""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出する（複数行投稿対応）"""
    results = []
    # 「1.」「1)」「【案1】」などで始まるブロックを分割
    blocks = re.split(r"\n(?=\d+[\.\)]\s|【案\d+】)", raw.strip())
    for block in blocks:
        # 先頭の番号・ラベルを除去
        cleaned = re.sub(r"^(\d+[\.\)]\s*|【案\d+】\s*)", "", block.strip())
        # 空行を1行に圧縮してトリム
        cleaned = re.sub(r"\n{2,}", "\n", cleaned).strip()
        if cleaned and 10 < len(cleaned) <= 280:
            results.append(cleaned)
    return results[:NUM_CANDIDATES]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[PostCandidate]:
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

    link_instruction = f"\n- 文末にNoteリンクを入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さりバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内（URLは23文字換算）。URLを含む場合は実質117文字以内
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 上記の「バズる型」を必ず1つ選んで使う（使った型の名前を【】で投稿前に明記）{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    posts = _extract_posts(raw)
    return [PostCandidate(text=p, source_url=note_url) for p in posts]


def fetch_rss_items(max_items: int = 10) -> list[dict]:
    """RSSから記事タイトルとURLを取得"""
    items: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    # Google NewsのリダイレクトURLを除外してオリジナルURLを優先
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    # 重複排除（タイトルベース）
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> list[PostCandidate]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_items()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}（{it['url']}）" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最もビジネス層に刺さるトピックを1〜2つ選び、
バズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、ビジネス効率化への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 上記の「バズる型」を必ず1つ使い、各案の冒頭に【型名】を明記
- 投稿に最も関連するニュースのURLを文末に入れる場合はURL込みで140文字以内
- 最後に：各案で使ったニュースのURLを「参照URL: ...」として別行に記載

## 今日の最新AIニュース（タイトルとURL）
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_posts(raw)

    # 参照URLを抽出して各投稿に紐付け
    url_matches = re.findall(r"参照URL:\s*(https?://\S+)", raw)
    candidates = []
    for i, post in enumerate(posts):
        url = url_matches[i] if i < len(url_matches) else (items[0]["url"] if items else "")
        # 投稿内のURL（既に含まれている場合）を優先
        inline_url = re.search(r"https?://\S+", post)
        final_url = inline_url.group(0) if inline_url else url
        candidates.append(PostCandidate(text=post, source_url=final_url))
    return candidates


def _generate_original_ai_insight() -> list[PostCandidate]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さるバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIエージェント、AIと社会変革などのテーマを優先
- 上記の「バズる型」を必ず1つ使い、各案の冒頭に【型名】を明記
"""
    raw = _call_claude(prompt)
    posts = _extract_posts(raw)
    return [PostCandidate(text=p) for p in posts]
