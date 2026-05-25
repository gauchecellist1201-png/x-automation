"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
バズる投稿パターンを徹底分析・適用
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+医療AI+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語 最速 AI ニュース
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- PHR/EHRへのブロックチェーン活用を研究・実装
- スイスの大学での研究経験、国連会議参加（グローバル視点）
- Claude Codeなど最新AIツールを日常活用
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

VIRAL_PATTERNS = """
## バズるAI投稿の必勝パターン（実績分析より）

【パターン1: 数字で証明型】
冒頭に具体的な数字・割合・時間削減を入れる
例: 「AIで診断精度が94%→99%に。医師が1時間かけた読影を30秒で」
→ 具体数字はシェア率3倍。ビジネス層が特に反応する

【パターン2: before/after型】
AIなし vs AIありのコントラストを1行で見せる
例: 「AIなし: 論文レビュー3日 / AIあり: 2時間。この差はもう埋まらない」
→ 視覚的コントラストがRT・保存を促進

【パターン3: 衝撃事実型】
「ほとんどの人が知らない」「実は〇〇だった」で始める
例: 「医師の80%が知らない、AIが見つける見落としの正体」
→「知らなかった」という感情が自然な拡散を生む

【パターン4: リスト型（スレッド誘導）】
「〇〇TOP3」「〇選」で保存を促し、スレッドへ誘導
例: 「2026年、医療AIが変えること 3つ🧵（詳しくはスレッドへ）」
→ 保存率が高く、後から何度も参照される

【パターン5: 問い・論争型】
答えのない問いを投げかけ、リプライを誘発
例: 「AIは医師を超えるか？超えた先に何が起きるか、誰も話していない」
→ リプライが増えアルゴリズムに乗りやすい

【パターン6: 共感・失敗型】
ビジネスパーソンの「あるある」を突く
例: 「AIを使いこなせないビジネスマンに共通する1つの思い込み」
→ 当事者意識で保存・シェアが爆増

【パターン7: 未来予測型】
専門家の目線で近未来を断言する
例: 「2026年末、AIが消す医療職種TOP3（今すぐ準備すべき）」
→ 権威性を演出し、保存・拡散を促す

【パターン8: 本音・独白型】
「正直に言う」「実は〇〇だった」の一人称で始める
例: 「正直に言う。Claude Codeなしで今の自分のプロダクトは存在しない」
→ 等身大の語りが親近感を生み、リプライ・引用RTを誘発
"""

TWEET_STRATEGY = """
## 投稿必勝ルール
1. 冒頭1行でスクロールを止める（上記パターンの冒頭フレーズを必ず活用）
2. 医療×AI×ビジネスの交差点を狙う（差別化ポイント）
3. 結論よりも「問い」か「続きが気になる終わり方」
4. ハッシュタグは #AI #生成AI のうち1〜2個のみ（多すぎると逆効果）
5. URLを入れる場合は文末に自然に配置（23文字換算）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_posts_with_meta(raw: str) -> list[dict]:
    """番号付きリストからツイート本文・画像提案を抽出"""
    results = []
    blocks = re.split(r"\n(?=\d+[\.\)])", raw.strip())
    for block in blocks:
        if not re.match(r"^\d+[\.\)]", block.strip()):
            continue
        lines = block.strip().splitlines()
        tweet_line = re.sub(r"^\d+[\.\)]\s*", "", lines[0]).strip()

        image_hint = ""
        for line in lines[1:]:
            if re.search(r"(画像|📷|スクリーン|グラフ|図|推奨)", line):
                image_hint = re.sub(r"^[📷\s\-＊*]*推奨画像[:：]?\s*", "", line).strip()
                break

        # URL を23文字換算して長さチェック
        clean_tweet = re.sub(r"https?://\S+", "x" * 23, tweet_line)
        if 0 < len(clean_tweet) <= MAX_TWEET_LENGTH + 10:
            results.append({"tweet": tweet_line, "image": image_hint})
    return results


def _extract_best_tweet(raw: str) -> list[str]:
    """後方互換用: テキストのみ返す"""
    return [p["tweet"] for p in _extract_posts_with_meta(raw)]


def generate_posts_with_meta_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[dict]:
    """Note記事 + 過去実績から戦略的投稿案（メタデータ付き）を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"
            )

    link_instruction = (
        f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内（URLは23文字換算）{link_instruction}
- 番号付きリスト（1. 2. 3.）で出力
- 各ツイートの直後の行に「📷 推奨画像: [添付すると効果的な画像の説明]」を追加
- {NUM_CANDIDATES}案それぞれ異なるバズパターンを使うこと

{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_posts_with_meta(raw)


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """後方互換用"""
    return [
        p["tweet"]
        for p in generate_posts_with_meta_from_notes(note_text, feedback_text, note_url)
    ]


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから最新ニュースをタイトルとURLで取得"""
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


def generate_posts_with_meta_from_rss() -> list[dict]:
    """最新AIニュースから投稿案（メタデータ付き）を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight_with_meta()

    headlines_text = "\n".join(
        f"- {item['title']}" + (f"  URL: {item['url']}" if item["url"] else "")
        for item in items
    )

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 各ツイートの直後の行に「📷 推奨画像: [添付すると効果的な画像の説明]」を追加
- {NUM_CANDIDATES}案それぞれ異なるバズパターンを使うこと
- 医療×AI、社会変革、ビジネス活用の観点を積極的に盛り込む
- 元ニュースのURLを使う場合は文末に配置

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_posts_with_meta(raw)


def generate_posts_from_rss() -> list[str]:
    """後方互換用"""
    return [p["tweet"] for p in generate_posts_with_meta_from_rss()]


def _generate_original_ai_insight_with_meta() -> list[dict]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界・医療AIの最重要トピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 各ツイートの直後の行に「📷 推奨画像: [添付すると効果的な画像の説明]」を追加
- {NUM_CANDIDATES}案それぞれ異なるバズパターンを使うこと
- Claude、GPT、医療AI、AIと社会変革のテーマを優先
"""
    raw = _call_claude(prompt)
    return _extract_posts_with_meta(raw)


def _generate_original_ai_insight() -> list[str]:
    """後方互換用"""
    return [p["tweet"] for p in _generate_original_ai_insight_with_meta()]
