"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース（高品質ソース）
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+エージェント+LLM&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+診断&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（グローバルトレンド）
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求する
- スイス留学・国連会議参加などグローバル視点を持つ
- 専門知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- ターゲット：ビジネス層・医療従事者・スタートアップ関係者
"""

VIRAL_TWEET_PATTERNS = """
## バズるX投稿の型（必ずいずれかを使うこと）

【型1: 逆説・カウンターインテューイティブ型】
「AIが○○できる時代に、なぜ私たちは××を続けるのか」
「○○と思われているが、実は△△だ」
→ 常識を疑わせる切り口。RTされやすい。

【型2: 数字・具体性型】
「AIで変わる医療の3つの現実」「知らないと損するAI活用法5選」
「○○するだけで生産性が2倍になった、たった1つの習慣」
→ 具体的な数字で信頼感と期待感を作る。

【型3: 速報・解説型】
「○○が発表された。これが意味することを医師の視点で解説する」
「今週のAI業界で最も重要なニュースは○○だった」
→ 最新ニュースに自分の解釈を加える。専門家らしさが際立つ。

【型4: 問いかけ・議論誘発型】
「AIが医師を超えた時、医師の価値は何になるのか」
「あなたはAIと共存できる側の人間ですか？」
→ 答えを言わない。読者に考えさせる。コメントが増える。

【型5: パーソナル体験型】
「医学生の自分がAIで○○したら、想像以上の結果になった」
「半年前まで○○できなかった私が、今日○○した」
→ 一人称で体験を語る。共感と好奇心を同時に引き出す。

【型6: 予測・未来型】
「2027年、○○は確実に変わる。準備できていますか？」
「5年後、AIを使えない医師は存在できなくなる」
→ 読者に行動を促す。フォロー率が上がる。

【型7: 比較・対比型】
「AIあり vs なし。同じ業務でこれだけ違う」
「ChatGPT vs Claude。医療現場ではどちらが使えるか」
→ 対比で差を際立たせる。わかりやすく拡散されやすい。
"""

TWEET_STRATEGY = """
## 投稿戦略
- 140文字以内に収める（URLは23文字換算）
- 冒頭1文が命。最初の20文字でスクロールを止める強いフックを入れる
- 専門的だが難解すぎない言葉選び
- ハッシュタグは #AI #生成AI #医療DX のうち1〜2個まで
- 結論より「問い」で終わるとRTされやすい
- ビジネス層が「へえ、知らなかった」「保存しよう」と感じる情報を選ぶ
- 感嘆符・大げさな表現は避け、落ち着いた鋭さを保つ
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
    candidates: list[str] = []
    current_lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            # 前のエントリを確定
            if current_lines:
                tweet = " ".join(current_lines).strip()
                if 10 < len(tweet) <= MAX_TWEET_LENGTH:
                    candidates.append(tweet)
            text = re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()
            current_lines = [text] if text else []
        elif stripped and current_lines:
            # 継続行（複数行ツイートの場合）
            tentative = " ".join(current_lines + [stripped])
            if len(tentative) <= MAX_TWEET_LENGTH:
                current_lines.append(stripped)

    if current_lines:
        tweet = " ".join(current_lines).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            candidates.append(tweet)

    # フォールバック：番号なし短文から抽出
    if not candidates:
        candidates = [
            l.strip()
            for l in raw.splitlines()
            if 20 < len(l.strip()) <= MAX_TWEET_LENGTH
            and not l.strip().startswith("#")
        ]

    return candidates[:NUM_CANDIDATES]


def extract_note_url(note_text: str) -> str:
    """Note本文から NOTE_URL: 行を抽出して返す"""
    for line in note_text.splitlines():
        if line.strip().startswith("NOTE_URL:"):
            return line.replace("NOTE_URL:", "").strip()
    return ""


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてよい（23文字換算）: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力し、それ以外の説明文は不要
- ハッシュタグは1〜2個まで
- 上記「バズる型」のいずれかを明示的に使うこと
- AIに関するプロレベルの洞察を、一般読者にも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから見出しとURLを取得"""
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
    # 重複タイトル除去
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成。
    返り値: (投稿案リスト, 選ばれた記事タイトル)
    """
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {it['title']}" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力し、それ以外の説明文は不要
- 上記「バズる型」のいずれかを明示的に使うこと
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_best_tweet(raw)

    # 選ばれた記事タイトルをClaudeのレスポンスから推測（最初のニュース見出し近似）
    chosen_title = items[0]["title"] if items else ""
    return posts, chosen_title


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力し、それ以外の説明文は不要
- 上記「バズる型」のいずれかを明示的に使うこと
- Claude、GPT、医療AI、AIエージェント、AIと社会変革などを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
