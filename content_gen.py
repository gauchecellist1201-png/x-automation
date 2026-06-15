"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
目的: ビジネス層向けユーザー獲得のためのバズ投稿
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス活用+企業+生産性&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 280
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求、スイス研究経験・国連会議参加のグローバル視点
- ターゲット読者: AIを仕事に活かしたいビジネスパーソン・経営者・起業家
- 目標: 「このアカウントをフォローするとAI最新情報が得られる」と思わせてフォロワーを増やす
- スタイル: 押しつけがましくなく、静かに鋭い洞察。専門知識を読者に刺さる言葉で届ける
"""

VIRAL_FORMATS = """
## バズるツイートフォーマット集（必ずいずれかを使うこと）

【数字インパクト型】
例: 「GPT-5でこの作業が3時間→5分になった話
具体的なツール名と数字で信頼性UP #生成AI」

【リスト型（改行必須）】
例: 「AI活用で差がつく人の習慣3つ↓

①毎朝ニュースをAIで要約
②会議前に議題をプロンプトで整理
③週次レポートを自動化

これだけで年間100時間以上の余裕が生まれる #AI」

【比較対比型】
例: 「AIを使う人vs使わない人

提案書作成: 30分 vs 3時間
情報収集: 10分 vs 2時間
アイデア出し: 5分 vs 詰まったまま

2026年、この差は取り返せない #生成AI」

【衝撃事実型】
例: 「実は多くの人が知らないが、Claude 3.5はPDFを読んで
医療論文を患者向けに翻訳できる。
医師の説明時間を80%削減できる可能性 #AI #医療」

【問いかけ型（RTされやすい）】
例: 「AIが医師の診断精度を超えた時、
あなたはAIとヒトのどちらを信じますか？

この問いに答えがない間にも、医療AIは進んでいる #AI」

【今すぐ使える型（保存されやすい）】
例: 「知らないと損するClaude活用術↓

・「〇〇を専門家の視点で分析して」→コンサル品質の分析
・「反論を3つ挙げて」→思考の死角を埋める
・「5歳児に説明して」→理解度チェック

全部無料でできる #生成AI」

【ストーリー型】
例: 「医学生がAIを使って論文1本を2週間→3日で書いた。
ポイントは「AIに考えさせること」ではなく
「自分の思考をAIで加速すること」だった #AI」
"""

TWEET_STRATEGY = """
## 投稿戦略（ビジネス層向けユーザー獲得）

1. 【フック】最初の1〜2行でスクロールを止める
   - 数字・驚き・「知らないと損」感を入れる
   - 「えっ本当?」「これは保存しておきたい」と思わせる

2. 【価値提供】ビジネスパーソンが明日使える情報
   - 具体的なツール名・手順・数字を入れる
   - 「時間短縮」「コスト削減」「競争優位」の視点

3. 【拡散設計】RTと引用RTを狙う
   - 「これシェアしたい」「部下に送りたい」と思わせる
   - 意見が分かれる問いかけでリプライを誘発

4. 【改行活用】視覚的読みやすさが命
   - 重要情報の前で改行
   - リスト形式で情報を整理（①②③ or ・）
   - 空白行でリズムを作る

5. 【ハッシュタグ】#AI #生成AI #ChatGPT から1〜2個（文末に）

6. 【最適文字数】100〜200文字+改行が最も拡散される
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
    """=== 案N === セパレータでブロックを分割して投稿文を抽出"""
    sections = re.split(r'===\s*案\d+\s*===', raw)
    tweets = []
    for section in sections[1:]:  # 最初のセクション（ヘッダー前）をスキップ
        tweet = section.strip()
        if not tweet:
            continue
        # 連続する空行を最大1行に圧縮
        tweet = re.sub(r'\n{3,}', '\n\n', tweet)
        # Claudeが追加する説明文（「理由:」「ポイント:」「解説:」以降）を除去
        tweet = re.sub(r'\n+(?:理由|ポイント|解説|補足|注)[：:].+$', '', tweet, flags=re.DOTALL).strip()
        if 5 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)
    return tweets[:NUM_CANDIDATES]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績（few-shot）から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層のフォロワー獲得を目的とした
バズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_STRATEGY}

出力形式:
- 必ず「=== 案1 ===」「=== 案2 ===」「=== 案3 ===」で区切る
- 各案はツイート本文のみ（説明不要）
- 改行を積極的に使う（リスト形式・空行でリズム）
- 各案は異なるフォーマットを使う（数字型・リスト型・問いかけ型など）
- ハッシュタグは1〜2個まで
- 各投稿は280文字以内（URLは23文字換算）{link_instruction}

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
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    headlines.append(f"{title}" + (f" ({link})" if link else ""))
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIニュースをビジネス視点でバズる投稿に変換"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目・拡散されやすいトピックを選び、
ビジネス層のフォロワーが増えるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_STRATEGY}

出力形式:
- 必ず「=== 案1 ===」「=== 案2 ===」「=== 案3 ===」で区切る
- 各案はツイート本文のみ（説明不要）
- 改行を積極的に使う（リスト形式・空行でリズム）
- 各案は異なるフォーマットを使う（数字型・リスト型・比較型・問いかけ型など）
- ハッシュタグは1〜2個まで
- 各投稿は280文字以内
- 医療×AI・社会変革・ビジネス活用の視点を優先

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最重要のトピックについて、
ビジネス層のフォロワーが増えるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_STRATEGY}

出力形式:
- 必ず「=== 案1 ===」「=== 案2 ===」「=== 案3 ===」で区切る
- 各案はツイート本文のみ（説明不要）
- 改行を積極的に使う
- 各案は異なるフォーマットを使う
- ハッシュタグは1〜2個まで
- 各投稿は280文字以内
- Claude、GPT、医療AI、ビジネスAI活用、AI×社会変革などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
