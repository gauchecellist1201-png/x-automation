"""
Claude API を使った戦略的投稿文生成モジュール
対象: ビジネス層（経営者・マネジメント・スタートアップ）向けAI情報発信
アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI × ビジネス
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+OpenAI+ビジネス+活用+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+経営+DX+スタートアップ+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+資金調達+投資+テック+日本+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 AI ニュース（最先端・ビジネス向け）
    "https://news.google.com/rss/search?q=AI+enterprise+productivity+agent+ROI+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+OpenAI+GPT+Gemini+breakthrough+business+2026&hl=en&gl=US&ceid=US:en",
    # Ledge AI（日本語専門メディア）
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 発信者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合・PHR/EHRへのブロックチェーン活用を研究
- スイス大学での研究、国連会議参加のグローバル視点
- Claude Codeなど最先端AIツールを実務で活用中
- ターゲット読者: 経営者・マネジメント・スタートアップ創業者・投資家（ビジネス層）
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（必ずどれか1つを採用すること）

【A: 数字フック】具体的な数値で「知らなかった」を引き出す
例: "日本企業のAI導入率は8割超。でも『業務が変わった』は2割未満。差は"使い方"ではなく経営判断にある。"

【B: 逆張り・常識破壊】業界の思い込みをひっくり返す
例: "AIは仕事を奪わない。AIを使う人が、使わない人の仕事を奪う。これはもう現実だ。"

【C: インサイダー視点】専門家・現場だから知っている情報
例: "医師として断言する。AIが最初に置き換えるのは診断ではなく書類作業だ。現場はすでにそうなっている。"

【D: 問いかけ】リプライ・RTを誘発する一言
例: "あなたの会社で、AIを毎日使いこなしている人は何%いる？正直に。"

【E: リスト・保存推奨】すぐ使えて保存されやすいコンテンツ
例: "2026年、経営者が知るべきAIの変化3選（保存推奨）"

【F: Before/After・変化の可視化】
例: "半年前: 議事録に30分 → 今: AIが会議中にリアルタイム生成。この差は2年後に会社の差になる。"

【G: トレンド先読み・予測】
例: "6ヶ月後、AIエージェントを導入した企業とそうでない企業で採用力・生産性に明確な差が出る。今動くか否かで決まる。"
"""

TWEET_STRATEGY = """
## 投稿戦略
- 140文字をフル活用。「続きが気になる」「保存したい」「RTしたい」のどれかを必ず狙う
- ビジネス層の関心: ROI・生産性・競合優位・採用力・資金調達・リスク管理
- 問いで終わるとリプライ・RTが増える（特にパターンD）
- ハッシュタグは #AI または #生成AI のうち最大1個のみ（乱用しない）
- 絵文字は使わないか、最小限（1個まで）。ビジネス層には硬めのトーンが刺さる
- URLは文末に自然に組み込む（23文字換算）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """ヘッドラインとリンクを含む記事リストを取得（重複排除済み）"""
    articles: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    articles.append({"title": title, "link": link})
        except Exception:
            continue
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            deduped.append(a)
    return deduped[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績からビジネス層向け戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層（経営者・スタートアップ・投資家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

追加ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def generate_posts_from_rss() -> tuple[list[str], str, str]:
    """最新AIニュースからビジネス層向け投稿を生成。

    Returns:
        (投稿案リスト, ソース記事リンク, ソース記事タイトル)
    """
    articles = fetch_rss_headlines()
    if not articles:
        posts = _generate_original_ai_insight()
        return posts, "", ""

    headlines_text = "\n".join(f"- {a['title']}" for a in articles)
    source_link = articles[0]["link"]
    source_title = articles[0]["title"]

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も「バズりそう」かつ「ビジネス層に刺さる」トピックを1つ選び、
X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- バズるパターンA〜Gのどれかを必ず使う
- ビジネス層（経営者・投資家・スタートアップ）の意思決定に関わる角度で書く

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_posts(raw)
    return posts, source_link, source_title


def _generate_original_ai_insight() -> list[str]:
    """RSS取得不可時のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトレンドについて、
ビジネス層（経営者・スタートアップ・投資家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- バズるパターンA〜Gのどれかを必ず使う
- AIエージェント・医療AI・生産性・競合優位・資金調達などのテーマ優先
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)
