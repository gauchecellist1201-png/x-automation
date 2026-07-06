"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+Fable&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+医療AI+AI規制+AIガバナンス&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    "https://news.google.com/rss/search?q=AI+productivity+ROI+enterprise+2026&hl=ja&gl=JP&ceid=JP:ja",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3
THREAD_TWEETS = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- PHR/EHRへのブロックチェーン活用、非中央集権的医療データ管理を研究・実装
- スイスの大学での研究経験、国連会議参加など、グローバル視点
- 2026年現在、Claude Codeなど最新AIツールを医療×AI×ブロックチェーン領域で活用
- 課題解決志向、専門的知識を一般読者にも届けるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TWEET_STRATEGY = """
## 2026年版バズるAI投稿戦略（最新アルゴリズム対応）

### アルゴリズム理解（必須）
- 最初の30〜60分のエンゲージメント速度が全て。
- 返信は「いいね」の150倍の評価 → 議論を呼ぶ投稿、問いかけで終わる投稿が最強。
- ハッシュタグは効果薄（X社のNLPが自動分類するため不要）。使うなら1個まで。
- スレッド形式は単発ツイートよりエンゲージメントが高い。

### フック（1行目）の型
- 断言系: 「○○は終わった」「これが真実だ」「正直に言う」
- 数字系: 「150倍」「3つの事実」「2026年最重要の変化」
- 逆説系: 「AIに仕事を奪われる、は間違い」「〜と思っていたが、全く逆だった」
- 緊急系: 「今知らないと手遅れになる」「5年後に後悔する人が出る」

### ビジネス層に刺さるテーマ
- ROI・生産性の数値（「○○%向上」「週○時間削減」）
- リスク・脅威（「知らないと損する」「Death by AI訴訟、Gartner予測2000件超」）
- 格差（「AIを使う人 vs 使わない人の差が取り返せなくなる」）
- 医療×AI（「医師10万人分の知識を持つAIがなぜ現場で使われないか」）
- データ主権（「医療データは誰のもの？」）

### やってはいけない
- 「〜でしょうか？」「〜かもしれません」→ 曖昧さはリーチを殺す
- 結論を最後に隠す → 最初に結論、後で根拠
- ハッシュタグ多用（0〜1個）
- URL貼りすぎ（リーチが下がる、貼る場合は1つ）
"""

VIRAL_HOOKS = [
    "正直に言う。",
    "AIを使っている人と使っていない人の差が、来年から取り返しのつかない差になる。",
    "誰も言わないが、",
    "これが2026年最重要の変化だ。",
    "医師として断言する。",
    "データが示す事実を言う。",
]


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def _extract_thread(raw: str) -> list[str]:
    """スレッド形式（1/ 2/ ...）から各ツイートを抽出する"""
    tweets = []
    current = []
    for line in raw.splitlines():
        m = re.match(r"^(\d+)/\s*(.*)", line.strip())
        if m:
            if current:
                tweets.append("\n".join(current).strip())
            current = [m.group(2)] if m.group(2) else []
        elif current and line.strip():
            current.append(line.strip())
    if current:
        tweets.append("\n".join(current).strip())
    return [t for t in tweets if t]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 必要なら文末にNoteリンクを1つだけ: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- フックは上記の型を参考に、最初の一文で読者を引き込む
- ハッシュタグは0〜1個まで
- 問いかけ・断言・逆説を混ぜて{NUM_CANDIDATES}案作ること{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_from_rss(headlines: list[str]) -> list[str]:
    """最新AIニュースから、バズるスレッド形式の投稿を生成する"""
    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
Xスレッド（連続投稿）形式で{THREAD_TWEETS}ツイートのスレッドを1本作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッドのルール:
- 「1/ 」「2/ 」...「{THREAD_TWEETS}/ 」の形式で各ツイートを出力
- 1ツイート目: 衝撃的なフックで読者を引き込む（140文字以内）
- 2〜{THREAD_TWEETS-1}ツイート目: 洞察・データ・具体例を展開（各140文字以内推奨、少し超えてもOK）
- 最終ツイート: 問いかけ or 行動を促すCTA（フォロー・RT誘導、140文字以内）
- ハッシュタグは最終ツイートに1個のみ可
- 医療×AI、ビジネス変革、社会的インパクトの視点を入れる

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_thread(raw)


def fetch_rss_headlines(max_items: int = 12) -> list[str]:
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


def generate_posts_from_rss() -> tuple[list[str], list[str]]:
    """最新AIニュースを元に単発ツイート案3本 + スレッド案1本を生成。
    Returns: (single_tweets, thread_tweets)
    """
    headlines = fetch_rss_headlines()
    if not headlines:
        singles = _generate_original_ai_insight()
        thread = _generate_original_thread()
        return singles, thread

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    # 単発ツイート案
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 案ごとに違うフックの型を使うこと（断言型・逆説型・数字型など）
- ハッシュタグは0〜1個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    singles = _extract_tweets(raw)

    # スレッド案
    thread = generate_thread_from_rss(headlines)
    return singles, thread


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
- AIエージェント、医療AI、AIガバナンス、Death by AI訴訟、Claude Fable 5などのテーマを優先
- 案ごとに違うフックの型を使う
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_thread() -> list[str]:
    """RSSが取得できない場合のオリジナルスレッド生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年現在、最もビジネス層の心を動かすAIテーマについて、
Xスレッド（{THREAD_TWEETS}ツイート連続投稿）を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

フォーマット: 「1/ 」〜「{THREAD_TWEETS}/ 」で各ツイートを出力。
テーマ候補: AIエージェントと経営判断、医療データ主権とブロックチェーン、
Death by AI訴訟リスク、AIを使う人と使わない人の格差、Fable 5の意味など。
"""
    raw = _call_claude(prompt)
    return _extract_thread(raw)
