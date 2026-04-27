"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズる投稿パターン分析 × 最新AIニュース × スレッド生成対応版
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AI速報（一次ソース）
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Claude+Gemini+AI+model&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/venturebeat/SZYF",
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

VIRAL_PATTERNS = """
## バズるAI投稿の黄金パターン（ビジネス層向け・分析済み）

【P1: 衝撃スタート型】数字・ファクトで始めてスクロールを止める
例:「企業のAI導入率は80%超だが、ROIを実感できた担当者は20%未満という調査がある。問題は道具ではなく、使い方を誰も教えていないこと。 #AI」

【P2: 逆張り・反論型】常識に反論して議論を生む
例:「『AIは仕事を奪う』は半分間違い。正確には、AIを使う人間が使わない人間を置き換える。格差の軸が変わっただけ。 #AI」

【P3: 問いかけ型】返信・RTが自然に増える
例:「医師がAIの診断を信頼するには何が必要か。技術より先に制度と倫理の整備が必要だと思う。あなたはどう考えますか？ #医療AI」

【P4: リスト型】保存・引用RTが増える最強フォーマット
例:「2026年、ビジネス必須AIツール3選：①Claude-長文分析 ②Perplexity-リサーチ ③NotebookLM-情報整理。まだ使っていない理由が見つからない。 #生成AI」

【P5: ストーリー×洞察型】共感・シェアが増える
例:「医学部の試験でAI活用した学生が最高点。教授は困惑した。でも臨床でAIを使いこなせる医師が最強になる時代、これは正しい適応だと思う。 #AI」

【P6: 速報反応型】タイムリーな情報に乗っかる
例:「【注目】○○社がAI新機能発表。精度が前世代比40%向上。医療診断への実装が加速しそう。ゲームチェンジャーになり得る。 #AI」

【P7: ビフォーアフター型】変化のインパクトを可視化する
例:「AI導入前後：Before→論文サーベイ3時間 / After→15分でエッセンス把握。残り2時間45分をどう使うかが今問われている。 #生成AI」
"""

TWEET_STRATEGY = """
## 投稿戦略
1. 最初の一文でスクロールを止める（強いフック必須）
2. 専門的だが難解すぎない言葉選び
3. 医療・社会変革・ビジネス価値・未来への問いを絡める
4. 感情（驚き・共感・危機感・希望）を喚起する
5. ハッシュタグは #AI #生成AI #医療AI のうち1〜2個まで
6. 経営者・医療従事者・スタートアップ起業家に刺さる内容優先
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_len: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数制限内のものだけ返す"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_len]


def fetch_rss_items(max_items: int = 8) -> list[dict]:
    """RSS記事をタイトル・URLとともに取得"""
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
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def fetch_rss_headlines(max_items: int = 8) -> list[str]:
    return [item["title"] for item in fetch_rss_items(max_items)]


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
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- 上記バズパターン（P1〜P7）のいずれかを意識して使う
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_items()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、ビジネス価値の観点を絡める
- 上記バズパターン（P1〜P7）のいずれかを意識して使う
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_viral_thread(topic: str, details: str) -> list[str]:
    """スレッド形式の投稿を生成（最大5ツイート）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、Xのスレッド形式投稿を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッド構成ルール:
- 1ツイート目: 強烈なフック（スクロールを止める一文、「🧵」で始めるとなお良い）
- 2〜4ツイート目: 洞察・データ・事例（本論）
- 最終ツイート（5）: まとめ or 問いかけ or CTA
- 各ツイートは140文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- スレッド全体で一つのストーリーを作る

## トピック
{topic}

## 詳細情報
{details[:2000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw, max_len=140)


def suggest_image(tweet: str) -> str:
    """投稿に最適な画像・メディアのアイデアを1行で提案"""
    prompt = f"""以下のX投稿に最適な添付画像・メディアを1行で提案してください（日本語・具体的に）。
例:「AIとビジネスマンが握手するイメージ図」「グラフ：AI導入企業と非導入企業の売上比較」「スクショ：Claude/ChatGPTの実際の使用画面」

投稿文:
{tweet}

画像提案（1行のみ・具体的に）:"""
    result = _call_claude(prompt).strip()
    return result.split("\n")[0]


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、医療AI、AIと社会変革などのテーマを優先
- 上記バズパターン（P1〜P7）のいずれかを意識して使う
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
