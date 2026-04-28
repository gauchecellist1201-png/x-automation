"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import json
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI / ビジネス
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+診断&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語 AI 最前線（翻訳してネタにする）
    "https://news.google.com/rss/search?q=OpenAI+Claude+Gemini+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+agent+automation+enterprise&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスでの研究経験・国連会議参加など国際的視野
- 課題解決志向、データと洞察を組み合わせたスタイル
- ターゲット読者：経営者・医療従事者・テックに関心のあるビジネスパーソン
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（必ずいずれかを採用すること）

### P1: 数字リストフック
「〇〇を△日使って気づいた□つのこと↓」から始まるリスト。
例: 「Claude Codeを30日使い倒して気づいた5つのこと↓」

### P2: 衝撃データ開幕
具体的な数字・統計で一行目を掴む。
例: 「医師の診断精度をAIが15%改善した研究が出た。」

### P3: 逆張り・異論提示
通説に反する主張でスクロールを止める。
例: 「AIで仕事が奪われる、は半分嘘だと思う理由。」

### P4: 未来予測
近い将来の具体的変化を断言する。
例: 「2027年、日本の一般病院でもAI診断が標準になる。その根拠→」

### P5: 実体験・正直レビュー
「実際に使ってみた」系は信頼と共感を生む。
例: 「GPT-4oとClaudeを3週間並行使用した正直な比較。」

### P6: 問題提起 + 解答示唆
読者が「自分事」と感じる問いを立てる。
例: 「AIを使いこなせる人と使えない人、5年後の差は何か。」

### P7: スレッド導入（🧵）
「〇〇について整理する🧵」で続きを読ませる。
例: 「医療AIが本当に変えること、変えないこと。整理する🧵」

### P8: 比較・ランキング
選択や優劣の判断材料を提供する。
例: 「ビジネスでAIを使うなら Claude > GPT > Gemini な理由。」
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）
1. 最初の一文でスクロールを止める（強フック必須）
2. ビジネスパーソンが「職場で即使える」と思える視点
3. 医療・社会変革・未来への問いかけを絡める
4. 「続きが気になる」構造を意識する
5. ハッシュタグは #AI または #生成AI を1個のみ
6. 具体的な数字・事例・対比を必ず入れる
7. 感情を動かすキー：驚き・危機感・希望・知的好奇心
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_numbered_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_viral_thread(headlines: list[str]) -> dict:
    """バイラル可能性の高いスレッド形式投稿を生成"""
    headlines_text = "\n".join(f"- {h}" for h in headlines[:6])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるスレッド形式の投稿セットを作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

## 今日の最新AIニュース
{headlines_text}

## 出力形式（必ずこのJSON形式のみで返すこと）
{{
  "selected_topic": "選んだトピック（1行）",
  "hook": "スレッド1ツイート目。140文字以内。強烈なフック+🧵",
  "thread": [
    "2ツイート目（140文字以内）",
    "3ツイート目（140文字以内）",
    "4ツイート目（140文字以内）"
  ],
  "cta": "最後のCTA。フォローやRTを自然に促す。140文字以内。",
  "standalone": "スレッドなしで単体でも使える140文字以内の投稿案",
  "image_prompt": "投稿に合う画像のDALL-Eプロンプト（英語・50語以内）",
  "viral_reason": "この投稿がバズる理由（日本語・30文字以内）"
}}"""

    raw = _call_claude(prompt)
    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass
    return {}


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1個まで
- それぞれ異なるバズパターン（P1〜P8）を使うこと{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw)


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


def generate_posts_from_rss() -> tuple[list[str], dict]:
    """最新AIトレンドニュースから投稿案 + スレッドセットを生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        posts = _generate_original_ai_insight()
        return posts, {}

    thread = generate_viral_thread(headlines)

    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- それぞれ異なるバズパターン（P1〜P8）を使うこと
- ビジネス層が「いいね」したくなる切り口を意識する
- ハッシュタグは1個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_numbered_tweets(raw)
    return posts, thread


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
- それぞれ異なるバズパターン（P1〜P8）を使うこと
- Claude、医療AI、AIと社会変革などのテーマを優先
- ハッシュタグは1個まで
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw)
