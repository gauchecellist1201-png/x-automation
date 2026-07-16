"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import random
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+AIエージェント&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+医療AI+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（最先端情報）
    "https://news.google.com/rss/search?q=AI+agents+LLM+OpenAI+Anthropic+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+healthcare+business+2026&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大テーマ
- PHR/EHRへのブロックチェーン活用、非中央集権的医療データ管理を研究
- スイスの大学での研究経験、国連会議参加などグローバル視点
- 課題解決志向、専門的知識を持ちながら読者に考えさせる問いを投げかける
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

TWEET_STRATEGY = """
## 2026年Xアルゴリズム対応：バズる投稿の黄金則
1. 【絶対ルール】URLリンクは本文に入れない（リーチが50%激減する）
2. 【数字の魔力】具体的な数字を入れる（「多くの」より「47%」→エンゲージメント3.4倍）
3. 【返信誘発】返信を誘う問いで終わる（返信はいいねより27倍アルゴリズムに評価される）
4. 【自信の一言】ヘッジせず断言する（「かもしれない」は禁止。「これが現実だ」）
5. 【独自視点】医師×AI×ブロックチェーンという希少な複合視点から語る
6. 【初速が命】投稿後30分の反応がバイラルを決める→議論を生む表現を選ぶ
7. 【ハッシュタグ】1〜2個まで（多すぎるとスパム判定）

## バズるフォーマット例（どれか一つ使う）
- 「誰も言わないけど、〇〇は△△だ」（逆張り＋断言）
- 「AIで医療が変わる5年後より、今年起きることの方が怖い」（近未来への警鐘）
- 「Anthropic年収47億ドル。これが意味することを医療業界はまだ理解していない」（数字＋業界批評）
- 「〇〇を知らずにAIを語る人が多すぎる」（優越感刺激→返信誘発）
- 「医師がコードを書かなくていい時代が来た。では医師は何をすべきか？」（問いかけ）
- 「AIエージェントが本番稼働した企業の共通点を調べたら、意外な結果が出た」（煽り＋好奇心）
"""

VIRAL_FORMATS = [
    "逆張り断言型：「誰も言わないけど〜」か「実は〜だ」という切り口で、通説に反する洞察を自信を持って断言する",
    "数字衝撃型：Anthropicが47億ドル・GPT-5.6など最新の具体的数字を使い、その意味をビジネス文脈で解説する",
    "問いかけ型：読み手が「自分にも関係ある」と思う問いで締め、返信・引用を促す",
    "警鐘型：AIが変える医療・社会の未来について「5年後ではなく今年」の視点で語る緊迫感のある表現",
    "医療×AI融合型：医学生・医師・患者という視点から、AIが医療現場に与える影響を具体的に描く",
    "エージェントAI時代型：AIエージェントが実務に入った今、ビジネスパーソンが知るべき変化を語る",
]


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
    results = []
    for line in raw.splitlines():
        stripped = line.strip()
        # 番号付き行を抽出
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", stripped)
        if cleaned and cleaned != stripped and 10 < len(cleaned) <= MAX_TWEET_LENGTH:
            results.append(cleaned)
    return results


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    viral_format = random.choice(VIRAL_FORMATS)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

今回使うバズフォーマット: {viral_format}

ルール:
- 各投稿は140文字以内（URLは絶対に本文に入れない）
- 番号付きリスト（1. 2. 3.）で出力（1行1案）
- ハッシュタグは#AI #生成AI #医療AIのうち1〜2個まで
- 具体的な数字・専門用語を適度に使う
- 断言する・ヘッジしない
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
                if title and len(title) > 15:
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
    viral_format = random.choice(VIRAL_FORMATS)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

今回使うバズフォーマット: {viral_format}

ルール:
- 各投稿は140文字以内（URLは絶対に本文に入れない）
- 番号付きリスト（1. 2. 3.）で出力（1行1案）
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 具体的な数字・企業名・モデル名を使って信頼性を高める
- 断言する・ヘッジしない

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    viral_format = random.choice(VIRAL_FORMATS)

    # 2026年7月時点の最新AIトピック（知識ベース）
    current_topics = """
- Anthropicの年換算収益が477億ドルに到達（2026年7月）
- GPT-5.6（Sol/Terra/Luna）が一般提供開始
- AIエージェントが医療・製造・金融の現場に本番導入
- EUのAIコンテンツ透明性規則が2026年8月施行予定
- Claude Codeがプロンプトを80%削減する機能を実装
- AIエージェント同士が協調する「マルチエージェント」が実用段階へ
"""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

今回使うバズフォーマット: {viral_format}

## 2026年7月の主要AIトピック（参考）
{current_topics}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（1行1案）
- URLリンクは絶対に含めない
- 具体的な数字を必ず1つ以上入れる
- 断言する・ヘッジしない
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
