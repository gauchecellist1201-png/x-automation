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
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+生産性+DX+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加（グローバル視点）
- 専門的知識を持ちながら、読者に「考えさせる問い」を投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- AIが民主化することで医師・医学生がコードなしで医療プロダクトを作れる時代の伝道者
"""

VIRAL_PATTERNS_2026 = """
## 2026年にバズるX投稿の鉄則

### 最重要：最初の7語でスクロールを止める
フックのタイプ（どれか1つを必ず使う）:
- 【逆説型】常識・思い込みを否定する（例：「AIで仕事が増えた、は嘘じゃない」）
- 【数字型】具体的な数字で説得力を出す（例：「Claudeが前年比855%成長」）
- 【格差型】AIを使う人 vs 使わない人の差を可視化する
- 【問い型】「え、どういうこと?」と思わせる問いかけ
- 【告白型】個人の経験・失敗から始まる意外な事実

### エンゲージメントを生む要素（2026年X最新アルゴリズム）
- リプライは「いいね」の27倍重み付けされる→議論を生む投稿が最強
- 少し挑発的・意見性の強い内容がリプを呼ぶ
- 「〇〇だと思ってたけど実は〜」という認知の更新が最もRTされやすい
- ビジネス層には「生産性」「競合格差」「コスト削減」のワードが刺さる
- 医療層には「患者データ」「AIの限界」「医師の役割」が刺さる

### 2026年7月の旬トピック（積極的に使う）
- Claude（Anthropic）が前年比855%成長、2月〜5月で228%増
- ChatGPTの世界シェアが初めて50%割れ（46.4%）、GeminiとClaudeが追い上げ
- GPT-5.6ファミリー（Sol/Terra/Luna）プレビュー公開（米政府限定）
- Gemini 3.5 Pro 7月正式リリース
- UN AI ガバナンス会議 ジュネーブで開幕（7月6日）
- AIエージェントが「デモ映え」から「実務完遂」フェーズへ移行
- AI活用企業 vs 非活用企業の生産性格差が数値化され始める
- 核融合・太陽光専用データセンターへのAI計算需要集中
"""

TWEET_STRATEGY = """
## 投稿フォーマット戦略

1. 単発ツイート（140文字以内）
   - 最初の7語でフック → 核心を1文で → 問いか余韻で締める
   - ハッシュタグ1〜2個を末尾に

2. スレッド冒頭ツイート（140文字以内、単体でも成立）
   - 「〇つの理由」「〇つのこと知らなかった」形式
   - 続きを読みたくなる問題提起

3. 数字・データ型ツイート
   - 具体的な数値を先頭に
   - 「なぜそうなるか」を一言で補足

ハッシュタグは #AI #生成AI #医療AI のうち最大1〜2個のみ
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
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
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを自然に入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS_2026}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力、本文のみ（説明不要）
- ハッシュタグは1〜2個まで
- 最初の7語で読者のスクロールを止めること
- ビジネス層・医療層に刺さる洞察{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


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
    """最新AIトレンドニュースを元に @GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS_2026}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力、本文のみ（説明不要）
- 医療×AI、ビジネス格差、社会変革、未来への問いを絡める
- ハッシュタグは1〜2個まで
- 最初の7語で読者のスクロールを止めること
- ビジネス層（経営者・起業家・マーケター）と医療層の両方に響く内容

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def generate_thread_opener(topic: str) -> list[str]:
    """スレッド冒頭ツイート（連ツイ1枚目）を生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、Xスレッド冒頭ツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS_2026}

要件:
- 140文字以内
- 単体でも成立するが「続きを読みたい」と思わせる
- 「〇つのこと」「〇ステップで〜」「なぜ〇〇なのか」形式も有効
- 番号付きリスト（1. 2. 3.）で出力、本文のみ
- ハッシュタグ1〜2個まで

## トピック
{topic}
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月のAI業界の最前線について、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS_2026}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力、本文のみ
- Claude/GPT/Geminiの競合構図、医療AI、AIと社会変革のテーマを優先
- 最初の7語でスクロールを止める
- ビジネス層・医療層に刺さる洞察を含む
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)
