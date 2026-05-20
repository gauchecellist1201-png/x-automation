"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 - 最新AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+ビジネス活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+業務DX+効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアDX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語 - 最先端情報
    "https://hnrss.org/frontpage",
    "https://venturebeat.com/category/ai/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHR×ブロックチェーン、非中央集権的医療データ管理を研究
- スイスの大学での研究経験、国連会議参加（グローバル視点）
- Claude Codeなど最先端AIツールを日常的に活用
- AIが医師・医学生でもコードなしでプロダクトを作れる時代の牽引者
- 静かで鋭い洞察、押しつけがましくない文体が特徴
"""

VIRAL_STRATEGY = """
## バズるX投稿の鉄則（ビジネス層・AI関心層向け）

【パターン1: 数字で信頼獲得】
「AIを〇ヶ月使い込んで分かった、たった1つのこと」
「作業時間が〇〇%削減。その方法とは」

【パターン2: 問いかけでエンゲージ】
「あなたの会社、まだ〇〇してない？ 2年後に差がつく」
「医療にAIを使う前に、考えておくべきことがある」

【パターン3: 逆説・意外性でRT誘発】
「AIが普及するほど、〇〇の価値が上がる逆説」
「みんなが〇〇を使う時代に、必要になるのは〇〇力だ」

【パターン4: 速報+意見で存在感】
「〇〇が今日発表。ビジネス実務への影響を3行で解説↓」
「これは本物の変化。〇〇がついに実用レベルに」

【パターン5: 警告+FOMO】
「〇〇を知らないまま2026年を過ごすと、確実に置いて行かれる」

【パターン6: スレッド予告でタップ率UP】
末尾に「↓」や「→詳しくは」を入れることでエンゲージメントが上がる

## 必須ルール
- 各投稿は140文字以内（URLは23文字換算）
- ハッシュタグは #AI または #生成AI のうち最大1個
- 医療・社会変革・ビジネスの観点を自然に絡める
- 問いかけか洞察で締める（断言より「問い」が拡散されやすい）
- ビジネス層が「RTして共有したい」と思う価値ある情報を凝縮する
- 「〜です。〜ます。」より体言止めや余韻のある終わり方を優先
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def select_best_tweet(candidates: list[str]) -> str:
    """Claude が候補からビジネス層に最もバズりそうな1つを選ぶ"""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX投稿候補から、ビジネス層向けに最もバズりそうな1つを選んでください。

選択基準:
- RT・いいねされやすいか（問いかけ・意外性・有用性）
- 「医療×AI」「社会変革」の専門性と読みやすさのバランス
- 140文字以内か
- 体言止めや余韻のある終わり方か

候補:
{numbered}

回答形式: 番号のみ（例: 2）"""

    raw = _call_claude(prompt).strip()
    try:
        match = re.search(r"\d", raw)
        if match:
            idx = int(match.group()) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]
    except Exception:
        pass
    return candidates[0]


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
{VIRAL_STRATEGY}

追加ルール:
- AIに関するプロレベルの洞察を、一般読者にも刺さる言葉で{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """タイトルとURLをセットで取得する"""
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
    return items[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に @GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- 医療×AI、社会変革、ビジネス変革の観点を絡めると尚良い
- 最新情報への言及が速報感を生み出しバズりやすい

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

追加ルール:
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 2026年現在のAI最前線を踏まえた内容にすること
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
