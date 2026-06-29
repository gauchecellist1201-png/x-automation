"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AI・テクノロジーニュース
    "https://news.google.com/rss/search?q=AI+人工知能+ChatGPT+Claude&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+DX&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語高品質AIニュース
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイス大学での研究経験・国連会議参加、グローバル視点
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- Claude Codeなど最新AIツールを実際に使いこなしているリアルな実践者
"""

VIRAL_STRATEGY = """
## バズるAI投稿の戦略（ビジネス層向け）

【拡散されやすいフォーマット】
1. 「数字で驚かせる」型: 具体的データ・事実で冒頭インパクト
   例: "ChatGPTに〇〇やらせたら、3時間の仕事が8分で終わった。"
2. 「ほとんどの人が知らない」型: 専門家だけが知る逆張り視点
   例: "AIが医療を変えると皆言う。でも一番変わるのは診療ではなく〇〇だ。"
3. 「Before/After対比」型: 変化を可視化して危機感を煽る
   例: "1年前: AIを試験導入。今: AIなしで仕事できない。"
4. 「問いかけ終わり」型: コメント・RTを誘発する未解決の問い
5. 「リスト」型: 「〇選」「〇つの理由」は保存されやすい
6. 「告白・実話」型: 「〇〇してみたら〇〇だった」の体験談

【ビジネス層に刺さるキーワード】
- 生産性・時短・コスト削減・競争優位
- 「経営者が見落としている」「先行企業はもうやっている」
- 具体的な数字（時間・コスト・件数）
- 「2026年末までに」「3年以内に」の時間軸

【文体ルール】
- 冒頭1文でスクロールを止める
- 体言止め・改行を活用して読みやすく
- 難解な専門語は使わず、でも浅くならない
- ハッシュタグは #AI #生成AI のうち最大2個
- URLを含む場合は文末に自然に配置（URL=23文字換算）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str, max_len: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数制限内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_len]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい: {note_url}（URL=23文字換算）" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、説明不要
- 上記「バズるフォーマット」のいずれかを各案で異なる型を使うこと
- ビジネス層（経営者・医師・スタートアップ関係者）に刺さる内容{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_articles(max_items: int = 8) -> list[dict]:
    """RSS から記事タイトルとURLのリストを取得"""
    articles: list[dict] = []
    seen_titles: set[str] = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:4]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    articles.append({"title": title, "url": link})
        except Exception:
            continue
    return articles[:max_items]


def generate_posts_from_rss() -> tuple[list[str], str]:
    """最新AIニュースから @GAUCHE_cellist らしい意見投稿を生成。(tweets, best_url) を返す"""
    articles = fetch_rss_articles()
    if not articles:
        return _generate_original_ai_insight(), ""

    headlines_text = "\n".join(f"- {a['title']}" for a in articles)
    urls_by_title = {a["title"]: a["url"] for a in articles}

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、説明不要
- 上記「バズるフォーマット」のいずれかを各案で異なる型を使うこと
- 医療×AI、社会変革、ビジネスインパクトの観点を絡める
- ニュース元URLを文末に入れる場合はURL=23文字換算で140字以内に収める

## 今日の最新AIニュース（このうち最も重要な1本を選ぶ）
{headlines_text}

## 選んだニュースのURL（投稿に含めたい場合のみ使用）
最も重要と判断したニュースのURLを最後の行に「SELECTED_URL: <url>」形式で出力してください。
"""
    raw = _call_claude(prompt)

    # 選択されたURLを抽出
    best_url = ""
    for line in raw.splitlines():
        if line.startswith("SELECTED_URL:"):
            candidate_url = line.replace("SELECTED_URL:", "").strip()
            # URLが記事リストに含まれるか確認
            for article in articles:
                if article["url"] and article["url"] in candidate_url:
                    best_url = article["url"]
                    break
            break

    tweets = _extract_tweets(raw)
    return tweets, best_url


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最もホットなトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿文のみ、説明不要
- Claude / GPT-5 / 医療AI / AGI / AI×ビジネス変革などのテーマを優先
- 各案で異なるバズるフォーマットを使うこと
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def pick_best_tweet(candidates: list[str]) -> str:
    """Claude にベストな1案を選ばせる"""
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(candidates))
    prompt = f"""以下のX(Twitter)投稿候補から、ビジネス層への拡散力が最も高い1案を選んでください。
選んだ番号だけを答えてください（例: 2）。

{numbered}
"""
    raw = _call_claude(prompt).strip()
    match = re.search(r"\d+", raw)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return candidates[0]
