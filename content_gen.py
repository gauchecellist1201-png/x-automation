"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
対象読者: ビジネス層（経営者・起業家・ビジネスリーダー）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+ビジネス+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+企業+DX+導入事例&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+OpenAI+経営&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+Agent+自動化+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス留学・国連会議参加などグローバル視点を持つ
- 専門的知識をビジネス文脈で分かりやすく発信するスタイル
- 「AIで世界を変える」という強い信念を持ち、読者に行動を促す
"""

TWEET_STRATEGY = """
## バズるAIビジネス投稿の戦略（ビジネス層向け）

### 対象読者
経営者・起業家・ビジネスリーダー・スタートアップ関係者

### 高バズフォーマット（どれか1つ選ぶ）
1. 【衝撃ファクト型】数字・事実から始め「知らなかった」を引き起こす
   例：「ChatGPTのユーザー4億人突破。日本のGDPに匹敵する経済価値がAIに移行中。」
2. 【逆張り洞察型】常識を覆す鋭い視点を一行で
   例：「AIが仕事を奪う、は半分間違い。正確には『AIを使う人間』が奪う。」
3. 【リスト+問い型】具体的Tips→最後に問いかけ
   例：「経営者がAI導入で失敗する理由①ツール導入が目的化②ROI未測定③社員教育後回し あなたの会社は？」
4. 【予測型】近未来への根拠ある予測で危機感と期待感
   例：「2027年、AI活用スキルがない人材は市場価値が半減すると予測する。今すぐ始めよ。」
5. 【ビフォーアフター型】具体的変化を数字で示す
   例：「3ヶ月前：資料作成3時間→今：20分。AIが変えたのは仕事量ではなく、思考の深さだった。」
6. 【医療×AI型】著者固有の専門性を活かした洞察
   例：「医師がAIで診断補助→手術ミス30%減という論文が出た。医療は変わる。問題はスピード感だ。」

### 共通ルール
- 最初の15文字でスクロールを止める
- 具体的な数字を必ず入れる（「多い」より「43%」）
- 「あなた」「経営者の多くは」など読者に語りかける一文を入れる
- 問いか「〜だ」という断言で締める（「〜だと思います」は弱い）
- ハッシュタグは #AI #生成AI #DX のうち最大2個
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """<tweet>タグまたは番号付きリストから投稿文を抽出し140文字以内に絞る"""
    # <tweet>タグ形式を優先
    tag_matches = re.findall(r"<tweet>(.*?)</tweet>", raw, re.DOTALL)
    if tag_matches:
        tweets = [t.strip() for t in tag_matches if 10 < len(t.strip()) <= MAX_TWEET_LENGTH]
        if tweets:
            return tweets

    # フォールバック：番号付きリスト
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        for line in raw.splitlines()
        if re.match(r"^\d+", line.strip())
    ]
    return [t for t in lines if 10 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい（URL込みで140文字以内）: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層（経営者・起業家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 必ず<tweet>タグで囲んで出力: <tweet>投稿テキスト</tweet>
- 最初の案が最もバズ度が高い「最推し案」にしてください
- ハッシュタグは最大2個{link_instruction}
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
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    return list(dict.fromkeys(headlines))[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、ビジネス層向けバズ投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1〜2個選び、
ビジネス層（経営者・起業家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 必ず<tweet>タグで囲んで出力: <tweet>投稿テキスト</tweet>
- 最初の案が最もバズ度が高い「最推し案」にしてください
- 医療×AI・社会変革・未来予測の切り口が入ると尚良い
- ハッシュタグは最大2個

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なビジネストピックについて、
ビジネス層（経営者・起業家）に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 必ず<tweet>タグで囲んで出力: <tweet>投稿テキスト</tweet>
- 最初の案が最もバズ度が高い「最推し案」にしてください
- テーマ優先順: AIエージェント・医療AI・生産性革命・AI格差・未来予測
- ハッシュタグは最大2個
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
