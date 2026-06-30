"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層（経営者・マネージャー・意思決定者）
"""

import os
import re
import requests
import anthropic
from xml.etree import ElementTree as ET

# ビジネス層ターゲットのRSSフィード（AI×経営）
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ビジネス活用+企業+導入+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+Claude+業務効率&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+AI+新機能&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+DX+経営戦略+ROI+コスト削減&hl=ja&gl=JP&ceid=JP:ja",
]

MAX_TWEET_LENGTH = 140
URL_CHAR_COUNT = 23  # Xでは全URLを23文字換算
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- ビジネス経営者層への洞察を発信
- スイスの大学での研究経験、国連会議参加のグローバル視点
- 難しいことを平易に、でも鋭く語るスタイル
"""

BUSINESS_TARGET = """
## ターゲット読者
- 経営者・役員・部長クラス（AI投資を検討中）
- 中間管理職（AI導入の実務担当）
- 起業家・スタートアップ（競争優位を求めている）
- 共通キーワード：ROI・競合差別化・業務効率・リスク回避・未来予測
"""

VIRAL_PATTERNS = """
## 必ず以下のいずれかのフォーマットで書く（最重要）
A【数字インパクト】
  「〇〇をAIで自動化→週△時間削減。年換算□万円の効果が出ている」具体的な数字で驚かせる
B【反常識の発見】
  「AI導入に失敗する企業の共通点はAIではなく、〇〇だった」意外な視点
C【問いかけ】
  「あなたの会社、まだ〇〇を手作業でやってますか？競合はすでにAIに任せています」
D【速報+経営示唆】
  「〔注目〕〇〇がついに△△に。この変化で経営に必要な行動は…」ニュース解説
E【未来予測】
  「3年後、〇〇という仕事の△割はAIに。今からやっておくべき準備は?」
F【箇条書きリスト】
  「AI活用で変わる業務TOP3\n①〇〇 ②△△ ③□□\nあなたの業界では?」
G【体験・事例】
  「先週、〇〇をAIに任せたら△△の結果に。経営判断のスピードが変わった」
H【対比で見せる】
  「AI活用企業 vs 未活用企業の生産性、3年後は〇倍差になる予測が出た」
"""

TWEET_RULES = f"""
## 投稿ルール
- 最初の20字でスクロールが止まるようにする（数字・問い・反常識）
- 各投稿は{MAX_TWEET_LENGTH - URL_CHAR_COUNT - 1}文字以内（URLは別途添付）
- ハッシュタグは #AI #生成AI #DX のうち1個のみ文末に
- 難解な技術語より「ビジネスへの影響」で語る
- RTされやすい「問い」か「驚き」で終わる
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_numbered_tweets(raw: str, url: str = "") -> list[dict]:
    """番号付きリストから投稿文を抽出しdictリストを返す"""
    candidates = []
    # 番号区切りで分割（1. / 1) / 案1: 形式に対応）
    parts = re.split(r"\n(?:案?\d+[\.\):\s])\s*", "\n" + raw)
    for part in parts[1:]:
        line = part.strip().split("\n")[0].strip()
        line = line.strip("\"'「」")
        # URLが付く場合は文字数を調整済みで制限
        if 10 < len(line) <= MAX_TWEET_LENGTH:
            candidates.append({"text": line, "url": url})
    return candidates[:NUM_CANDIDATES]


def _parse_rss_xml(xml_text: str) -> list[dict]:
    """RSS XMLからタイトルとリンクを抽出"""
    articles = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        # RSS 2.0
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
                link = ""
                if link_el is not None and link_el.text:
                    link = link_el.text.strip()
                # Google NewsのURLは長いが有効
                if len(title) > 10:
                    articles.append({"title": title, "url": link})
    except ET.ParseError:
        pass
    return articles


def fetch_rss_with_urls(max_items: int = 10) -> list[dict]:
    """RSSからタイトルとURL付きで記事を取得"""
    all_articles: list[dict] = []
    seen_titles: set[str] = set()
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            for art in _parse_rss_xml(resp.text):
                if art["title"] not in seen_titles:
                    seen_titles.add(art["title"])
                    all_articles.append(art)
                    if len(all_articles) >= max_items:
                        return all_articles
        except Exception:
            continue
    return all_articles[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[dict]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    url_instruction = f"\n- URLとして文末に添付予定: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGET}
{VIRAL_PATTERNS}
{TWEET_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3.）で出力{url_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_numbered_tweets(raw, url=note_url)


def generate_posts_from_rss() -> list[dict]:
    """最新AIビジネスニュースを元に @GAUCHE_cellist らしい意見投稿を生成"""
    articles = fetch_rss_with_urls()
    if not articles:
        return _generate_original_ai_insight()

    articles_text = "\n".join(
        f"- 【{i+1}】{a['title']} | {a['url']}"
        for i, a in enumerate(articles[:8])
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIビジネスニュースから最も注目すべき記事を1つ選び、
ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGET}
{VIRAL_PATTERNS}
{TWEET_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3.）で出力
- 最後に1行で「選んだ記事のURL: <URL>」を出力すること（投稿文には含めない）
- 医療×AI、社会変革、経営への影響を絡めると尚良い

## 今日の最新AIビジネスニュース
{articles_text}
"""
    raw = _call_claude(prompt)

    # 選ばれた記事URLを抽出
    selected_url = ""
    url_match = re.search(r"選んだ記事のURL[：:]\s*(https?://\S+)", raw)
    if url_match:
        selected_url = url_match.group(1).strip()
    if not selected_url and articles:
        selected_url = articles[0]["url"]

    posts = _parse_numbered_tweets(raw, url=selected_url)
    return posts if posts else _generate_original_ai_insight()


def _generate_original_ai_insight() -> list[dict]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界でビジネス層が最も気にすべきトピックについて、
鋭い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{BUSINESS_TARGET}
{VIRAL_PATTERNS}
{TWEET_RULES}

追加ルール:
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIと経営戦略などのテーマを優先
"""
    raw = _call_claude(prompt)
    return _parse_numbered_tweets(raw)
