"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語ビジネスAIニュース
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+DX+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+医療+ヘルスケア+病院&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    # 英語技術ニュース（グローバル視点）
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.technologyreview.com/feed/",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5  # 案の数を増やしてより多様なパターンを提供

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHRへのブロックチェーン活用、非中央集権的医療データ管理を研究・実装
- スイスでの研究経験・国連会議参加などグローバル視点
- Claude Codeなど最新AIツールを実務で活用中
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- 専門的知識を持ちながら、読者に考えさせる問いを投げかける
"""

BUSINESS_TARGETING = """
## ターゲット：ビジネス層（経営者・マネージャー・意思決定者）
- AI導入・DX推進を検討しているリーダー層
- 医療・ヘルスケア業界の変革に関心がある人
- テクノロジーで競合優位を築きたい経営者
- 「何をすべきか」より「なぜ今か」を知りたい人
"""

VIRAL_TWEET_PATTERNS = """
## バズる投稿パターン（以下から最も効果的なものを選んで使う）

### 🔥 パターン1: 数字・データフック（最高エンゲージメント）
「GPT-4で医療診断、人間医師と一致率86%の研究が出た。残り14%こそが医師の価値」
「AIを導入した企業の73%が1年以内に用途を変更している。最初の想定が甘すぎた」

### ⚡ パターン2: 逆張り・反直感（RT率が高い）
「AIは仕事を奪わない。"判断しない人間"を奪う」
「ChatGPTに全部聞けばいいという人ほど、問いを立てる能力が落ちていく」
「医療AIが進化するほど、医師に求められるのは"共感力"だと思う理由」

### 💡 パターン3: 問いで締める（会話・返信を促す）
「AIが書いた処方箋を患者が信頼する日は来るか」
「医療データが患者のものになったとき、医師と病院の関係はどう変わる？」

### 📊 パターン4: ビジネス意思決定層への問いかけ
「AI導入で後悔する会社に共通すること：ツールを選ぶ前に"何をやめるか"を決めていない」
「経営者が今すぐ答えるべき1問：3年後も人間にしかできない仕事を3つ挙げられるか」

### 🏥 パターン5: 医療×AI（差別化ポイント）
「医学部6年間で学んだことをAIは0.3秒で出力する。でも患者の前で必要なのは"0.3秒の答え"じゃない」
「AIが診断精度で医師を超える日より、患者がAI診断を望む日の方が先に来ると思う」

### 🌍 パターン6: 未来予測（保存率が高い）
「2030年、医療データはブロックチェーンで患者が所有する時代へ。病院のビジネスモデルが根底から変わる」

### 🧵 パターン7: スレッド冒頭（リーチ拡大）
「医療×AIで本当に変わること、誰も正直に語らないから言う🧵」
「AIで起業してわかった、誰も教えてくれなかった3つのこと↓」

### 😮 パターン8: 共感・実体験（親近感でフォロワー増）
「Claude使い始めて気づいたこと：人間の仕事で本当に残るのは"文脈理解"と"責任を取ること"だけだった」

## 高エンゲージメントのコツ
- 冒頭に「」「→」「▶」などを使うと目を引く
- 「〜だと思う」「〜かもしれない」は柔らかさと知性を両立
- 数字（%、万人、秒）があると具体性が増す
- 「でも——」「しかし——」の逆接は読み進めさせる
- 結論を言い切るより"余白"を残すとRTされやすい
"""

TWEET_STRATEGY = """
## 投稿戦略
1. 上記のバズるパターンから最適なものを選ぶ
2. ビジネス層が「保存したい」「RTしたい」と思う洞察を入れる
3. 医療・社会変革・テクノロジーの交差点を狙う
4. ハッシュタグは #AI #生成AI #医療DX #AIビジネス のうち0〜2個まで
5. URLは文末に自然に入れる（23文字換算）
6. 毎回異なるパターンで5案作る（単調にならないよう）
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る（改良版）"""
    tweets: list[str] = []

    # パターン1: "1. " "1) " などで始まる行
    numbered = re.findall(r'^\d+[\.\)]\s*(.+?)(?=\n\d+[\.\)]|\Z)', raw, re.MULTILINE | re.DOTALL)
    for t in numbered:
        cleaned = t.strip().replace('\n', ' ')
        # 140文字超えは切り捨て（URLありの場合は117+23=140換算）
        if 10 < len(cleaned) <= 200:
            tweets.append(cleaned[:140])

    if tweets:
        return tweets[:NUM_CANDIDATES]

    # パターン2: 「案X」「【案X】」で始まる行
    bracketed = re.findall(r'(?:案\d+[：:]?|【案\d+】)\s*\n?(.+?)(?=(?:案\d+|【案\d+】)|\Z)', raw, re.DOTALL)
    for t in bracketed:
        cleaned = t.strip().replace('\n', ' ')
        if 10 < len(cleaned) <= 200:
            tweets.append(cleaned[:140])

    return tweets[:NUM_CANDIDATES]


def _generate_image_prompt(topic: str, tweet: str) -> str:
    """投稿に合う画像生成プロンプトを提案"""
    prompt = f"""以下のX投稿に合う、エンゲージメントを高める画像を1つ提案してください。

投稿: {tweet}
トピック: {topic}

回答形式:
- 画像タイプ: [グラフ/インフォグラフィック/写真イメージ/引用カード/スクリーンショット]
- 内容説明: (日本語で20字以内)
- ポイント: (なぜこの画像が効果的か1行で)"""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> tuple[list[str], str]:
    """Note記事 + 過去実績から戦略的投稿案を生成。(tweets, image_suggestion) を返す"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 最後の1案にはNoteリンクを入れる: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGETING}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- 5案それぞれ異なるバズパターンを使う
- ハッシュタグは0〜2個{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)

    # 画像提案（最も良さそうな1案目に対して）
    image_suggestion = ""
    if tweets:
        try:
            image_suggestion = _generate_image_prompt("AI×医療×ビジネス", tweets[0])
        except Exception:
            pass

    return tweets, image_suggestion


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
                    items.append({"title": title, "url": link})
        except Exception:
            continue
    # 重複除去
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str, str]:
    """最新AIトレンドニュースを元に意見投稿を生成。(tweets, topic, image_suggestion) を返す"""
    items = fetch_rss_headlines()
    if not items:
        tweets = _generate_original_ai_insight()
        return tweets, "AI業界トレンド", ""

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さる洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGETING}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- 5案それぞれ異なるバズパターンを使う
- 医療×AI、社会変革、経営判断への問いを絡めると尚良い
- ハッシュタグは0〜2個

## 今日の最新AIニュース
{headlines_text}

まず選んだトピックを1行で述べてから、投稿案を出力してください。
"""
    raw = _call_claude(prompt)

    # トピック行を抽出
    topic = "AIニュース"
    for line in raw.splitlines():
        if line.strip() and not re.match(r'^\d+', line.strip()) and len(line.strip()) < 80:
            topic = line.strip().lstrip("選択トピック：「」#*-→▶").strip()
            break

    tweets = _extract_tweets(raw)

    # 画像提案
    image_suggestion = ""
    if tweets:
        try:
            image_suggestion = _generate_image_prompt(topic, tweets[0])
        except Exception:
            pass

    return tweets, topic, image_suggestion


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層の意思決定者に刺さる洞察をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGETING}
{VIRAL_TWEET_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 5案それぞれ異なるバズパターンを使う
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_thread_opener(topic: str) -> list[str]:
    """スレッド形式の冒頭ツイートを生成（リーチ拡大用）"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
「{topic}」について、Xのスレッド形式で発信するための冒頭ツイートを3案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGETING}

ルール:
- 140文字以内（🧵や↓などのスレッド記号を含む）
- 「続きを読みたい」と思わせる強いフック
- 番号付きリスト（1. 2. 3.）で出力
- ビジネス層が「これは読まないと」と思うテーマ設定
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
