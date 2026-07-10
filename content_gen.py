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
    "https://news.google.com/rss/search?q=生成AI+LLM+エージェント&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+規制+法律+倫理&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点（スイス研究経験、国連会議参加）
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- チェリスト。感性と論理の両立を体現
"""

VIRAL_TWEET_PATTERNS = """
## バズるツイートの型（必ずいずれかを使う）

【型1: 衝撃スタッツ型】
数字・事実から入り「なぜそうなのか」に問いで着地
例: 「医師の診断精度は平均78%。最新AIは94%。でも患者が求めているのは正確さだけではない。」

【型2: 逆張り洞察型】
「みんなが思っている常識」を静かに否定する
例: 「AIに仕事を奪われると言われるが、最初に奪われるのは『考えなくていい仕事』だ。逆に言えば、考える人間の価値は上がる。」

【型3: 問いかけ型】
答えを持たない問いで終わる。読者が「考えたい」と思わせる
例: 「AIが医師より正確に診断できる時代、医師に残る価値とは何か。」

【型4: before/after ナラティブ型】
「昔はXだった。今はYになった。」で共感→変化→洞察
例: 「3年前、電子カルテは医師の負担だった。今、AIが自動で要約する。次に変わるのは何か。」

【型5: リスト／まとめ型】
「○つの理由」「知らないと損する○選」形式。保存されやすい
例: 「AIエージェント時代に医師が持つべき3つのスキル：①臨床推論 ②AIへの指示力 ③患者との信頼構築 これだけは機械に代替されない。」

【型6: 一次情報型】
自分だけが知っていることを共有する
例: 「今日の医学部の授業、AIが症例提示してた。5年前は想像もできなかった風景。」

【型7: 哲学/本質型】
深い問いに短い言葉で切り込む。RTされやすい
例: 「AIが『考える』ようになっても、『感じる』ことはできるのか。答えを持つ人はまだいない。」
"""

TWEET_STRATEGY = """
## 投稿戦略
1. 140文字をフルに使わない（90〜120文字がリズム良い）
2. 文末は「。」より余韻を残す方がRT率が高い
3. ハッシュタグは #AI #生成AI #医療AI から1〜2個
4. URLは文末に自然に配置（使う場合）
5. 改行は最大1回まで
6. 数字・固有名詞があると信憑性UP
7. ビジネス層に刺さる切り口: 生産性・コスト・競争優位・人材
"""

IMAGE_STRATEGY = """
## 画像提案ルール
- 投稿に最適な画像を1つ提案（実際の画像URLではなく、どんな画像が合うか説明）
- 「グラフ」「インフォグラフィック」「ニュース記事のスクリーンショット」「AI生成画像のプロンプト」など
- 画像があるとエンゲージメントが2〜3倍になる
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets_and_images(raw: str) -> tuple[list[str], list[str]]:
    """番号付きリストから投稿文と画像提案を抽出する"""
    tweets = []
    images = []

    tweet_section = True
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 「画像提案」セクションの検出
        if any(kw in line for kw in ["画像提案", "画像案", "【画像", "画像："]):
            tweet_section = False
            continue
        if re.match(r"^\d+[\.\)]\s*", line):
            content = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if tweet_section:
                if 0 < len(content) <= MAX_TWEET_LENGTH:
                    tweets.append(content)
            else:
                images.append(content)

    return tweets[:NUM_CANDIDATES], images[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> tuple[list[str], list[str]]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            ln for ln in feedback_text.splitlines() if ln.strip() and not ln.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 異なるバズる型を使い、バリエーションをつける{link_instruction}
{few_shot_section}

その後、各投稿案に合う画像提案を番号付きで出力してください（「## 画像提案」という見出しの後）。

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets_and_images(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    headlines.append(f"{title} ({link})" if link else title)
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> tuple[list[str], list[str]]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1〜2つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 異なるバズる型を使い、バリエーションをつける
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- ビジネス層・医療従事者が「保存したい」「RTしたい」内容

その後、各投稿案に合う画像提案を番号付きで出力してください（「## 画像提案」という見出しの後）。

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets_and_images(raw)


def _generate_original_ai_insight() -> tuple[list[str], list[str]]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 異なるバズる型を使う（衝撃スタッツ、逆張り、問いかけ等）
- Claude 5・GPT-5・AIエージェント・医療AI・AIと雇用などのテーマを優先
- ビジネス層・医療従事者に刺さる切り口

その後、各投稿案に合う画像提案を番号付きで出力してください（「## 画像提案」という見出しの後）。
"""
    raw = _call_claude(prompt)
    return _extract_tweets_and_images(raw)
