"""
Claude API を使ったバズり特化型投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層へのAI情報発信でユーザー獲得
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース (Google News)
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+ビジネス活用+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+デジタルヘルス+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=LLM+大規模言語モデル+企業&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AIニュース（グローバルトレンド速報）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+business+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI+announcement&hl=en&gl=US&ceid=US:en",
    # 専門メディア
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を最大のテーマとして活動
- スイスでの研究経験、国連会議参加などグローバル視点を持つ
- 2026年現在、Claude Codeなど最新AIツールを活用し医療×AI×ブロックチェーンで価値創出
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

VIRAL_PATTERNS = """
## バズる投稿の7パターン（必ず複数パターンを混ぜて案を作る）

1. **数字スタート型**（最も保存・RTされやすい）
   例：「ChatGPTユーザーが3億人突破。でも使いこなせている人は3%未満。」
   → 具体的数字で「知らなかった」「調べたい」を演出する

2. **逆説・反転型**（コメントを呼びやすい）
   例：「AIは仕事を奪わない。『考える必要のない仕事』を奪う。」
   → 常識を逆転させてRT・引用を誘発する

3. **ビジネス痛点型**（フォロー率が高い）
   例：「まだExcelで集計してる？競合は3倍速く動いてる。」
   → 経営者・管理職の焦りに直接訴える

4. **体験・実験型**（信頼度・フォロー率が高い）
   例：「AIに診断書を分析させたら見落としを3つ指摘された。これが医療の未来。」
   → 一人称の体験談は専門家としての信頼性を担保しつつ驚きを与える

5. **速報・独自情報型**（保存・引用が多い）
   例：「速報｜OpenAIがo3-miniを無料公開。個人がGPT-4レベルを0円で使える時代に。」
   → 情報の速さと希少性で保存・RTを誘発する

6. **リスト予告型**（フォロワー増加に直結）
   例：「2026年、今すぐ使うべきAIツール5選🧵」
   → スレッドへの導線でインプレッション最大化

7. **問題提起→答え保留型**（議論・コメントを呼ぶ）
   例：「医療AIが誤診したとき、責任は誰が取る？法律も医師も、まだ答えを持っていない。」
   → 答えのない問いはコメント・引用RTで拡散する
"""

BUSINESS_STRATEGY = """
## ビジネス層向けコンテンツ戦略

### ターゲット読者像
- 30〜50代のビジネスパーソン（経営者・管理職・士業・医療従事者）
- AI活用に興味があるが「何から始めるか」を探している層
- 情報感度は高く、実務に使えるネタを求めている

### エンゲージメント最大化ルール
1. 「知らないと損する」という危機感を自然に組み込む
2. 具体的数字・最新事実を1つ必ず含める
3. 医療×AI or ビジネス変革の切り口で差別化する
4. 140文字内で完結させつつ「続きが気になる」構成にする
5. ハッシュタグは #AI #生成AI #医療AI のうち1〜2個まで
6. ニュースリンクは文末に自然に入れる
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
    tweets = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 番号付きリストを除去: "1.", "1)", "【1】", "1 " 等
        cleaned = re.sub(r"^\d+[\.\)】]?\s*", "", line).strip()
        # 【案X】 形式も除去
        cleaned = re.sub(r"^【案\d+】\s*", "", cleaned).strip()
        if 15 < len(cleaned) <= MAX_TWEET_LENGTH:
            tweets.append(cleaned)
    # 重複除去しつつ順序を保持
    seen: set[str] = set()
    unique = []
    for t in tweets:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _viral_score(tweet: str) -> int:
    """バズりやすさを数値化するスコアリング"""
    score = 0
    # 具体的数字を含む（+3）
    if re.search(r'\d+', tweet):
        score += 3
    # 疑問符で終わる（問いかけ型）（+2）
    if tweet.endswith('？') or tweet.endswith('?'):
        score += 2
    # 逆説・反転ワード（+2）
    if any(k in tweet for k in ['ない。', 'ではない', 'でも', 'しかし', 'むしろ', '逆に']):
        score += 2
    # ビジネス痛点・危機感ワード（+3）
    if any(k in tweet for k in ['損', '差をつけ', '競合', '遅れ', '知らないと', 'まだ']):
        score += 3
    # 速報・独自情報ワード（+2）
    if any(k in tweet for k in ['速報', '発表', '公開', '解禁', '初めて', '世界初']):
        score += 2
    # 医療×AI文脈（差別化）（+2）
    if any(k in tweet for k in ['医療', '医師', '診断', '患者', '病院', '治療']):
        score += 2
    # ハッシュタグあり（+1）
    if '#' in tweet:
        score += 1
    # リンクあり（保存されやすい）（+1）
    if 'https://' in tweet or 'http://' in tweet:
        score += 1
    # 最適文字数（80〜128文字）（+2）
    if 80 <= len(tweet) <= 128:
        score += 2
    elif len(tweet) < 50:
        score -= 2
    return score


def rank_by_virality(tweets: list[str]) -> list[str]:
    return sorted(tweets, key=_viral_score, reverse=True)


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績からバズり投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを自然に入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるバズり投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. 4. 5.）で出力し、投稿文のみを書く（説明は不要）
- ハッシュタグは1〜2個まで
- 7つのバズりパターンのうち、異なるパターンを使って多様な案を出す{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)
    return rank_by_virality(tweets)[:NUM_CANDIDATES]


def fetch_rss_headlines(max_items: int = 12) -> list[dict]:
    """RSSから見出し・リンク・画像URLを取得"""
    items: list[dict] = []
    seen_titles: set[str] = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Googleニュースの「- ソース名」サフィックスを除去
                title = re.sub(r"\s*-\s*[^\-]+$", "", title).strip()
                if not title or len(title) < 10 or title in seen_titles:
                    continue
                seen_titles.add(title)

                # 画像URLを抽出（media > enclosure の順で試行）
                image_url = None
                if hasattr(entry, "media_content") and entry.media_content:
                    image_url = entry.media_content[0].get("url")
                elif hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image/"):
                            image_url = enc.get("href")
                            break

                items.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "image_url": image_url,
                })
        except Exception:
            continue
        if len(items) >= max_items:
            break

    return items[:max_items]


def generate_posts_from_rss() -> tuple[list[str], list[dict]]:
    """最新AIトレンドニュースからバズり投稿を生成、ニュースアイテムも返す"""
    news_items = fetch_rss_headlines()

    if not news_items:
        return _generate_original_ai_insight(), []

    headlines_text = "\n".join(
        f"- {item['title']}" + (f"  {item['link']}" if item["link"] else "")
        for item in news_items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層に刺さるバズり投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3. 4. 5.）で出力し、投稿文のみを書く（説明は不要）
- ハッシュタグは1〜2個まで
- 7つのバズりパターンを異なる組み合わせで使う
- ニュースのリンクを文末に入れてもよい

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)
    ranked = rank_by_virality(tweets)[:NUM_CANDIDATES]
    return ranked, news_items


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さるバズり投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3. 4. 5.）で出力し、投稿文のみを書く
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 7つのバズりパターンをそれぞれ使って多様な案を出す
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw)
    return rank_by_virality(tweets)[:NUM_CANDIDATES]
