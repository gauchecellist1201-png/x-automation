"""
Claude API を使った戦略的投稿文生成モジュール（v2）
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けバズ分析強化版
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI・ビジネス
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+エージェント+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+DX+革新&hl=ja&gl=JP&ceid=JP:ja",
    # 英語グローバルソース
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/ai/feed/",
    "https://www.technologyreview.com/feed/",
]

NUM_CANDIDATES = 3
MAX_TWEET_CHARS = 140

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- スイス大学研究・国連会議参加のグローバル視点
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- Claude Codeなど最先端AIツールを日常的に活用中
"""

BUSINESS_AUDIENCE = """
## ターゲット読者：ビジネス層
- 経営者・マネージャー・意思決定者
- AI導入を検討中または導入済みの企業人
- 医療・ヘルスケア業界のプロフェッショナル
- スタートアップ創業者・投資家
- 「AIで何が変わるか」を実践的に知りたいビジネスパーソン
"""

VIRAL_PATTERNS = """
## バズるAI投稿のパターン（ビジネス層向け）

【パターンA: 数字で掴む】
例：「AI導入企業の生産性は平均40%向上。未導入企業との差は2年後に埋めがたくなる。」
→ 具体的な数字で実感させ、危機感を与える

【パターンB: 逆説・驚き】
例：「AIは医師を置き換えない。でも、AIを使えない医師は淘汰される。」
→ 逆説で思考を止め、最後まで読ませる

【パターンC: 未来予測・緊急性】
例：「2年後、AIエージェントは上司の承認なしに業務を完結させる。あなたの会社は準備できているか。」
→ 具体的な年数で現実感を出す

【パターンD: 問いかけで終わる（RT率高）】
例：「ChatGPTに3ヶ月で仕事の質が変わったと感じる人が急増。問題は技術ではなく、学ぶ速度の差ではないか。」
→ 読者自身の問題として引き込む

【パターンE: リスト形式（保存率高）】
例：「AIを使いこなすビジネスパーソンが必ずやっていること3選：①プロンプトを資産管理 ②出力を必ず検証 ③ツールより思考法として使う」
→ 保存・共有されやすい実用情報

【パターンF: 体験・実証報告】
例：「Claude Codeで医療データ分析ツールを1日で構築。コードは0行。これが2026年のリアル。」
→ 本人の体験で信頼性と共感を生む

【パターンG: 警鐘・機会損失】
例：「AIを知らないことが、今やビジネスリスクになっている。」
→ 行動を促す危機感の演出
"""

OUTPUT_FORMAT = """
## 出力フォーマット（必ずこの形式で出力すること）

---案1---
投稿: （140文字以内の投稿文。改行可。ハッシュタグ含む）
画像: （この投稿に合う画像の説明。20〜40文字）
パターン: （使用したパターン名。例：B逆説・驚き）
---案2---
投稿: ...
画像: ...
パターン: ...
---案3---
投稿: ...
画像: ...
パターン: ...
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_structured_output(raw: str) -> list[dict]:
    """---案N--- 形式の構造化出力を辞書リストに変換する"""
    results = []
    blocks = re.split(r"---案\d+---", raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        tweet_match = re.search(r"投稿:\s*(.+?)(?=画像:|パターン:|$)", block, re.DOTALL)
        image_match = re.search(r"画像:\s*(.+?)(?=パターン:|---案|$)", block, re.DOTALL)
        pattern_match = re.search(r"パターン:\s*(.+?)(?=---案|$)", block, re.DOTALL)

        tweet_text = tweet_match.group(1).strip() if tweet_match else ""
        image_text = image_match.group(1).strip() if image_match else ""
        pattern_text = pattern_match.group(1).strip() if pattern_match else ""

        # 文字数チェック（URL 23文字換算済みで140文字以内）
        url_adjusted = re.sub(r"https?://\S+", "x" * 23, tweet_text)
        if tweet_text and len(url_adjusted) <= MAX_TWEET_CHARS:
            results.append({
                "tweet": tweet_text,
                "image": image_text,
                "pattern": pattern_text,
            })

    return results[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[dict]:
    """Note記事 + 過去実績から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_note = f"\n- 文末にNoteリンクを入れても良い: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_PATTERNS}

投稿ルール:
- 各投稿は140文字以内（URL は23文字換算）{link_note}
- ハッシュタグは #AI #生成AI #医療AI #ビジネス のうち最大2個
- 必ず上記バズパターンのいずれかを意識して使うこと
- ビジネス層が「保存・RT したい」と思う情報価値を持たせる
{few_shot}
## Note記事本文
{note_text[:4000]}

{OUTPUT_FORMAT}"""

    raw = _call_claude(prompt)
    return _parse_structured_output(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    """複数 RSS フィードからAI関連ニュースを収集"""
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Google News の "- 出典名" を除去
                title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    # 重複除去して最大 max_items 件
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[dict]:
    """最新AIトレンドニュースからビジネス層向け投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1〜2つ選び、
ビジネス層に刺さる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_PATTERNS}

投稿ルール:
- 各投稿は140文字以内
- ハッシュタグは #AI #生成AI #医療AI #ビジネス のうち最大2個
- 医療×AI、社会変革、企業の競争優位を絡めると尚良い
- ビジネス層が「保存・RT したい」と思う実用的洞察を含める

## 今日の最新AIニュース
{headlines_text}

{OUTPUT_FORMAT}"""

    raw = _call_claude(prompt)
    posts = _parse_structured_output(raw)
    return posts if posts else _generate_original_ai_insight()


def _generate_original_ai_insight() -> list[dict]:
    """RSS 取得失敗時のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界・医療DX・ビジネス変革の最重要トピックについて、
ビジネス層に刺さる深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_PATTERNS}

投稿ルール:
- 各投稿は140文字以内
- Claude、GPT-5、AI Agent、医療AI、AIと経営戦略などのテーマを優先
- ビジネス層が「明日の会議で話したい」と思う情報価値を持たせる

{OUTPUT_FORMAT}"""

    raw = _call_claude(prompt)
    return _parse_structured_output(raw)
