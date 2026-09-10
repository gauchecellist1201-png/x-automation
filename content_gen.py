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
    "https://news.google.com/rss/search?q=AIエージェント+医療AI+ビジネスAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向けユーザー獲得最優先）

### 拡散しやすいフォーマット（優先順）
1. 「数字で驚かす」型：「〇〇が△△%削減」「〇〇社が〇〇円投資」などの具体的数値
2. 「逆説・意外性」型：「AIに仕事を奪われる？実は〇〇の仕事が増えている」
3. 「問いかけ」型：結論を言わずに読者に考えさせる。RTされやすい
4. 「専門家視点の告白」型：「医学生として言う。AIの〇〇は使えない。でも〇〇は本物だ」
5. 「未来予測」型：「2027年、〇〇は消える。その理由は」
6. 「Before/After」型：「AIを導入する前→後」の対比で価値を可視化

### 言葉選びのルール
- 専門用語は1投稿に1個まで、必ず一言で定義する
- ビジネス層が「これうちの会社に使える」と思う具体性
- 医療×AI×社会変革を絡めると井出直毅らしさが出る
- 「〇〇の本質は△△」「実は〇〇」「誰も言わないが〇〇」で始めると開封率アップ

### ハッシュタグ
- #AI #生成AI #AIエージェント #医療AI のうち1〜2個のみ
- 文末に自然に配置

### リンク・メディア活用
- Note記事URLを貼る場合は文末に「→ （URL）」形式で
- 統計や図表を引用する場合は出典を明記
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_best_tweet(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    # 140文字超でも160文字以内ならURLを考慮して許容
    return [t for t in lines if 0 < len(t) <= 160]


def generate_viral_analysis(note_text: str) -> str:
    """記事からバズ要素を分析し、画像・リンク活用案を返す"""
    prompt = f"""以下のAI記事から、X（Twitter）でバズるための戦略を分析してください。

## 分析して欲しい内容（箇条書きで簡潔に）
1. 最も拡散しそうな「数字・統計・事実」を3つ抽出
2. 推奨する投稿フォーマット（問いかけ型/数値型/逆説型）
3. 添付すると効果的な画像・図表のアイデア（生成AIで作れるものを提案）
4. 関連リンク候補（引用すべき公式発表・論文・ニュースURL）

## 記事
{note_text[:3000]}
"""
    return _call_claude(prompt)


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
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- AIに関するプロレベルの洞察を、一般読者にも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 8) -> list[str]:
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
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
