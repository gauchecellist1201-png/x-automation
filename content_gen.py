"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
2026年X バイラル戦略 v2対応
"""

import os
import re
import feedparser
import anthropic
from datetime import date

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+エージェント+自動化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+DX&hl=ja&gl=JP&ceid=JP:ja",
    # 英語ビジネス AI ニュース（翻訳して使用）
    "https://news.google.com/rss/search?q=Claude+Fable+GPT+Grok+enterprise+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大テーマ
- スイスでの研究経験・国連会議参加などグローバル視点
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- 読者に考えさせる「問い」を投げかけることを得意とする
- 専門用語を噛み砕き、ビジネス層と一般層の橋渡しをする
"""

TWEET_STRATEGY = """
## 2026年X(Twitter)バイラル戦略（最新アルゴリズム対応）

### アルゴリズムの仕組み（2026年最新）
- リプライはいいねの27倍重み付けされる → 議論・共感を呼ぶ投稿が最強
- 投稿後30分の初速エンゲージメントが拡散を左右する（スタートが全て）
- スレッド形式はエンゲージメントが連鎖的に伝播し最もバイラルしやすい
- Grok評価システムは「本物のエンゲージメント」を優遇する

### 強力なフック（最初の1行）の黄金パターン
1. 数字で驚かせる: 「AI導入企業の83%が1年以内に撤退する理由」
2. 逆説・意外性: 「GPTが普及したのに、なぜ現場は全く変わらないのか」
3. 専門家の暴露: 「医療AIが普及しない本当の理由を医学生の私が言う」
4. 問いで始める: 「AIに仕事を奪われる前に、あなたはAIに何を教えたか？」
5. 警告系: 「今AIエージェントを使っていないなら、2年後に後悔する」
6. 告白・本音: 「正直に言う。ChatGPTより○○の方がずっと良い」
7. 格差・二項対立: 「AIを使いこなす人と使われる人、差がつく一点」

### コンテンツ戦略（ビジネス層ユーザー獲得向け）
- 具体的な数字・ROI・生産性向上で語る（抽象論より数字が刺さる）
- 医療×AI の専門的視点を一般読者に翻訳する
- 「知らない人が損をしている」フレームを使う
- 「結論」より「問い」で終わるとRTが増える
- ハッシュタグは最大2個（多すぎるとリーチが下がる）
- URLリンクは文末に1個（23文字換算）

### 避けるべきパターン
- AIを礼賛するだけの投稿（独自視点なし）
- 曖昧な未来予測（「〜でしょう」など）
- 長い説明文（フックが弱い）
- ハッシュタグ3個以上
"""

TODAY_CONTEXT = f"""
## 今日の日付
{date.today().strftime('%Y年%m月%d日')}

## 2026年7月 最重要AIトピック（バズりやすい切り口付き）
- Claude Fable 5: 5000万行コード移行を「2ヶ月→1日」に圧縮（衝撃の実績）
- Claude Sonnet 5: エージェント型コーディングが日常業務に浸透（企業変革）
- NVIDIA Nemotron: 推論速度2.42倍・品質98.7%維持（コスパ革命）
- SAP が前払いAIスタートアップを1,180億円で買収（エンタープライズ戦争）
- OpenAI×Broadcom「Jalapeño」チップが9ヶ月で設計→量産（驚異の速度）
- AIエージェントが本番業務に本格投入開始（「実験」→「インフラ」へ転換）
- GPT-5.6 / Grok 4.5 / Claude Cowork モバイル版が相次いでリリース
- ソフトバンク×OpenAI: AIサイバーセキュリティサービス開始（日本市場）
- 若年層によるAIベースのサイバー攻撃が新リスクとして浮上
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+[\.\)]", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_image_prompt(topic: str) -> str:
    """投稿に合うSNS映えする画像のプロンプトを生成"""
    prompt = f"""以下のX投稿テーマに合う、SNS映えする画像を生成するためのプロンプトを英語で1つ作成してください。
スタイル: モダン・ミニマル・プロフェッショナル・日本のビジネス層に刺さるビジュアル
フォーマット: Midjourney/DALL-Eで使える英語プロンプト、1行で

テーマ: {topic}

プロンプトのみ出力してください。説明不要。"""
    return _call_claude(prompt).strip()


def generate_thread_hook(topic: str, news_context: str = "") -> str:
    """スレッドのフック投稿（1ツイート目）を生成"""
    context = news_context or TODAY_CONTEXT
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のテーマでスレッドを始めるフック投稿を1つ作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{context}

ルール:
- 140文字以内
- 最初の1行で「続きが読みたい」と思わせるフックを入れる
- 「🧵」または「（スレッド）」を末尾に付ける
- ハッシュタグ1〜2個まで

テーマ: {topic}

フック投稿のみ出力してください。番号・説明不要。"""
    result = _call_claude(prompt).strip()
    # 140文字を超える場合は通常の生成にフォールバック
    if len(result) <= MAX_TWEET_LENGTH:
        return result
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

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TODAY_CONTEXT}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 上記「フック」パターンを必ず1つ以上使うこと
- AIに関するプロレベルの洞察を、ビジネス層・一般読者にも刺さる言葉で{link_instruction}
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


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIトレンドニュースから @GAUCHE_cellist らしい意見投稿を生成
    Returns: (投稿案リスト, 画像プロンプト)
    """
    headlines = fetch_rss_headlines()
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else "（RSSフィード取得できず）"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TODAY_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 必ず「フック」パターンを使って最初の1行で心を掴む
- 医療×AI、社会変革、ビジネスへの影響を絡めると尚良い
- ハッシュタグは1〜2個まで
- リプライを誘発する問いかけ・議論の余地を残す

## 今週の最新AIニュース（RSSから）
{headlines_text}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)

    # 画像プロンプトを生成（投稿テーマに基づく）
    topic = headlines[0] if headlines else "AIエージェントとビジネス変革"
    image_prompt = generate_image_prompt(topic)

    return tweets, image_prompt


def _generate_original_ai_insight() -> tuple[list[str], str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{TODAY_CONTEXT}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 必ずフックパターンを使う
- Claude Fable 5、AIエージェント、医療AI、GPT-5.6 などのテーマを優先
- ビジネス層が「いいね」「RT」「返信」したくなる内容
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)
    image_prompt = generate_image_prompt("2026年AIエージェントビジネス変革")
    return tweets, image_prompt
