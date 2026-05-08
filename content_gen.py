"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層への毎日のAI情報発信・ユーザー獲得
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 - AI×ビジネス活用
    "https://news.google.com/rss/search?q=AI+企業活用+ChatGPT+業務効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス+DX+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Claude+Google+AI発表&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+スタートアップ&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 - グローバルAIトレンド
    "https://news.google.com/rss/search?q=AI+business+enterprise+productivity+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

SYSTEM_PROMPT = """あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。

## 著者プロフィール
- 医学生 × AI/ブロックチェーン起業家（2026年現在）
- 医療×テクノロジーの融合が最大のテーマ
- スイス大学研究経験・国連会議参加のグローバル視点
- Claude Codeなど最先端AIツールの実践的ユーザー・開発者
- ターゲット読者：経営者・マネージャー・ビジネスパーソン・起業家

## 高エンゲージメント投稿パターン（実績ベース）
以下のいずれかのパターンを使うこと：

【数字インパクト型】"ChatGPTで会議録作成が90%削減→でも本当の変化は別にあった"
　→ 数字と具体性で信頼構築、「続きが気になる」終わり方

【逆説・反直感型】"AIが進化するほど、〇〇の価値が上がる理由"
　→ 一般論を覆す視点でRTされやすい

【リスト予告型】"経営者が今すぐ知るべきAI活用法3選（スレッド↓）"
　→ スレッドへの誘導でインプレッション最大化

【問いかけ型】"あなたの会社で今週AIが節約した時間は何時間でしたか？"
　→ リプライが集まりアルゴリズムに乗りやすい

【最新ニュース+洞察型】"[事実]。重要なのは技術より、ビジネスモデルへの影響"
　→ 情報提供者としての権威性を構築

【Before/After型】"半年前：コード書けない→今：Claude Codeで医療アプリを1日で試作"
　→ 変化の物語は共感とシェアを呼ぶ

【警告型】"まだAIを使っていない会社は、来年何かが起こります"
　→ FOMO（取り残される恐怖）が行動を促す

## 投稿戦略（ビジネス層ユーザー獲得）
- 文頭3秒で「読む価値がある」と感じさせる
- ビジネスインパクトを数字・具体例で示す
- 医療×AI・社会変革・未来への洞察で差別化
- ハッシュタグは #AI または #生成AI のうち1個のみ
- 「フォローしたら毎日価値ある情報が来る」と思わせる品質を目指す"""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _call_claude(user_prompt: str) -> str:
    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きブロックから投稿文を抽出（複数行対応）"""
    # **1.** / 1. / 1) などのパターンで分割
    parts = re.split(r'(?:^|\n)\s*\**\d+[\.\)]\**\s+', raw)
    tweets = []
    for part in parts:
        if not part.strip():
            continue
        # 空行の前まで（1ブロック分）を取得し、改行を空白に
        first_block = re.split(r'\n\s*\n', part.strip())[0]
        tweet = ' '.join(first_block.splitlines()).strip()
        # マークダウン装飾・余分な空白を除去
        tweet = re.sub(r'\*\*?|__?', '', tweet).strip()
        if 10 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)
    return tweets[:NUM_CANDIDATES]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note記事 + 過去実績から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_note = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""以下のNote記事を読み、ビジネス経営者・マネージャーに刺さるX投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力（各投稿を1行に収める）
- ハッシュタグは1個のみ{link_note}
- 高エンゲージメントパターンのいずれかを必ず使うこと
{few_shot}
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
    """最新AIトレンドニュースを元に、ビジネス層向け投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス経営者・マネージャーに刺さる洞察投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（各投稿を1行に収める）
- 医療×AI・社会変革・未来への問いを絡めると尚良い
- ハッシュタグは1個のみ
- 高エンゲージメントパターンのいずれかを必ず使うこと

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""2026年のAI業界で最も重要なトピックについて、
ビジネス経営者・マネージャー層に刺さる深い洞察投稿を{NUM_CANDIDATES}案作成してください。

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（各投稿を1行に収める）
- Claude・ChatGPT・医療AI・ビジネスDXなどのテーマを優先
- ハッシュタグは1個のみ
- 高エンゲージメントパターンのいずれかを必ず使うこと
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_image_suggestion(tweet: str) -> str:
    """投稿に合わせた画像提案を1行で生成"""
    prompt = f"""以下のX投稿に最も適した画像を提案してください。

投稿：{tweet}

必ずこの形式で2行のみ出力してください（余計な説明不要）：
検索KW: [Unsplash/Pixabay用の英語キーワード3語以内]
画像: [理想の画像説明を30文字以内]"""
    return _call_claude(prompt).strip()


def generate_thread_posts(topic: str, note_url: str = "") -> list[str]:
    """ビジネス層向け5ツイートスレッドを生成"""
    link_note = f"\n- 最後のツイートにNote URL: {note_url}" if note_url else ""

    prompt = f"""以下のトピックで、ビジネス経営者・マネージャーに刺さる5ツイートのスレッドを作成してください。

トピック：{topic}

スレッド構成（必ず守ること）：
1. フック（問いかけか驚きの事実で読者を引き込む）
2. 背景・問題提起（なぜ今重要か）
3. ビジネスへの具体的インパクト
4. 医療×AIの視点か将来予測
5. まとめ＋フォロー・コメント誘導{link_note}

ルール：
- 各ツイートは140文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力（各ツイートを1行に収める）
- ハッシュタグは1番と5番のみ1個ずつ
"""
    raw = _call_claude(prompt)

    parts = re.split(r'(?:^|\n)\s*\**\d+[\.\)]\**\s+', raw)
    thread = []
    for part in parts:
        if not part.strip():
            continue
        first_block = re.split(r'\n\s*\n', part.strip())[0]
        tweet = ' '.join(first_block.splitlines()).strip()
        tweet = re.sub(r'\*\*?|__?', '', tweet).strip()
        if 5 < len(tweet) <= MAX_TWEET_LENGTH:
            thread.append(tweet)
    return thread[:5]
