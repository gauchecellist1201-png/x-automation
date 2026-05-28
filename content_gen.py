"""
Claude API を使った戦略的バズり投稿生成モジュール
ターゲット: ビジネス層向けAI情報発信
アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic
from pathlib import Path

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+経営+DX+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+最新&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_CHARS = 140
THREAD_SIZE = 4
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 発信者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学研究・国連会議参加のグローバル視点
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

BUSINESS_AUDIENCE = """
## ターゲット：ビジネス層
- 経営者・起業家・マネージャー・投資家
- AIを「競争優位に変えたい」と思っている人
- 「明日の経営判断に使える」「シェアしたい」と思わせることが最重要
- 難解な技術論より「ビジネスへの影響・実用的な使い方・未来予測」が刺さる
"""

VIRAL_PATTERNS = """
## バズる投稿パターン（6種 — 必ずいずれかを選んで使うこと）

【P1: 数字フック型】驚きの統計・データで始める
構造: [衝撃の数字] → [比較・文脈] → [洞察または問い]
強み: いいねを集めやすい。ビジネス層が数字に反応する
例: 「GPT-4は弁護士試験で上位10%を取った。医師国家試験は上位3%。AIが資格を超えた時代に、「専門性」の価値をどう再定義するか。 #AI」

【P2: Before/After型】変化の落差を見せる
構造: [〇年前の状態] → [現在] → [近未来への示唆]
強み: シェアされやすい。時代の変化を体感させる
例: 「2020年のAI：文章がぎこちない。2023年：プロライター超え。2026年：経営戦略を立案。あなたの会社のAI活用は今どこにある？ #生成AI」

【P3: 問いかけ型】最後を問いで締める（最もRT率が高い）
構造: [共通認識] → [逆説的視点] → [あなたはどうする？]
強み: リプライ・RTが増える。フォロワーとの対話が生まれる
例: 「「AIに仕事を奪われる」はよく聞く。でも実際は「AIを使いこなす人が使いこなせない人の仕事を奪う」。あなたはどちら側にいますか？ #AI」

【P4: リスト型】箇条書きで即使える情報提供
構造: [タイトル：〇〇の〇選] → [番号付きリスト] → [締め一言]
強み: 保存・ブックマーク率が高い。後でシェアされる
例: 「今すぐ使えるAIツール5選：①Claude→文章・分析②Perplexity→調査③Cursor→コード④Midjourney→デザイン⑤NotebookLM→資料整理。全部今日から使える。 #AI」

【P5: 逆説型】常識を否定する逆張り
構造: [一般的な認識] → [実は違う本質] → [本当の問い]
強み: 議論を呼ぶ。印象に残り、フォローされやすい
例: 「「AIが人間を超えた」と言われる。私の見方は逆だ。人間はAIを使って自分を超えることができる。これは人類史上初めての出来事だ。 #AI」

【P6: 速報解説型】ニュース＋独自洞察
構造: [速報・最新事実] → [一般人が気づかない本質] → [ビジネスへの示唆]
強み: タイムリーで拡散しやすい。専門家としての権威性が上がる
例: 「【注目】OpenAIが医療AI参入。表面上は「診断支援」だが本質は「医師5分の診断をAIが0.1秒で」する世界への移行。医療費の構造が変わる。 #AI #医療」
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _load_file_lines(path: str, skip_prefix: str = "#") -> str:
    p = Path(path)
    if not p.exists():
        return ""
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith(skip_prefix)]
    return "\n".join(lines)


def _parse_output(raw: str, source_url: str = "") -> dict:
    """Claude出力をタグで解析してdict形式で返す"""
    result: dict = {"pattern": "", "tweets": [], "thread": [], "image": ""}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if m := re.match(r"\[PATTERN\]:\s*(.+)", line):
            result["pattern"] = m.group(1).strip()
        elif m := re.match(r"\[TWEET\]:\s*(.+)", line):
            tweet = m.group(1).strip()
            if tweet and len(result["tweets"]) < NUM_CANDIDATES:
                result["tweets"].append(tweet)
        elif m := re.match(r"\[THREAD_\d\]:\s*(.+)", line):
            result["thread"].append(m.group(0).split("]: ", 1)[1].strip())
        elif m := re.match(r"\[IMAGE\]:\s*(.+)", line):
            result["image"] = m.group(1).strip()

    if source_url:
        result["tweets"] = [f"{t}\n{source_url}" for t in result["tweets"]]
        if result["thread"]:
            result["thread"][-1] = f"{result['thread'][-1]}\n{source_url}"

    return result


def _build_prompt(context: str, source_url: str = "") -> str:
    feedback = _load_file_lines("data/feedback.txt")
    viral_examples = _load_file_lines("data/viral_examples.txt")
    combined = "\n".join(filter(None, [feedback, viral_examples]))
    few_shot = f"\n## 参考: 過去に反応が良かった投稿（文体・構成を再現）\n{combined}\n" if combined else ""
    url_note = f"（URLは自動付与のため文字数不要: {source_url}）" if source_url else ""

    return f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の情報を元に、ビジネス層にバズるX投稿を作成してください。

{AUTHOR_PROFILE}
{BUSINESS_AUDIENCE}
{VIRAL_PATTERNS}
{few_shot}
## 今日の素材
{context}

## 出力フォーマット（必ずこのタグ形式で一行ずつ出力）
[PATTERN]: 使用パターン（P1〜P6）
[TWEET]: 1番目の投稿案（140文字以内・ハッシュタグ込み{url_note}）
[TWEET]: 2番目の投稿案（異なるパターンで）
[TWEET]: 3番目の投稿案（異なるパターンで）
[THREAD_1]: スレッド1/4（フック・100文字以内）
[THREAD_2]: スレッド2/4（根拠・詳細・120文字以内）
[THREAD_3]: スレッド3/4（ビジネスへの示唆・120文字以内）
[THREAD_4]: スレッド4/4（問いかけ・CTA・100文字以内）
[IMAGE]: 添付推奨画像の提案（30文字以内）

## ルール
- 1番目の[TWEET]にP1〜P3のどれかを使うと最も拡散しやすい
- 医療×AI・社会変革・未来の仕事など井出直毅らしい視点を必ず入れる
- ハッシュタグは各ツイートに1〜2個（#AI #生成AI #医療DX #医療 などから選ぶ）
- ビジネス層が「これは知らなかった」「明日使える」と感じる内容にする
- [TWEET]と[THREAD_x]は必ず一行で出力すること
"""


def fetch_rss_entries(max_items: int = 10) -> list[tuple[str, str, str]]:
    """(headline, url, summary) のリストを返す"""
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()[:200]
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    entries.append((title, link, summary))
        except Exception:
            continue
    return entries[:max_items]


def generate_from_rss() -> dict | None:
    """最新AIニュースからバズり投稿を生成"""
    entries = fetch_rss_entries()
    if not entries:
        return generate_original_insight()

    headlines_text = "\n".join(f"- {title}" for title, _, _ in entries[:8])
    primary_title, primary_url, primary_summary = entries[0]

    context = f"""最新AIニュース一覧（最も注目すべき1件を選んで投稿を作成）:
{headlines_text}

選択ニュースの詳細タイトル: {primary_title}
概要: {primary_summary}"""

    raw = _call_claude(_build_prompt(context, primary_url))
    return _parse_output(raw, primary_url)


def generate_from_notes(note_text: str, note_url: str = "") -> dict | None:
    """Note記事からバズり投稿を生成"""
    context = f"## Note記事\n{note_text[:4000]}"
    raw = _call_claude(_build_prompt(context, note_url))
    return _parse_output(raw, note_url)


def generate_original_insight() -> dict | None:
    """RSSが取得できない場合のオリジナル洞察投稿を生成"""
    context = (
        "2026年のAI業界トレンド: AIエージェントが業務を自律実行する時代。"
        "Claude、GPT-5、Gemini Ultra が競い合い、医療・法律・教育分野でのAI活用が加速。"
        "経営者がAIをどう組織に組み込むかが最大の経営課題になっている。"
    )
    raw = _call_claude(_build_prompt(context))
    return _parse_output(raw)
