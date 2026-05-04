"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズ分析・スレッド投稿・RSS URL対応版
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+自動化+医師&hl=ja&gl=JP&ceid=JP:ja",
    # English AI business news
    "https://news.google.com/rss/search?q=AI+agents+enterprise+2026&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大テーマに活動
- PHR/EHRへのブロックチェーン活用を研究・実装中
- スイスでの研究経験、国連会議参加などグローバルな視点を持つ
- Claude Codeなど最新AIツールを実際に使いこなしている当事者
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_TWEET_FORMATS = """
## バズるツイートの形式パターン（実績ベース分析）

【形式1: FOMO型】エンゲージメント・RT率が高い
「ほとんどの人が気づいていない〇〇が始まっている。」
→ 知識の非対称性を突く。「自分だけ知らないかも」という焦りで共有が生まれる

【形式2: 衝撃数字型】保存・引用数が高い
「AIが〇〇を△時間→□秒に短縮。これは〇〇業界への宣戦布告だ。」
→ 具体的数字で信頼性UP。変化の実感が拡散を促す

【形式3: 逆張り洞察型】引用数・議論誘発が高い
「みんなが〇〇を心配している。本当の問題は△△だ。」
→ 常識への反論が知的刺激になり、返信・引用を誘発

【形式4: 予言型】保存・長期拡散に強い
「3年後、〇〇業界で△△が起きる。今の医療現場にはその予兆がある。」
→ 未来への好奇心。「後で見返したい」で保存される

【形式5: 体験証言型】親近感・返信率が高い
「今日、AIに△△をさせてみた。〇〇という結果に言葉を失った。」
→ 個人の体験談が共感を呼び、「自分も試したい」を生む

【形式6: 問いかけ型】返信数・スレッド化に強い
「AIが〇〇を超えた今、医師に残された本当の価値は何か。」
→ 問いに答えたくなる心理。対話を生む

【形式7: Before/After型】ビジネス層への訴求が高い
「Before: 〇〇に3時間 → After AI: 3分。これが今の医療現場の現実。」
→ 変化を可視化。ビジネス層・経営者層が最も反応する

【形式8: リスト型】保存率最高・実用的
「AIで変わる医師の仕事3選：\n①〜 ②〜 ③〜\nあなたはいくつ経験した？」
→ 実用的な情報＋問いかけで保存と返信を両立
"""

TWEET_STRATEGY = """
## 投稿戦略（ビジネス層向けユーザー獲得）
1. 冒頭1行で「読み続けたい」と思わせるフック必須
2. 医療・社会変革・未来への問いかけを絡める
3. ビジネス層（経営者・専門職・スタートアップ）が「使える」「考えさせられる」内容
4. 結論より「問い」で終わると引用・返信を誘発しやすい
5. ハッシュタグは #AI #生成AI のうち1〜2個まで（多すぎると見苦しい）
6. URLは文末に自然な形で（23文字換算）
7. 改行・句読点で読みやすいリズムをつくる
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
    """番号付きリストから投稿文を抽出（複数行対応）"""
    tweets: list[str] = []
    current: list[str] = []
    in_tweet = False

    for line in raw.splitlines():
        if re.match(r"^\d+[\.\)]\s+\S", line):
            if in_tweet and current:
                tweet = "\n".join(current).strip()
                if 0 < len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            current = [re.sub(r"^\d+[\.\)]\s*", "", line).strip()]
            in_tweet = True
        elif in_tweet:
            stripped = line.strip()
            if stripped:
                current.append(stripped)
            else:
                # 空行はツイート内改行として保持
                current.append("")

    if in_tweet and current:
        tweet = "\n".join(current).strip()
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets[:NUM_CANDIDATES]


def _extract_thread_tweets(raw: str) -> list[str]:
    """「ツイートN:」形式のスレッドを抽出"""
    tweets: list[str] = []
    pattern = re.compile(r"ツイート\s*\d+[：:]\s*(.+?)(?=ツイート\s*\d+[：:]|\Z)", re.DOTALL)
    for m in pattern.finditer(raw):
        tweet = m.group(1).strip()
        if tweet and len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)
    return tweets[:3]


def _pick_best_headline(items: list[dict]) -> dict:
    """Claude にヘッドラインを評価させて最もバズりそうな1本を選ぶ"""
    headlines_text = "\n".join(f"{i+1}. {item['title']}" for i, item in enumerate(items))
    prompt = f"""以下のAIニュース見出しから、ビジネス層・医療関係者・AIに関心を持つユーザーに最も響きそうな1本を選んでください。

選定基準:
- 社会的インパクトが大きい
- 「知らなかった」「考えさせられる」と感じさせる
- 医療×AI、または企業×AIの変化を示す

見出し:
{headlines_text}

回答形式: 番号のみ（例: 3）"""
    raw = _call_claude(prompt).strip()
    m = re.search(r"\d+", raw)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(items):
            return items[idx]
    return items[0]


def _suggest_image(topic: str) -> str:
    """投稿に合う画像のヒントをClaudeに生成させる"""
    prompt = f"""以下のAI関連トピックに対して、Xに投稿する際に添付すると効果的な画像・スクリーンショットを1行で提案してください。
（実際のURLではなく「何の画像を用意すべきか」のヒントを日本語で）

トピック: {topic}

回答は1行のみ。"""
    return _call_claude(prompt).strip()[:100]


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
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- {NUM_CANDIDATES}案それぞれ異なるバズ形式（上記パターン）を使う
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


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

    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    return unique[:max_items]


def generate_posts_from_rss() -> dict:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成

    Returns: {posts, url, is_thread, image_hint}
    """
    items = fetch_rss_headlines()

    if not items:
        posts = _generate_original_ai_insight()
        return {"posts": posts, "url": "", "is_thread": False, "image_hint": ""}

    best = _pick_best_headline(items)
    topic = best["title"]
    news_url = best.get("url", "")

    # スレッド生成を試みる
    thread = _generate_thread(topic, news_url)
    if len(thread) >= 2:
        image_hint = _suggest_image(topic)
        return {"posts": thread, "url": news_url, "is_thread": True, "image_hint": image_hint}

    # 単発ツイート3案にフォールバック
    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- {NUM_CANDIDATES}案それぞれ異なるバズ形式を使う
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)
    image_hint = _suggest_image(topic) if posts else ""
    return {"posts": posts, "url": news_url, "is_thread": False, "image_hint": image_hint}


def _generate_thread(headline: str, article_url: str = "") -> list[str]:
    """ニュース1本から3ツイートのスレッドを生成"""
    link_part = f"\n- ツイート3の末尾にこのURLを含める: {article_url}" if article_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のニュースを元に、3ツイートのスレッドを作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッド構成:
- ツイート1: 強烈なフック（FOMO型 or 衝撃数字型）でスクロールを止める
- ツイート2: 医療×AI視点での深い洞察・解説
- ツイート3: ビジネス層へのインプリケーションまたは行動を促す問いかけ{link_part}

ルール:
- 各ツイートは140文字以内
- 以下の形式で出力（他の説明文は不要）:
ツイート1: [内容]
ツイート2: [内容]
ツイート3: [内容]

## ニュース
{headline}
"""
    raw = _call_claude(prompt)
    return _extract_thread_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_FORMATS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- {NUM_CANDIDATES}案それぞれ異なるバズ形式を使う
- Claude Agents、医療AI自動化、AIと社会変革などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
