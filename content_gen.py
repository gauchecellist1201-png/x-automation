"""
Claude API を使った戦略的投稿文生成モジュール（バズ特化・ビジネス層向け版）
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AI総合
    "https://news.google.com/rss/search?q=AI+人工知能+OpenAI+Claude&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ChatGPT+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    # ビジネスAI特化
    "https://news.google.com/rss/search?q=AI+ビジネス活用+業務効率化+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+企業導入+DX+コスト削減&hl=ja&gl=JP&ceid=JP:ja",
    # 最新モデル・技術動向
    "https://news.google.com/rss/search?q=GPT-5+Claude+Anthropic+最新&hl=ja&gl=JP&ceid=JP:ja",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者：井出直毅 (@GAUCHE_cellist)
医学生 × AI/ブロックチェーン起業家。医療×テクノロジーの融合を追求。
スイス大研究・国連会議など国際経験豊富。Claude Codeなど最先端AIを日常使い。
医療データのブロックチェーン管理、非中央集権的PHR/EHRを研究・実装中。
"""

VIRAL_FORMULAS = """
## バズる投稿の6公式（3案で必ず異なるものを使う）

A【数字インパクト型】
統計・数字で始める。衝撃的な事実でスクロールを止める。
例：「McKinseyの調査でAI活用企業の生産性は非導入企業の2.3倍になると判明。日本は導入率が先進国最下位。このままでは差が縮まらない。 #AI」

B【意外な事実型】
「実は」「誤解されているが」で始める。常識を覆す切り口。
例：「ChatGPTの本当の使い方を間違えている人が多い。プロンプトの最初に「あなたは○○の専門家です」と書くだけで出力精度が激変する。 #生成AI」

C【緊急性・警告型】
業界変化・競合動向で健全な危機感を醸成する。
例：「○○業界でAI完全導入が加速。人間が担っていた△△の工程が3年以内に変わる可能性がある。今から準備している企業とそうでない企業の差は明確だ。 #AI」

D【具体ノウハウ型】
すぐ使えるtipsを提供。保存・シェアされやすい。
例：「会議の議事録作成にAIを使ったら月20時間節約できた。ポイントは①録音→文字起こし②要点抽出プロンプトの設計③テンプレ化の3ステップ。 #生成AI」

E【問いかけ型】
読者に考えさせる。返信・RTを誘う哲学的問い。
例：「AIが診断補助をできるようになった今、医師の本質的な価値は何か。技術革新の前に、私たちは答えを持っているか。 #医療AI #AI」

F【対比・格差型】
AI使用者と非使用者の格差を具体的に示す。
例：「AI使う営業職は提案書を30分で仕上げる。使わない人は3時間かかる。この差が積み重なれば、1年で何百時間もの差になる。 #AI #生成AI」
"""

CONTENT_RULES = """
## 投稿ルール
- 140文字以内（URLは23文字換算）
- 最初の一文でスクロールを止める強力なhookを入れる
- 数字・固有名詞・具体例で信頼性を高める
- ハッシュタグは #AI #生成AI #ChatGPT #医療AI から1〜2個まで
- 3案はA〜Fの異なるパターンを使うこと
- 番号付きリスト（1. 2. 3.）で、各案は必ず1行に収める
- 嘘の数字・未確認の事実は絶対に書かない
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
    """番号付きリストからツイート本文を抽出（1行形式）"""
    results = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^\d+[\.\)]\s*(.*)", line)
        if not m:
            continue
        text = m.group(1).strip()
        # [パターン名] / 【パターン名】 プレフィックスを除去
        text = re.sub(r"^\[.*?\]\s*", "", text).strip()
        text = re.sub(r"^【.*?】\s*", "", text).strip()
        if len(text) > 10:
            results.append(text[:MAX_TWEET_LENGTH])
    return results[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事から戦略的バズ投稿を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 参考：過去に好評だった投稿スタイル\n{examples}\n"

    link_note = f"\n- 文末にNoteリンクを自然に入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を元に、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{CONTENT_RULES}{link_note}
{few_shot}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    """RSSから最新AIニュースのヘッドラインを取得"""
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
    seen: set[str] = set()
    unique: list[str] = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    return unique[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIニュースからビジネス層向けバズ投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースからビジネス層に最も刺さるトピックを選び、
バズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{CONTENT_RULES}

重要：ニュースの内容を正確に反映すること。嘘の数字・事実は書かない。
複数のトピックから別々に選んで3案作ってもよい。

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    return posts if posts else _generate_original_ai_insight()


def _generate_original_ai_insight() -> list[str]:
    """RSS取得失敗時のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界の最新動向をもとに、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMULAS}
{CONTENT_RULES}

テーマ例：Claude/GPT最新機能、AIエージェント、医療AI、AI×経営変革、日本企業のAI活用格差
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
