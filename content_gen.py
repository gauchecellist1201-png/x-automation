"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import json
import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIビジネス+AI活用+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスでの研究経験、国連会議参加のグローバル視点
- 専門的知識をわかりやすく伝えつつ、読者に考えさせる問いを投げかける
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

# バズる投稿パターンの分析（実際にRT・いいねが多い日本語AIツイートの共通構造）
VIRAL_PATTERNS = """
## バズる投稿の構造分析（必ずこれに従うこと）

### パターン1: 数字インパクト型
「〇〇が△△%向上」「〇〇秒でできる」「〇〇万円が不要に」
→ 具体的な数字でスクロールを止める

### パターン2: 逆説・反転型
「AIが〇〇できる時代に、なぜ△△が重要になるのか」
「〇〇のはずが、実は△△だった」
→ 「え、なんで？」と読ませる

### パターン3: ビジネス脅威・機会型
「〇〇業界がAIで変わる」「この仕事は5年後に存在しない」
「逆に今、〇〇ができる人材の価値が爆上がりしている」
→ 自分ごととして捉えさせる

### パターン4: 気づき共有型
「ChatGPT/Claudeを使い始めて気づいたこと：」
「多くの人が見落としている〇〇の本質：」
→ コロンで続きを読ませる

### パターン5: 問いかけ型（最もRT されやすい）
「〇〇って思ってる？実は△△かもしれない。」
「AIが医療を変えるとき、医師は何をすべきか。」
→ 答えを持たせず、読者に考えさせる

### 重要ルール
- 1行目（hook）で勝負。スクロールを止める一文が命
- 改行は効果的に使う（1〜2回まで）
- ハッシュタグは文末に1〜2個のみ
- URLは23文字換算（実際の文字数から除く）
- 「〜です」より「〜だ」の断言調の方が刺さる
- ビジネス層（経営者・スタートアップ・管理職）が「シェアしたい」と思う内容に
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_tweet_candidates(raw: str) -> list[str]:
    """
    Claude の出力から投稿候補を抽出する。
    JSON配列形式を優先し、失敗時は番号付きリストにフォールバック。
    """
    # JSON配列の抽出を試みる
    json_match = re.search(r'\[[\s\S]*?\]', raw)
    if json_match:
        try:
            candidates = json.loads(json_match.group())
            return [t.strip() for t in candidates if isinstance(t, str) and 0 < len(t.strip()) <= MAX_TWEET_LENGTH * 2]
        except json.JSONDecodeError:
            pass

    # フォールバック: "1." "2." "3." 形式から抽出
    # 複数行ツイートに対応（次の番号または末尾まで）
    tweets = []
    blocks = re.split(r'\n(?=\d+[\.\)])', raw.strip())
    for block in blocks:
        text = re.sub(r'^\d+[\.\)]\s*', '', block).strip()
        if text and len(text) <= MAX_TWEET_LENGTH * 2:
            tweets.append(text)
    return tweets


def score_tweet(tweet: str) -> int:
    """バズりやすさのヒューリスティックスコア（高いほど良い）"""
    score = 0
    if any(c.isdigit() for c in tweet):
        score += 2  # 数字入り
    if '？' in tweet or '?' in tweet:
        score += 3  # 問いかけ
    if '：' in tweet or ':' in tweet:
        score += 2  # コロン（続きを読ませる）
    if any(w in tweet for w in ['変わる', '消える', '爆上がり', '衝撃', '本質', '気づき']):
        score += 2  # 感情トリガーワード
    if len(tweet) >= 60:
        score += 1  # 適度な長さ
    return score


def select_best_tweet(candidates: list[str]) -> str:
    """スコアが最も高い投稿を選択する"""
    if not candidates:
        return ""
    return max(candidates, key=score_tweet)


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}（URL は23文字換算）" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 「バズる投稿の構造分析」のいずれかのパターンを必ず使う
- ハッシュタグは1〜2個まで{link_instruction}
- ビジネス層（経営者・スタートアップ）が「いいね・RT したい」と思う内容に

{few_shot_section}
## Note記事本文
{note_text[:4000]}

## 出力形式
以下のJSON配列で出力すること（他の説明文は不要）:
["投稿案1のテキスト", "投稿案2のテキスト", "投稿案3のテキスト"]
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから見出しとリンクを取得し、AIトレンドとして重要度でソートして返す"""
    items: list[dict] = []
    seen_titles: set[str] = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue

    # バズりやすいキーワードで優先度付け
    priority_keywords = [
        'GPT', 'Claude', 'Gemini', 'OpenAI', 'Anthropic', 'Google',
        '規制', '医療', '雇用', '収益', '億円', 'AGI', 'エージェント',
        '2026', '最新', '衝撃', '革命', '廃止', '導入'
    ]

    def _priority(item: dict) -> int:
        t = item["title"]
        return sum(2 if kw in t else 0 for kw in priority_keywords)

    return sorted(items, key=_priority, reverse=True)[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースを元に投稿案を生成し、(候補リスト, 参照記事URL) を返す"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    top_link = items[0].get("link", "") if items else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内
- 「バズる投稿の構造分析」のパターンを活用する
- 医療×AI、社会変革、ビジネス変革の視点を絡める
- ハッシュタグは1〜2個まで
- ビジネス層が「シェアしたい・保存したい」と思う内容に

## 今日の最新AIニュース
{headlines_text}

## 出力形式
以下のJSON配列で出力すること（他の説明文は不要）:
["投稿案1のテキスト", "投稿案2のテキスト", "投稿案3のテキスト"]
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw), top_link


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

ルール:
- 各投稿は140文字以内
- Claude、GPT、医療AI、AGI、AIと社会変革などのテーマを優先
- ビジネス層が「シェアしたい」と思う内容に

## 出力形式
以下のJSON配列で出力すること（他の説明文は不要）:
["投稿案1のテキスト", "投稿案2のテキスト", "投稿案3のテキスト"]
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)
