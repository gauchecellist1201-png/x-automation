"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+企業+導入&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 AI ニュース（最新情報）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+business&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+OpenAI+Gemini+release&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議登壇などグローバル視点
- 課題解決志向、押しつけがましくなく鋭い洞察を届けるスタイル
- Claude Codeなど最前線AIツールを日常的に活用
"""

# バズりやすい投稿フォーマット定義
VIRAL_FORMATS = """
## バズるAI投稿フォーマット（必ずいずれか1つを採用）

### A. 統計ショック型
「○○%の企業がまだ〜していない」「○○円のコスト削減が可能」
→ 数字で驚かせ、現実との乖離を見せる

### B. 問いかけ型（最もRT・返信されやすい）
「〜、あなたの会社は対応できていますか？」
「〜を知らないまま2026年を生き残れると思いますか？」
→ 読者に自分事として考えさせる

### C. リスト型（保存率が高い）
「AIで業務効率化できる5つのこと：
①〜
②〜
③〜
④〜
⑤〜」
→ 保存・引用RTされやすい

### D. 逆張り型（論争を生む→拡散）
「みんながChatGPTを使っている中、本当に差がつくのは〜だ」
「AIに仕事を奪われる前に、AIを使いこなす側になれ」

### E. Before/After型（変化を可視化）
「AIなし：○時間かかる作業
AIあり：○分で完了
差：○○時間/月 = ○○円のコスト削減」

### F. 予言・未来型（知的権威を示す）
「3年後、〜ができない会社は淘汰されている」
「今のうちに〜をしておかないと後悔する理由」
"""

TWEET_RULES = """
## 投稿ルール
- 140文字以内（URLは23文字換算）でまとめる
  ただしリスト型・Before/After型はスレッド1通目として140文字 + 展開文を別途書く
- ハッシュタグは末尾に1〜2個（#AI #生成AI #ChatGPT #AIビジネス から選ぶ）
- 絵文字は1〜3個まで（多用するとスパム感が出る）
- 数字を必ず1つ以上入れる
- 「難しい言葉を易しく説明」より「知らなかった事実を鋭く提示」
- CTA（コールトゥアクション）：「RT・引用でご意見を」「フォローで続報を」等を自然に入れる
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts(raw: str) -> list[str]:
    """
    番号付きリスト（1. / 1) / 【案1】）から投稿文を抽出する。
    複数行にまたがる投稿（リスト型・Before/After型）も1エントリとして取得。
    """
    lines = raw.splitlines()
    posts: list[str] = []
    current: list[str] = []

    header_re = re.compile(r"^[【\[]?[案\d][】\]]?[\d\.\)：:\s]|^\d+[\.\)]\s")

    for line in lines:
        if header_re.match(line.strip()):
            if current:
                posts.append("\n".join(current).strip())
            # ヘッダー行自体は番号部分を除いて保持
            body = re.sub(r"^[【\[]?[案\d][】\]]?[\d\.\)：:\s]+", "", line.strip())
            current = [body] if body else []
        elif current:
            current.append(line)

    if current:
        posts.append("\n".join(current).strip())

    # 空エントリを除去
    return [p for p in posts if len(p) > 10]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_part = f"\n- 文末にNoteリンクを自然に入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_RULES}

- 各案は異なるフォーマット（A〜F）を使うこと{link_part}
{few_shot_section}
## Note記事本文
{note_text[:4000]}

## 出力形式
1. （投稿文）
2. （投稿文）
3. （投稿文）
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSS から title + link を取得"""
    items: list[dict] = []
    seen: set[str] = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue
        if len(items) >= max_items:
            break
    return items[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースから、ビジネス層に刺さるバズ投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}  {it['link']}" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最もバズりそうなトピックを1つ選び、
ビジネス層（経営者・マネージャー・起業家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_RULES}

- 各案は必ず異なるフォーマット（A〜F）を使うこと
- 選んだニュースのリンクが自然に投稿に組み込める場合は入れてもよい
- 医療×AI、社会変革、未来予測の角度を絡めると尚良い

## 今日の最新AIニュース（タイトル + URL）
{headlines_text}

## 出力形式
1. （投稿文）
2. （投稿文）
3. （投稿文）
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、ビジネス層に刺さるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_FORMATS}
{TWEET_RULES}

- 各案は必ず異なるフォーマット（A〜F）を使うこと
- Claude、GPT-5、Gemini、医療AI、AI×経営など最前線トピックを優先

## 出力形式
1. （投稿文）
2. （投稿文）
3. （投稿文）
"""
    raw = _call_claude(prompt)
    return _extract_posts(raw)
