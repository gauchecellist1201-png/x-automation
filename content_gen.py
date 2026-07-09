"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+生成AI+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+企業導入+業務効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=人工知能+医療AI+ヘルスケアDX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+自律AI+Anthropic+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    # グローバル視点
    "https://news.google.com/rss/search?q=AI+business+impact+enterprise+productivity+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大のテーマに活動
- スイス留学・国連会議参加など国際的視野を持つ
- Claude Codeなど最新AIツールを医療プロダクト開発に活用中
- 押しつけがましくなく、静かに鋭い洞察を問いとして届けるスタイル
"""

VIRAL_TWEET_PATTERNS = """
## バズるツイートの型（必ず以下の型のいずれかを使うこと）

【型A: 問いかけ型】← 最もRT・コメントが多い
「AIが○○になった時、私たちは○○を何と呼ぶのか？」
「○○が変わった時、△△は誰がやる？」
→ 答えを与えず余白を残す。読者が考えたくなる問いで終わる。

【型B: 対比・逆説型】← ビジネス層に刺さる
「凡人は○○に使う。プロは○○に使う」
「みんなが○○と思っているが、実は△△だ」
「○○が増えるほど、△△の価値が上がる逆説」

【型C: 数字・実績型】← 具体性でビジネス層の信頼を獲得
「AI導入で月○時間削減」「コスト○%削減」「○社に1社がすでに○○」
→ 具体的な数字で現実感を出す

【型D: 警告・予言型】← 共有・保存されやすい
「○年後、○○できない人は○○になる」
「今すぐ○○しないと、○○を後悔する」
→ 危機感を煽りすぎず、行動を促す

【型E: 衝撃事実・発見型】
「誰も教えてくれなかった事実：」「○○で気づいたこと：」
「AIのある使い方で、○○が劇的に変わった」

【型F: リスト型】← 保存率が高い
「AIで変わる医療の5つの現実」「今週使うべきAI活用法3選」
"""

CONTENT_RULES = """
## 投稿ルール
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは1〜2個まで（#AI #生成AI #ChatGPT から選ぶ）
- ビジネス層（経営者・管理職・起業家）が「共有したい」と思う内容
- 医療×AI、社会変革、未来予測を絡めると井出らしさが出る
- 答えより「問い」で終わると拡散しやすい
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_best_tweet(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る。複数行にまたがる場合も対応。"""
    tweets: list[str] = []
    current_parts: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_parts:
                tweet = " ".join(current_parts).strip()
                if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current_parts = [re.sub(r"^\d+[\.\)]\s+", "", stripped)]
        elif stripped and current_parts and not stripped.startswith("【"):
            current_parts.append(stripped)
        elif stripped.startswith("【") and current_parts:
            tweet = " ".join(current_parts).strip()
            if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                tweets.append(tweet)
            current_parts = []

    if current_parts:
        tweet = " ".join(current_parts).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets


def _extract_note_url(note_text: str) -> str:
    """Note記事本文からURLを抽出"""
    for line in note_text.splitlines():
        m = re.search(r"NOTE_URL:\s*(https?://\S+)", line)
        if m:
            return m.group(1)
    return ""


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    if not note_url:
        note_url = _extract_note_url(note_text)

    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = (
        f"\n- 最も適した1案の文末にNoteリンクを入れてよい: {note_url}" if note_url else ""
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層（経営者・管理職・起業家）に刺さりバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{CONTENT_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3. 4. 5.）で各案を出力
- 各案は異なる「型」（A〜F）を使うこと{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    headlines.append(title)
        except Exception:
            continue
    return headlines[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層（経営者・管理職・起業家）に刺さりバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{CONTENT_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3. 4. 5.）で各案を出力
- 各案は異なる「型」（A〜F）を使うこと
- 医療×AI、社会変革、ビジネス活用の視点を優先

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトレンドについて、
ビジネス層（経営者・管理職・起業家）に刺さりバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{CONTENT_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3. 4. 5.）で各案を出力
- 各案は異なる「型」（A〜F）を使うこと
- AIエージェント、医療AI、企業AI活用、AI×ブロックチェーンを優先テーマに
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
