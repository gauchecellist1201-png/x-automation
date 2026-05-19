"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層・経営者・スタートアップ・AI活用に関心のある層
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AIニュース
    "https://news.google.com/rss/search?q=AI+ChatGPT+Claude+OpenAI+生成AI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+Copilot+Gemini+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語 AIニュース（最速情報源）
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://www.technologyreview.com/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家（2026年現在）
- 医療×テクノロジーの融合を追求。PHR/EHRへのブロックチェーン活用を研究・実装中
- スイス大学研究経験・国連会議参加。グローバルな視点と現場感を持つ
- Claude Codeなど最新AIツールを毎日実務で使う実践者
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- 「AIが民主化した今、誰でも医療プロダクトを作れる時代が来た」
"""

TWEET_STRATEGY = """
## バズる投稿の戦略（ビジネス層向け）

### 狙うエンゲージメント層
- 経営者・起業家・スタートアップ創業者
- AIに興味があるが使いこなせていない中間管理職
- テック系・コンサル・金融のビジネスパーソン
- AIを自分のビジネスに活かしたい全ての人

### バズる投稿の共通点
1. 【数字インパクト】具体的な数字・割合・時間で現実を突きつける
2. 【意外性・逆説】「えっそうなの？」と思わせる切り口
3. 【FOMO・緊迫感】「乗り遅れると損」という感覚を自然に演出
4. 【即実践可能】読んだ瞬間に「やってみよう」と思える内容
5. 【問いで終わる】答えを与えず、読者に考えさせるとRTが増える
6. 【スレッド予告】「1/7」「続きは→」でクリック率UP
7. 【ニュース反応】速報に誰よりも鋭いコメント
8. 【感情を動かす】怒り・驚き・共感・希望のどれかを刺激する

### 文体ルール
- 書き出しに強い「フック」（1行目で止める）
- 難解な専門用語は使わない、でも表面的にもならない
- ハッシュタグは #AI #生成AI #AIビジネス のうち最大2個
- 体験談・実例があると一気に信頼度UP
"""

VIRAL_PATTERNS = """
## バズりやすい投稿パターン（使い分ける）

【パターンA: 数字インパクト型】
「○○の作業、AIに任せたら3時間→8分になった。
同じ業務コストを払い続ける理由、もうなくない？ #AI」

【パターンB: 逆説・意外性型】
「AIが進化するほど、人間に求められるのは『○○』だと実感してる。
逆説的だけど、これが2026年の現実。」

【パターンC: FOMO・警告型】
「2026年末、AI活用してる会社とそうでない会社の生産性差は
もう埋められないレベルになってると思う。
今が最後のボーダーライン。」

【パターンD: リスト・スレッド予告型】
「経営者が知るべきAI活用法5選（1/5）
↓ 続きはスレッドで #AIビジネス」

【パターンE: 問い・思考実験型】
「明日から社員全員にClaude使い放題を与えたら、
あなたの会社の何が変わる？何が変わらない？
答えが出た人は、もう半歩先にいる。 #生成AI」

【パターンF: ニュース反応＋洞察型】
「[ニュース内容]が意味することの本質は、○○じゃなく○○。
この違いに気づいた企業が次の10年を獲る。」

【パターンG: Before/After対比型】
「AI導入前：企画書作成に2日
AI導入後：叩き台まで40分、本番まで3時間
差は「ツール」じゃなく「使う覚悟」にある。」

【パターンH: 実体験・発見型】
「最近○○をAIでやってみたら、想定外の発見があった。
むしろAIのほうが○○だった。→（続き）」
"""


def _call_claude(prompt: str, system: str = "") -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": "claude-opus-4-7",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    message = client.messages.create(**kwargs)
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きブロックから投稿文を抽出する（複数行対応）"""
    tweets: list[str] = []

    # 「1.」「2.」「3.」などで始まるブロックに分割
    blocks = re.split(r"\n(?=\d+[\.\)])", raw.strip())
    for block in blocks:
        # 先頭の番号を除去
        text = re.sub(r"^\d+[\.\)]\s*", "", block.strip())
        # 引用符・コードブロックで囲まれた場合は除去
        text = re.sub(r"^[「『\"]|[」』\"]$", "", text.strip())
        # 空行で区切られた場合は最初のまとまりだけ使う
        text = text.split("\n\n")[0].strip()
        # 改行を自然な形に
        text = re.sub(r"\n{2,}", "\n", text)
        if text and 10 < len(text) <= 280:
            tweets.append(text)

    # フォールバック: 番号なしで行が長い場合
    if not tweets:
        for line in raw.splitlines():
            line = line.strip()
            if 10 < len(line) <= 280 and not line.startswith("#"):
                tweets.append(line)

    return tweets[:NUM_CANDIDATES]


def _select_best_headline(headlines: list[str]) -> str:
    """ヘッドラインからバズりやすいものを1つ選ぶ"""
    if not headlines:
        return ""
    if len(headlines) == 1:
        return headlines[0]

    headlines_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:10]))
    prompt = f"""以下のAIニュースヘッドラインから、Xでバズりやすい（ビジネス層が反応しやすい）ものを1つ選び、その番号と理由を20文字以内で答えてください。

形式: 「番号: 理由」（例: 「3: 数字インパクトが強い」）

{headlines_text}"""
    try:
        result = _call_claude(prompt)
        match = re.search(r"^(\d+)", result.strip())
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(headlines):
                return headlines[idx]
    except Exception:
        pass
    return headlines[0]


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Google Newsの「- メディア名」を除去
                title = re.sub(r"\s+-\s+\S+$", "", title).strip()
                if title and len(title) > 15:
                    headlines.append(title)
        except Exception:
            continue
    # 重複除去
    seen: set[str] = set()
    unique: list[str] = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    return unique[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事をもとに、ビジネス層にバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は全角140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。各案の間は空行で区切る
- 8つのバズパターンから最適なものを選んで使う
- 1案目は「数字インパクト型」か「FOMO型」、2案目は「問い型」か「逆説型」、3案目は自由
- ハッシュタグは最大2個{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss() -> list[str]:
    """最新AIニュースをもとにバズる投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return generate_original_ai_insight()

    best = _select_best_headline(headlines)
    headlines_text = "\n".join(f"- {h}" for h in headlines[:8])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最もバズりやすいトピックを選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は全角140文字以内
- 番号付きリスト（1. 2. 3.）で出力。各案の間は空行で区切る
- 最も注目度が高いと判断したトピック: 「{best}」を軸に、独自の視点・洞察を加える
- ニュースをそのまままとめるのはNG。「なぜ重要か」「ビジネスへの影響」を語る
- 8つのバズパターンから最適なものを選んで使う
- ハッシュタグは最大2個

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_post() -> list[str]:
    """エンゲージメントを最大化するスレッド投稿（1ツイート目 + 続き）を生成"""
    headlines = fetch_rss_headlines(max_items=5)
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else "最新AIトレンド全般"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のAIニュース・トレンドをもとに、スレッド形式のX投稿を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッド構成（各ツイートを番号で区切る）:
1. 【フック】「〇〇について知っておくべき5つのこと🧵（1/5）」のような強い書き出し（140文字以内）
2. 【本論1】具体的な事実・数字（140文字以内）
3. 【本論2】ビジネスへの影響・含意（140文字以内）
4. 【本論3】見落とされがちな視点（140文字以内）
5. 【まとめ】行動喚起 or 問い（140文字以内）

ルール:
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- 1ツイート目が最も重要。スクロールを止める強さが必要
- ハッシュタグは最後のツイートに1〜2個だけ

## 参考トレンド
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界の最重要トピックについて、
ビジネス層がRTしたくなるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_PATTERNS}

ルール:
- 各投稿は全角140文字以内
- 番号付きリスト（1. 2. 3.）で出力。各案の間は空行で区切る
- テーマ例: AIエージェント台頭・生産性革命・AI×医療・経営変革・人材市場の変化
- 抽象論より「具体的な場面・数字・問い」を優先
- ハッシュタグは最大2個
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
