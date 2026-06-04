"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # ビジネス×AI特化
    "https://news.google.com/rss/search?q=AI+ビジネス+DX+経営+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+企業+導入+効率化&hl=ja&gl=JP&ceid=JP:ja",
    # 最新技術トレンド
    "https://news.google.com/rss/search?q=ChatGPT+Claude+OpenAI+Gemini+最新&hl=ja&gl=JP&ceid=JP:ja",
    # 医療×AI（著者の専門領域）
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI+診断AI&hl=ja&gl=JP&ceid=JP:ja",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
    "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
]

MAX_TWEET_LENGTH = 260  # X制限280文字、URLは23文字換算のためバッファ込み
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
## ビジネス層に刺さるバズりやすいAI投稿戦略

### ターゲット: 経営者・管理職・ビジネスパーソン（30〜50代）

### バズる投稿の必勝パターン（必ずいずれかの構造を使うこと）:

【パターン1】数字フック型 ─ 具体的な数字で驚きと説得力を出す
例: "AIで月40時間→8時間になった。浮いた32時間を新規開拓に使えば、競合との差は縮まらない。時間コストを減らすより、何に再投資するかが経営の本質。 #AI"

【パターン2】逆説・反直感型 ─ 「そうだったのか」と思わせる
例: "AIが賢くなるほど、人間の判断力の価値が上がる。全自動化が進むほど、最終意思決定できる人材が希少になる。AIと人間は競合ではなく、希少性の再分配だ。 #生成AI"

【パターン3】問いかけ型（RTされやすい） ─ 読者に鋭い問いを投げる
例: "競合他社は今日もAIで差をつけている。3年後、AIなしで同じ土俵で戦えると思うか？ #AI"

【パターン4】未来予測型 ─ 具体的な年号で現実感を出す
例: "2027年、AIを使いこなせないビジネスパーソンは希少種になる。今は珍しくても、3年後は『使えて当然』になる。その変化はもう始まっている。 #生成AI"

【パターン5】ビフォーアフター対比型 ─ 劇的な変化を対比で体感させる
例: "AIなし: 週5日、同じ作業を繰り返す。AIあり: 1日で完了し、残り4日を価値創造に使う。これが現代のレバレッジ。仕事の密度が競争力になる時代。 #AI"

【パターン6】専門的洞察型（シェアされやすい） ─ 業界内側からの真実
例: "プロンプト設計の差は、AIが賢くなるほど広がる。ツールの精度より、問いの質が競争力になる。ChatGPTを使える人は増えても、上手く使える人は増えない。 #生成AI"

【パターン7】警告・FOMO型 ─ 行動を促す危機感
例: "今AIを無視している企業は3年後に後悔する。技術より怖いのは、競合がAIで差をつける速度。 #AI"

### 共通ルール:
- 結論より「問い」や「示唆」で終わるとRTされやすい
- ハッシュタグは #AI または #生成AI の1〜2個まで（文末に配置）
- リンクをつける場合は文末（URLは23文字換算、テキストは200文字以内に収める）
- 投稿は【バズ期待度が高い順】に出力すること（1番目が最もバズりやすい案）
- 絵文字は使わない（著者のトーンに合わない）
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
    """番号付きリストから投稿文を抽出し文字数制限内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = (
        f"\n- 文末にNoteリンクを入れてもよい: {note_url}（URLは23文字換算）"
        if note_url
        else ""
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

追加ルール:
- 各投稿はテキスト200文字以内（URLを含む場合はURL=23文字換算で計250文字以内）
- 番号付きリスト（1. 2. 3.）で出力
- ビジネスパーソンに刺さる洞察を、著者のプロフィールと重ねて表現{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[tuple[str, str]]:
    """最新AIニュースのタイトルとURLを取得"""
    items: list[tuple[str, str]] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append((title, link))
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for title, link in items:
        if title not in seen:
            seen.add(title)
            unique.append((title, link))
    return unique[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(
        f"- {title}" + (f" | URL: {link}" if link else "")
        for title, link in items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネスパーソン（経営者・管理職）に刺さる洞察をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

追加ルール:
- 各投稿はテキスト200文字以内（URLを含む場合はURL=23文字換算で計250文字以内）
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、ビジネス変革、社会変革などの視点を絡めると尚良い
- 記事URLを含める場合は文末のみ（URLは23文字換算）

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
経営者・管理職・ビジネスパーソンに刺さる深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

追加ルール:
- 各投稿はテキスト200文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT-4o、医療AI、AIと経営変革などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
