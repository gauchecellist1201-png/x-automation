"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層（経営者・マネージャー・起業家）向けユーザー獲得
"""

import os
import re
import feedparser
import anthropic
from dataclasses import dataclass

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+DX+経営+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+企業導入+活用事例&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

# 日本語ツイートの文字数上限
# X の重み付き文字数: 日本語1文字=2、URL=23固定、上限280
# → 日本語のみ: 140文字、URL含む: 128文字（余裕を持たせて117）
MAX_TWEET_LENGTH = 140
MAX_TWEET_WITH_URL = 117
NUM_CANDIDATES = 3


@dataclass
class NewsItem:
    title: str
    url: str


@dataclass
class TweetCandidate:
    text: str
    url: str = ""

    @property
    def full_text(self) -> str:
        """URLを末尾に付けた投稿テキスト（Xのリンクカードが自動生成される）"""
        if self.url:
            return f"{self.text}\n{self.url}"
        return self.text


AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

TARGET_AUDIENCE = """
## ターゲット読者（ユーザー獲得対象: ビジネス層）
- 経営者・役員・マネージャー・部長クラス
- AIで業務改革・DXを検討している企業担当者
- テック系起業家・スタートアップ創業者
- 「AIに乗り遅れたくない」と感じているビジネスパーソン
→ 彼らが「いいね・RT・フォローしたくなる」コンテンツを作る
"""

VIRAL_PATTERNS = """
## バズるAIツイートのパターン分析（ビジネス層向け・実例付き）

【パターン1: 数字インパクト型】← 保存・RTされやすい
具体的な調査数値 + ビジネス洞察
例: 「McKinsey: AI活用企業の生産性は最大40%向上。ただし成功企業の共通点は"ツール導入"でなく"使い方の設計"だった。あなたの会社はどちら？ #AI #DX」

【パターン2: 衝撃事実→問いかけ型】← いいね・引用されやすい
最新AIの驚異的な性能 + ビジネスへの鋭い問い
例: 「GPT-4が司法試験で上位10%の成績。5年後、企業の法務コストはどう変わるか。今の法務部は何に価値を置くべきか？ #生成AI」

【パターン3: before/after対比型】← 共感・保存されやすい
旧来の方法 vs AI活用後の時間・コスト対比
例: 「3年前: 市場調査レポートに2週間 / 今: Claude+Perplexityで2時間。この差に気づいていない競合がいる間に動く。 #AI活用」

【パターン4: 逆張り・反論型】← 議論・拡散されやすい
「常識」を否定する鋭い洞察
例: 「「AIが仕事を奪う」より怖いのは「AIを使いこなせる人に仕事が集中する」現実。格差は知識より"習慣"で生まれる。 #AI」

【パターン5: 即効ノウハウ型】← フォロワーが増えやすい
今すぐビジネスで試せるAI活用の具体的コツ
例: 「提案書をChatGPTで作る前に「読者=CFO、目的=予算承認、懸念=ROI」を1行書くだけで質が段違いになる。文脈設定がすべて。 #生成AI活用」
"""

TWEET_STRATEGY = """
## 投稿戦略（ユーザー獲得を最大化）
1. 冒頭1文でスクロールを止めるフックを入れる
2. 経営者・マネージャーが「これは使える」と感じる具体性
3. 数字・固有名詞・時間軸を入れると信頼性が上がる
4. 結論より「問い」で終わるとRTされやすい
5. ハッシュタグは #AI #生成AI #DX #AI活用 のうち1〜2個まで
6. URLを含む場合は文末に付ける（本文は117文字以内）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_len: int) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数制限内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+", line.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_len]


def fetch_rss_items(max_items: int = 10) -> list[NewsItem]:
    """RSSフィードからニュースアイテム（タイトル+URL）を取得"""
    items: list[NewsItem] = []
    seen_titles: set[str] = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append(NewsItem(title=title, url=url))
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[TweetCandidate]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"
            )

    has_url = bool(note_url)
    char_rule = (
        f"- 文末にNoteリンクを付ける: {note_url}（本文は117文字以内）"
        if has_url
        else "- URLなし（140文字以内）"
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TARGET_AUDIENCE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- {char_rule}
- 番号付きリスト（1. 2. 3.）で本文のみ出力
- ハッシュタグは1〜2個まで
- 上記のバズるパターンを1案ずつ使い分ける
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    max_len = MAX_TWEET_WITH_URL if has_url else MAX_TWEET_LENGTH
    tweets = _extract_tweets(raw, max_len)
    return [TweetCandidate(text=t, url=note_url) for t in tweets]


def generate_posts_from_rss() -> list[TweetCandidate]:
    """最新AIニュースからビジネス層向けのバズりやすい投稿を生成"""
    items = fetch_rss_items()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item.title}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
ビジネス層向けにバズるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TARGET_AUDIENCE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は117文字以内（末尾にニュースURLを添付するため）
- 番号付きリスト（1. 2. 3.）で本文のみ出力
- 上記のバズるパターンを1案ずつ使い分ける
- ハッシュタグは1〜2個まで
- 最後の行に「SELECTED: 選んだニュースの見出しをそのままコピー」を出力

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw, MAX_TWEET_WITH_URL)

    # 使用されたニュースのURLを特定
    selected_url = _find_selected_url(raw, items)

    return [TweetCandidate(text=t, url=selected_url) for t in tweets]


def _find_selected_url(raw: str, items: list[NewsItem]) -> str:
    """Claude の出力から選択されたニュースのURLを特定する"""
    for line in raw.splitlines():
        if line.startswith("SELECTED:"):
            headline = line.replace("SELECTED:", "").strip()
            for item in items:
                if headline[:15] in item.title or item.title[:15] in headline:
                    return item.url
            break
    # 特定できない場合は最初のアイテムのURLを使用
    return items[0].url if items else ""


def _generate_original_ai_insight() -> list[TweetCandidate]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界の重要トピックについて、ビジネス層に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TARGET_AUDIENCE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で本文のみ出力
- 上記のバズるパターンを1案ずつ使い分ける
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    tweets = _extract_tweets(raw, MAX_TWEET_LENGTH)
    return [TweetCandidate(text=t) for t in tweets]
