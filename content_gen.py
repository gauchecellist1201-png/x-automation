"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
戦略: ビジネス層向けAIニュースでユーザー獲得を最大化
"""

import os
import re
import feedparser
import anthropic

# ビジネス層向けAI情報 RSS フィード
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+活用事例+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+ChatGPT+Claude+企業+導入+効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+革新+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+DeepMind+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+business+productivity+ROI&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_CHARS = 280  # X は日本語も含め 280 文字
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジー融合が最大テーマ
- PHR/EHRへのブロックチェーン活用・非中央集権的医療データ管理を研究中
- スイス留学・国連会議参加のグローバル視点
- Claude Codeなど最新AIツールを積極活用
- 「専門知識×鋭い問い」で読者に考えさせる静かで鋭いスタイル
"""

VIRAL_PATTERNS = """
## バズる AI 投稿パターン（ビジネス層向け）

以下のフォーマットから最も効果的なものを選んで使う:

1. 【衝撃の数字】「AIで〇〇時間→△分に短縮」「導入企業の85%がXXを達成」
   → 具体的ROIで経営者の興味を惹く

2. 【速報・業界激震】「[企業名]がXXXを発表した」「これは業界を変える」
   → 最新ニュースに乗って拡散を狙う

3. 【対比・格差】「AIを使う企業 vs 使わない企業、3年後の差」
   → 危機感・FOMO（取り残される恐怖）を植える

4. 【実用 Tips・保存推奨】「ChatGPTで提案書を10分で作る方法↓（保存推奨）」
   → ブックマーク狙い＆教育コンテンツとして拡散

5. 【逆張り・反直感】「AIに仕事を奪われる、は間違い。本当の脅威は…」
   → 「確かに…」という納得感で RT される

6. 【医師×AI の専門的洞察】医学生ならではの切り口
   → ニッチ専門性でフォロワー質を上げる

7. 【問いかけ】「あなたの会社、まだ〇〇を手作業でやってる？」
   → リプライ・エンゲージメントを促す
"""

TWEET_STRATEGY = """
## 投稿戦略
- ターゲット：経営者・マネージャー・スタートアップ創業者・意思決定者
- 感情トリガー：危機感・好奇心・納得感・驚き のどれか一つに絞る
- 冒頭1行で勝負：スクロール停止させる最初の一文が全て
- 数字・固有名詞・実例で信頼性を高める（「ある企業」より「トヨタ」）
- 改行・絵文字で視認性を高める（スマホでの読みやすさ重視）
- ハッシュタグ：#AI #生成AI #AIビジネス から 1〜2個のみ（多すぎると減点）
- URL は文末に自然に配置（X では 23 文字換算）
"""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _extract_tweets(raw: str) -> list[str]:
    """<tweet>タグから投稿文を抽出し文字数チェック"""
    tweets = re.findall(r"<tweet>(.*?)</tweet>", raw, re.DOTALL)
    result = []
    for t in tweets:
        t = t.strip()
        # URL は 23 文字換算で有効文字数を計算
        effective_len = len(re.sub(r"https?://\S+", "x" * 23, t))
        if 0 < effective_len <= MAX_TWEET_CHARS:
            result.append(t)
    return result


def select_best_tweet(candidates: list[str]) -> str:
    """複数候補からビジネス層への訴求力が最も高い投稿を 1 つ選ぶ"""
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n\n".join(f"[{i + 1}]\n{t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿候補から、ビジネス層（経営者・マネージャー・起業家）への
訴求力・エンゲージメント・拡散性が最も高いものを1つ選んでください。

選定基準：
- 冒頭1行の引きの強さ（スクロール停止力）
- 具体性・数字・固有名詞の有無
- RT・いいねを押したくなる感情トリガー（危機感/驚き/納得感/好奇心）
- @GAUCHE_cellist のブランド（医療×AI×洞察）との整合性

{numbered}

回答は番号のみ（例: 3）"""

    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    m = re.search(r"\d+", msg.content[0].text.strip())
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]


def fetch_rss_items(max_items: int = 12) -> list[dict]:
    """RSS から headline + URL を取得して重複排除"""
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


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note 記事 + 過去実績（few-shot）から戦略的投稿案を生成"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"

    url_rule = f"\n- Note リンクを文末に入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を元に、X投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は URL 込みで280文字以内（URL は23文字換算）
- 改行・絵文字を積極活用して視認性を高める
- 必ず <tweet>〜</tweet> タグで各案を囲む{url_rule}
{few_shot}
## Note 記事本文
{note_text[:4000]}
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_tweets(msg.content[0].text)


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新 AI ニュースからビジネス層に響く意見投稿を生成。(posts, top_article_url) を返す"""
    items = fetch_rss_items()

    if not items:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {item['title']}" for item in items)
    top_url = items[0]["url"] if items else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層（経営者・マネージャー・起業家）に強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は URL 込みで280文字以内（URL は23文字換算）
- 改行・絵文字を活用して視認性を高める
- 必ず <tweet>〜</tweet> タグで各案を囲む
- 関連記事 URL を文末に入れてもよい（より信頼性が増す）

## 今日の最新 AI ニュース
{headlines_text}
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    posts = _extract_tweets(msg.content[0].text)
    return posts, top_url


def _generate_original_ai_insight() -> list[str]:
    """RSS が取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層（経営者・マネージャー・起業家）に強く刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

ルール:
- 各投稿は280文字以内
- 改行・絵文字を活用して視認性を高める
- 必ず <tweet>〜</tweet> タグで各案を囲む
- テーマ例：Claude/GPT 最新動向、医療AI革命、AIエージェント自律化、AI×経営変革
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_tweets(msg.content[0].text)
