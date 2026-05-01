"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語AIニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+ビジネス+DX+自動化+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語AIニュース（トレンド把握用）
    "https://news.google.com/rss/search?q=AI+breakthrough+Claude+GPT+Gemini&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+business+2026&hl=en&gl=US&ceid=US:en",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究経験、国連会議参加など、グローバル視点を保有
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- ターゲット読者：ビジネスパーソン、経営者、医療従事者、テック系会社員
"""

VIRAL_PATTERNS = """
## バズりやすいツイートのパターン（いずれか1つを必ず使うこと）

A【数字リスト型】
例: "AIで仕事が変わる5つの兆候" → 具体的な数字で信頼感と読みやすさを演出

B【逆説・意外性型】
例: "AIが普及するほど、人間の〇〇の価値が上がる理由" → 読者の期待を裏切り、考えさせる

C【体験・告白型】
例: "医学生がAIを6ヶ月使い続けた結果" → 一人称で具体性を出し、共感を呼ぶ

D【問いかけ型（RTされやすい）】
例: "あなたの会社、まだこのやり方してますか？" → 読者を当事者にする問いで引き込む

E【具体的数値・実績型】
例: "AIで10時間→20分になった業務がある。それより衝撃なのは…" → 数値で信憑性を示す

F【業界インサイダー型】
例: "医師×AIエンジニアとして言わせてほしい。" → 専門家の立場からの発言は拡散されやすい

G【未来予測・警告型】
例: "2026年末、AIを使えない人と使える人の年収差は…" → 危機感と好奇心を刺激する

H【比較・ランキング型】
例: "Claude vs GPT、医療用途で使ってみた本音" → 比較は検索されやすく、保存されやすい
"""

TWEET_STRATEGY = """
## 戦略
1. ビジネス層が「保存・RTしたくなる」実用的な情報か洞察を提供する
2. 専門的だが難解すぎない言葉選び（中学生でも意味がわかるが、深い内容）
3. 医療・社会変革・未来への問いかけを絡めると井出らしさが出る
4. 結論より「問い」「続き」で終わるとエンゲージメントが上がる
5. ハッシュタグは #AI #生成AI のうち1〜2個まで（多いと逆効果）
6. 数字・具体例・固有名詞を入れると信頼感が増す
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_numbered_items(raw: str, max_len: int = MAX_TWEET_LENGTH) -> list[str]:
    """番号付きリストから投稿文を抽出し文字数制限内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+[\.\)]", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= max_len]


def _extract_section(raw: str, marker: str) -> str:
    """マーカー行以降のテキストブロックを抽出する"""
    lines = raw.splitlines()
    capturing = False
    result = []
    for line in lines:
        if marker.lower() in line.lower():
            capturing = True
            continue
        if capturing:
            if re.match(r"^#{1,3}\s", line) or re.match(r"^---", line):
                break
            result.append(line)
    return "\n".join(result).strip()


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力
- ハッシュタグは1〜2個まで
- 使用したバズパターン（A〜H）を各案の末尾に【パターンX】と記載{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_numbered_items(raw)


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- 医療×AI、社会変革、未来への問いを絡めると尚良い
- ハッシュタグは1〜2個まで
- 使用したバズパターン（A〜H）を各案の末尾に【パターンX】と記載

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_numbered_items(raw)


def generate_thread_post(topic: str, headlines: list[str] | None = None) -> str:
    """スレッド形式の投稿を生成する（高エンゲージメント狙い）"""
    context = ""
    if headlines:
        context = "\n最新ニュース参考:\n" + "\n".join(f"- {h}" for h in headlines[:5])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のトピックについて、Xスレッド形式（3〜5ツイート）の投稿を作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

スレッドのルール:
- 1ツイート目（フック）: 読者を引き込む衝撃的な1文。絵文字1つ＋数字を使う
- 2〜4ツイート目（本論）: 各140文字以内。具体的な数値・事例・洞察を1つずつ展開
- 最終ツイート: 問いかけ or 行動を促すCTAで締める
- 全体を通じて「医療×AI」「ビジネス変革」の視点を盛り込む
- 出力形式: 「【1/N】...」「【2/N】...」の形式で

トピック: {topic}
{context}
"""
    return _call_claude(prompt)


def generate_image_prompt(post_text: str) -> str:
    """投稿に添付する画像のDALL-E / Midjourney用プロンプトを生成"""
    prompt = f"""以下のX投稿に添付する画像を生成するための、英語のDALL-Eプロンプトを1つ作成してください。

投稿文:
{post_text}

画像の要件:
- ビジネス・テクノロジー系のプロフェッショナルな雰囲気
- 医療とAIの融合を感じさせるビジュアル（必要に応じて）
- 日本のビジネスパーソンが「保存したくなる」インフォグラフィックか写真風
- シンプルで視認性が高い
- テキストを画像内に入れない

英語プロンプトのみを出力してください（説明文不要）:"""
    return _call_claude(prompt).strip()


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    """複数RSSから重複なしで最新ヘッドラインを取得"""
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Google News の "- メディア名" を除去
                title = re.sub(r"\s*-\s*[^\-]+$", "", title).strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    # 重複除去・上位件数に絞る
    return list(dict.fromkeys(headlines))[:max_items]


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力
- Claude、GPT、医療AI、AIと社会変革などのテーマを優先
- 使用したバズパターン（A〜H）を各案の末尾に【パターンX】と記載
"""
    raw = _call_claude(prompt)
    return _extract_numbered_items(raw)
