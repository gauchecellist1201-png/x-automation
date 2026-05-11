"""
Claude API を使った戦略的投稿文生成モジュール v2
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けAI投稿 - バズるパターン分析・RSS最新情報対応
"""

import os
import re
import feedparser
import anthropic

# ─────────────────────────────────────────
# RSS フィード（日英・AI×ビジネス特化）
# ─────────────────────────────────────────
RSS_FEEDS = [
    # 日本語：AI×ビジネス・最前線
    "https://news.google.com/rss/search?q=AI+活用+企業+ビジネス+成果+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+Claude+ChatGPT+Gemini+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+自動化+業務効率&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルステック+診断+創薬&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+規制+倫理+社会課題+日本&hl=ja&gl=JP&ceid=JP:ja",
    # 英語：最速AI情報（日本より先行）
    "https://news.google.com/rss/search?q=AI+agent+enterprise+productivity+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+release+model&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+healthcare+medical+diagnosis+breakthrough&hl=en&gl=US&ceid=US:en",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

# ─────────────────────────────────────────
# 著者プロフィール
# ─────────────────────────────────────────
AUTHOR_PROFILE = """
## 著者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス研究経験・国連会議参加のグローバル視点
- 「静かに鋭い洞察」を届けるスタイル
- 押しつけがましくなく、読者に考えさせる「問い」を大切にする
- チェリスト：感性と論理を両立させる人間
"""

# ─────────────────────────────────────────
# バズるツイートのパターン辞書（実績ベース）
# ─────────────────────────────────────────
VIRAL_PATTERNS = """
## バズる投稿の7パターン（エンゲージメント順）

【S級 ① 衝撃反転型】保存・RT最多
「[驚きの事実]。でも[意外な反転・逆説]。[示唆]」
例: 「AIは1日1億回使われている。でも業務フローに組み込んでいる企業は全体の5%未満。
道具を持つことと使いこなすことは、まったく別の話だ。」

【S級 ② ビフォーアフター型】共感→行動変容を促す
「◼ AI導入前: [苦労・非効率・時間]
◼ AI導入後: [劇的変化・時間短縮・成果]
[一行の深い示唆]」

【A級 ③ 数字フック型】自分ごと化されやすい
「[具体的な数字]%の[対象者]が[まだやっていないこと]。
[洞察・なぜ重要か]」

【A級 ④ 問いかけ終わり型】コメント・引用RT誘発
「[鋭い洞察や事実]。
[深い問いかけ]？ #AI」

【A級 ⑤ リスト型】保存・ブックマーク率が高い
「AIで変わる[業界/職種]Top3：
① [変化1]
② [変化2]
③ [変化3]
[問いor示唆] #生成AI」

【B級 ⑥ 逆張り型】議論・引用RT多い
「AIに[仕事/未来]を奪われない人の共通点は、
[スキルや技術]ではなく[意外な要素]だった。」

【B級 ⑦ 未来予言型】ブックマーク・保存率高い
「[具体的な時期]、[業界・職種・社会]は[大胆な予測]になる。
今から[具体的にすべきこと]だけが生き残る。」
"""

# ─────────────────────────────────────────
# 投稿ルール
# ─────────────────────────────────────────
TWEET_RULES = """
## 投稿ルール（必ず守る）
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは末尾に1〜2個のみ（#AI #生成AI #医療AI から選ぶ）
- 改行・スペースを使いモバイルで読みやすくする
- 数字・%・企業名・モデル名を入れると信頼性UP
- 「です・ます」より体言止め・余白を活かした表現
- 最初の一文で「読む価値がある」と思わせること（フック）
- 医療・社会変革・未来への視点を1つ絡めると尚良い
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
    """番号付きリスト or 【案N】形式からツイートを抽出し140文字以内に絞る"""
    tweets: list[str] = []

    # 【案N】形式
    blocks = re.split(r"【案\d+】", raw)
    if len(blocks) > 1:
        for block in blocks[1:]:
            text = block.strip().split("\n\n")[0].strip()
            if text and len(text) <= MAX_TWEET_LENGTH:
                tweets.append(text)
        if tweets:
            return tweets[:NUM_CANDIDATES]

    # 番号付きリスト形式（1. / 1) など）
    for line in raw.splitlines():
        line = line.strip()
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
        if cleaned and 10 < len(cleaned) <= MAX_TWEET_LENGTH:
            tweets.append(cleaned)

    # 上記で取れない場合は段落ごとに分割
    if not tweets:
        for para in raw.split("\n\n"):
            para = para.strip()
            para = re.sub(r"^\d+[\.\)]\s*", "", para)
            if para and 10 < len(para) <= MAX_TWEET_LENGTH:
                tweets.append(para)

    return tweets[:NUM_CANDIDATES]


def _extract_tweets_with_pattern(raw: str) -> list[tuple[str, str]]:
    """(ツイート本文, 使用パターン名) のリストを返す"""
    # パターン名を検出
    pattern_map = {
        "衝撃反転": "衝撃反転型",
        "ビフォーアフター": "ビフォーアフター型",
        "数字フック": "数字フック型",
        "問いかけ": "問いかけ終わり型",
        "リスト": "リスト型",
        "逆張り": "逆張り型",
        "未来予言": "未来予言型",
    }

    results: list[tuple[str, str]] = []
    blocks = re.split(r"【案\d+】", raw)

    for block in blocks[1:]:
        detected_pattern = "不明"
        for key, name in pattern_map.items():
            if key in block:
                detected_pattern = name
                break

        # ツイート本文を取得（パターン名行を除く）
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        tweet_lines = [l for l in lines if not any(k in l for k in pattern_map)]
        tweet = "\n".join(tweet_lines).strip()
        if tweet and len(tweet) <= MAX_TWEET_LENGTH:
            results.append((tweet, detected_pattern))

    if not results:
        tweets = _extract_tweets(raw)
        results = [(t, "自動検出") for t in tweets]

    return results[:NUM_CANDIDATES]


# ─────────────────────────────────────────
# Note記事からの投稿生成
# ─────────────────────────────────────────
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
                f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"
            )

    link_part = f"\n- 文末にNoteリンクを自然に入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_RULES}

出力形式（必ずこの形式で）:
【案1】[使用パターン: ○○型]
[ツイート本文]

【案2】[使用パターン: ○○型]
[ツイート本文]

【案3】[使用パターン: ○○型]
[ツイート本文]

追加指示:
- 3案それぞれ異なるパターンを使うこと
- ビジネス経営者・医療従事者・スタートアップ創業者に刺さる内容に{link_part}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_notes_with_meta(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[tuple[str, str]]:
    """(ツイート, パターン名) 付きで返すバージョン"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿\n{examples}\n"
            )

    link_part = f"\n- 文末にNoteリンクを自然に入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_RULES}

出力形式（必ずこの形式で）:
【案1】[使用パターン: ○○型]
[ツイート本文]

【案2】[使用パターン: ○○型]
[ツイート本文]

【案3】[使用パターン: ○○型]
[ツイート本文]

追加指示:
- 3案それぞれ異なるパターンを使うこと{link_part}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets_with_pattern(raw)


# ─────────────────────────────────────────
# RSS フィード取得
# ─────────────────────────────────────────
def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS から見出し+リンクを取得"""
    items: list[dict] = []
    seen: set[str] = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue
        if len(items) >= max_items:
            break

    return items[:max_items]


# ─────────────────────────────────────────
# RSSニュースからの投稿生成
# ─────────────────────────────────────────
def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースから @GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    top_link = items[0]["link"] if items else ""
    link_note = f"\n- 最も注目した記事のURLを文末に入れてもよい（23文字換算）: {top_link}" if top_link else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい鋭い洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_RULES}

出力形式（必ずこの形式で）:
【案1】[使用パターン: ○○型]
[ツイート本文]

【案2】[使用パターン: ○○型]
[ツイート本文]

【案3】[使用パターン: ○○型]
[ツイート本文]

追加指示:
- 3案それぞれ異なるパターンを使うこと
- 医療×AI・社会変革・未来への問いを1つ絡めると尚良い
- ビジネス経営者・スタートアップ創業者が「保存・RT」したくなる内容に{link_note}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss_with_meta() -> tuple[list[tuple[str, str]], str]:
    """(ツイート, パターン名) リスト と 参照ニュース見出しを返す"""
    items = fetch_rss_headlines()
    if not items:
        tweets = _generate_original_ai_insight()
        return [(t, "自動生成") for t in tweets], "（RSS取得失敗、オリジナル洞察）"

    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    top_link = items[0]["link"] if items else ""
    link_note = f"\n- 最も注目した記事のURLを文末に入れてもよい（23文字換算）: {top_link}" if top_link else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい鋭い洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_RULES}

出力形式（必ずこの形式で）:
【案1】[使用パターン: ○○型]
[ツイート本文]

【案2】[使用パターン: ○○型]
[ツイート本文]

【案3】[使用パターン: ○○型]
[ツイート本文]

追加指示:
- 3案それぞれ異なるパターンを使うこと
- 医療×AI・社会変革・未来への問いを1つ絡めると尚良い{link_note}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    results = _extract_tweets_with_pattern(raw)
    selected_headline = items[0]["title"] if items else ""
    return results, selected_headline


# ─────────────────────────────────────────
# フォールバック：オリジナル洞察
# ─────────────────────────────────────────
def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_RULES}

出力形式（必ずこの形式で）:
【案1】[使用パターン: ○○型]
[ツイート本文]

【案2】[使用パターン: ○○型]
[ツイート本文]

【案3】[使用パターン: ○○型]
[ツイート本文]

優先テーマ（いずれか1つ選ぶ）:
- AIエージェントと人間の協働の未来
- 医療AIが変える診断・創薬の現実
- ビジネスにおけるAI活用格差（勝ち組と負け組）
- Claude/GPTなど最新モデルが変えた働き方
- AI時代に「人間にしかできないこと」とは何か
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
