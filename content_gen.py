"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+Claude+OpenAI+GPT&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+エージェント+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=Anthropic+OpenAI+Google+AI+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアDX+デジタル医療&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHRへのブロックチェーン活用、非中央集権的医療データ管理を研究
- スイスの大学での研究経験、国連会議参加 — グローバル視点
- Claude Codeなど最新AIツールを実業務で活用中
- 課題解決志向、読者に問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_STRATEGY = """
## 2026年バズるAI投稿の戦略（最新版）

### フォーマット優先順位
1. 【衝撃の事実 + 問い】→ 「〇〇が△△になった。これは××を意味する。あなたはどう思う？」
2. 【数字で語る】→ 具体的な数字・データで権威性を演出（例: 「Anthropic 年収477億ドル」）
3. 【逆張り・反直感】→ 多数意見への反論が議論を呼ぶ
4. 【個人の失敗談 × 学び】→ 「〜で失敗した。気づいたのは〜」形式が拡散しやすい
5. 【未来予測 × 根拠】→ 「2027年末までに〜になる。なぜなら〜」

### フックの法則（1行目が命）
- 数字から始める: 「47.7兆ドル。」「3つのことを学んだ。」
- 問いから始める: 「なぜ医師はAIを恐れるのか？」
- 逆説から始める: 「AIが進化するほど、人間の価値は上がる。」
- 体験から始める: 「昨日、Claude Codeに驚かされた。」

### ハッシュタグ戦略
- ハッシュタグは末尾に1〜2個のみ（本文に入れない）
- 使うなら: #AI #生成AI #医療DX #AIエージェント のいずれか

### 禁止事項
- 「〜しましょう！」系の啓発口調
- 「〜についてまとめました」系のまとめ投稿感
- 体言止めの羅列だけ
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    # 番号付きリスト行を抽出（複数行にわたる場合も対応）
    candidates: list[str] = []
    current: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current:
                tweet = " ".join(current).strip()
                if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                    candidates.append(tweet)
            current = [re.sub(r"^\d+[\.\)]\s+", "", stripped)]
        elif current and stripped and not re.match(r"^#+", stripped):
            current.append(stripped)

    if current:
        tweet = " ".join(current).strip()
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            candidates.append(tweet)

    # 抽出できなかった場合は140字以内の行を全て候補に
    if not candidates:
        for line in raw.splitlines():
            t = line.strip()
            if 20 < len(t) <= MAX_TWEET_LENGTH and not t.startswith("#"):
                candidates.append(t)

    return candidates[:NUM_CANDIDATES]


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
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力、1案につき1行
- ハッシュタグは末尾に1〜2個まで
- 1行目のフックが命。数字・問い・逆説のいずれかで始める{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
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
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力、1案につき1行
- 1行目のフック（数字・問い・逆説）で読者を止める
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは末尾に1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成（2026年最新トレンド対応）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月現在のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

現在の主要トレンド（参考情報）:
- OpenAI「GPT-5.6」(Sol/Terra/Luna) 一般公開
- Anthropic 年換算収益477億ドル到達
- Claude Code がプロンプト80%削減を実現
- AIエージェントが医療・法務・金融で実装フェーズへ
- モデル競争が「性能」から「価格性能比」へ移行

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力、1案につき1行
- 上記トレンドから最も刺さる切り口を選ぶ
- ハッシュタグは末尾に1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
