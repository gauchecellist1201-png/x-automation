"""
Claude API を使った戦略的投稿文生成モジュール（バズ特化・ビジネス層向け）
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import requests
import feedparser
import anthropic

RSS_FEEDS = [
    # AI全般（日本語）
    "https://news.google.com/rss/search?q=AI+人工知能+OpenAI+Claude+Gemini&hl=ja&gl=JP&ceid=JP:ja",
    # 生成AI・LLM
    "https://news.google.com/rss/search?q=生成AI+LLM+ChatGPT&hl=ja&gl=JP&ceid=JP:ja",
    # ビジネス×AI
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+DX&hl=ja&gl=JP&ceid=JP:ja",
    # 医療AI
    "https://news.google.com/rss/search?q=医療AI+医療DX&hl=ja&gl=JP&ceid=JP:ja",
    # Ledge AI
    "https://feeds.feedburner.com/ledge-ai",
]

NUM_CANDIDATES = 3
X_CHAR_LIMIT = 140  # 日本語文字数上限（Twitter重みカウントでは×2=280）

AUTHOR_PROFILE = """
## 著者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合・PHR/EHRブロックチェーン活用
- スイス研究経験・国連参加、グローバル視点
- Claude Code等最新AIツールを医療現場で実務活用中
- スタイル：専門的だが読者に問いを投げかける、静かで鋭い洞察
"""

VIRAL_STRATEGY = """
## バズるビジネス層向けX投稿の鉄則

### ターゲット：経営者・ビジネスリーダー・意思決定者
彼らが反応するもの → 危機感 / 競合優位 / 具体的ROI / 先見性

### 必ず使うバズフォーマット（どれか1つ）

【逆説型】常識を覆す
例）「AIが変えるのは効率じゃない。変えるのは意思決定の主体だ。」

【数字衝撃型】驚きのデータで引き込む
例）「ChatGPT、1億ユーザー到達：2ヶ月。TikTok：9ヶ月。Google：60ヶ月。」

【リスト型】読みやすい箇条書き
例）「AI時代を生き残る経営者の3条件：\n1. …\n2. …\n3. …」

【Hot Take型】強い主張から入る
例）「正直に言う。AIを使わない選択は、もはや経営リスクだ。」

【予測型】未来を語る
例）「2027年、AIなしで戦える業界はほとんど残らない。今始めないと遅い。」

【問いかけ型】読者を当事者化する
例）「あなたの競合は、もうAIで〇〇してます。あなたは？」

### Hook（最初の1〜2行）が全て
- 数字・固有名詞・驚きの事実を最初に置く
- 改行を使ってリズムを作る
- 「続きが読みたい」と思わせる

### ルール
- 各投稿は日本語140文字以内（URLは23文字換算）
- ハッシュタグは #AI #生成AI #医療DX から1〜2個
- 「AIは便利です」系の薄い内容は絶対禁止
- 体言止め・行動喚起・問いかけで締める
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_candidates(raw: str) -> list[str]:
    """[TWEET_START_N] ... [TWEET_END_N] ブロックから投稿文を抽出（複数行対応）"""
    matches = re.findall(r'\[TWEET_START_\d+\](.*?)\[TWEET_END_\d+\]', raw, re.DOTALL)
    candidates = [m.strip() for m in matches if m.strip()]
    # フォールバック: マーカーがない場合は番号付きブロックを分割
    if not candidates:
        segments = re.split(r'\n(?=\d+[\.\)])', raw)
        for seg in segments:
            text = re.sub(r'^\d+[\.\)]\s*', '', seg).strip()
            if text:
                candidates.append(text)
    return [c for c in candidates if 10 < len(c) <= 280]


def select_best_tweet(candidates: list[str]) -> str:
    """Claude がビジネス訴求力・バズ度でベストツイートを選択"""
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]

    options = "\n\n".join(f"【{i + 1}】\n{t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿候補から、経営者・ビジネスリーダーに最も刺さり、最もバズりそうな1つを選んでください。

選定基準（重要順）：
1. 最初の1〜2行（Hook）の強さ
2. 危機感・競合優位・ROIへの訴求
3. シェア・RTしたくなる度合い
4. 具体性（数字・事例・固有名詞）

候補：
{options}

番号のみ回答（例：2）"""

    raw = _call_claude(prompt)
    match = re.search(r'\d+', raw)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]


def fetch_article_image(url: str) -> bytes | None:
    """記事URL から OGP 画像のバイトデータを取得"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; x-automation/1.0)"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return None
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        img_url = None
        for pat in patterns:
            m = re.search(pat, resp.text, re.IGNORECASE)
            if m:
                img_url = m.group(1)
                break
        if not img_url:
            return None
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        img_resp = requests.get(img_url, timeout=8, headers=headers)
        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
            return img_resp.content
    except Exception as e:
        print(f"[画像取得失敗] {e}")
    return None


def fetch_rss_articles(max_items: int = 10) -> list[dict]:
    """RSS から記事リスト（title + link）を取得"""
    articles: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if title and len(title) > 10:
                    articles.append({"title": title, "link": link})
        except Exception:
            continue
    seen: set[str] = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    return unique[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績（few-shot）から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_note = f"\n- 文末にリンクを自然に入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}
{few_shot}

追加ルール：
- 各案を [TWEET_START_1] ... [TWEET_END_1] のマーカーで囲む
- 改行を活用してリズムを出す
- 日本語140文字以内{link_note}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_candidates(raw)


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースをもとにバズ投稿候補を生成。(candidates, article_link) を返す"""
    articles = fetch_rss_articles()

    if not articles:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {a['title']}" for a in articles)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール：
- 各案を [TWEET_START_1] ... [TWEET_END_1] のマーカーで囲む
- 改行を活用してリズムを出す
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- 日本語140文字以内

最後に、選んだニュースのタイトルを「選択記事：〇〇」と1行で記載。

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    candidates = _extract_candidates(raw)

    # 選択記事のリンクを抽出
    article_link = ""
    m = re.search(r'選択記事[：:]\s*(.+)', raw)
    if m:
        selected_title = m.group(1).strip()
        for a in articles:
            if selected_title in a["title"] or a["title"] in selected_title:
                article_link = a["link"]
                break

    return candidates, article_link


def _generate_original_ai_insight() -> list[str]:
    """RSS 取得不可時のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス経営者層に刺さる深い洞察のX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール：
- 各案を [TWEET_START_1] ... [TWEET_END_1] のマーカーで囲む
- 改行を活用してリズムを出す
- Claude・GPT・医療AI・AIと社会変革などのテーマを優先
- 日本語140文字以内
"""
    raw = _call_claude(prompt)
    return _extract_candidates(raw)
