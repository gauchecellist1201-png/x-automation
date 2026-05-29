"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ビジネス+経営+導入&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+Claude+OpenAI+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AIエージェント+自動化+DX+ROI&hl=ja&gl=JP&ceid=JP:ja",
    "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- スイスの大学での研究・国連会議参加、グローバル視点
- Claude Codeなど最新AIツールを実際に活用中
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
"""

VIRAL_TWEET_TEMPLATES = """
## バズるツイートの型（実績データ分析済み・必ずいずれかの型を使うこと）

【型1: 衝撃の事実型】誰もが信じる通説を否定→真実を提示（RTされやすい）
例: 「AIは仕事を奪う」は間違い。実際に奪われているのは"判断を止めた人"の仕事だ。 #AI

【型2: 数字で殴る型】具体的な数字で読者を驚かせる（保存されやすい）
例: GPT-4導入企業のROI中央値が4.2倍という調査結果。この差はどこで生まれるか。 #生成AI

【型3: 問いで刺す型】答えを与えず読者に考えさせて止まらせる（引用RTを誘う）
例: AIが「創造」できるなら、人間に残る仕事とは何か。医師として、これを考え続けている。 #AI

【型4: 対比型】Before/Afterで変化を可視化（インパクト大）
例: 1年前→AI活用を検討中の企業が多数派。今→活用していない企業が少数派へ転換中。 #DX

【型5: 警告型】このまま何もしないと損をする感覚（経営者に刺さる）
例: 今AIに投資していない企業は、10年前にスマホ対応しなかった企業と同じ分岐点にいる。

【型6: 独自洞察型】誰も言っていないことを権威的に語る（フォロー増加）
例: AIエージェント時代に生き残るのは「問い続ける人」だけ。答えはもうAIが出す時代。 #AI

【型7: リスト型】スキャンしやすく保存されやすい（エンゲージメント高）
例: 医療AIで今すぐ変わること5つ: ①診断支援 ②投薬最適化 ③患者記録 ④予後予測 ⑤オペ支援

【型8: 予測型】大胆な予測で注目を集める（議論を呼ぶ）
例: 2027年、AIが診断する割合が現在の3倍に達する。問題はAIではなく、受け入れる側だ。 #医療AI
"""

BUSINESS_AUDIENCE_STRATEGY = """
## ビジネス層（経営者・役員・マネージャー・スタートアップ創業者）へのリーチ戦略

彼らが反応するキーワード・フレーム:
- 競合優位: "競合はすでに〜" "先行者利益" "市場シェア"
- ROI・数字: "平均●%削減" "コスト●分の一" "生産性●倍"
- 意思決定の焦り: "今動くべき理由" "手遅れになる前に" "この3ヶ月が分岐点"
- 業界変革: "〜業界に起きていること" "パラダイムシフト"
- リーダーシップ: "経営者として知っておくべき" "意思決定を変える"

投稿フォーマット:
- 1文目: フック（驚き・問い・データ・逆説）で止まらせる
- 2〜3文: 本質・洞察・具体例
- 最後: 問いかけか示唆（読者に何かを考えさせる）
- ハッシュタグ: #AI #生成AI #DX のうち最大2個

絶対に避けること:
- 曖昧な表現（「活用しましょう」「大切です」）
- 過度に技術的な専門用語の羅列
- 広告・PR的なトーン
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_candidates(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)【】]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+[\.\)【】]", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def select_best_post(posts: list[str]) -> str:
    """Claude がバズ可能性でランク付けして最良の1投稿を選択"""
    if len(posts) <= 1:
        return posts[0] if posts else ""
    candidates = "\n".join(f"{i+1}. {p}" for i, p in enumerate(posts))
    prompt = f"""以下のX投稿候補から、ビジネス層に最もリーチしバズる可能性が高い1つを選んでください。
選択基準: フックの強さ・具体性・感情的インパクト・共有したくなる度合い

{candidates}

回答: 番号のみ（1〜{len(posts)}の整数）"""
    raw = _call_claude(prompt).strip()
    for ch in raw:
        if ch.isdigit() and 1 <= int(ch) <= len(posts):
            return posts[int(ch) - 1]
    return posts[0]


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
{VIRAL_TWEET_TEMPLATES}
{BUSINESS_AUDIENCE_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。投稿本文のみ（解説不要）
- 必ず上記8型のいずれかを使うこと
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_candidates(raw)


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
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを1つ選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_TEMPLATES}
{BUSINESS_AUDIENCE_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿本文のみ（解説不要）
- 必ず上記8型のいずれかを使うこと
- 医療×AI・社会変革・ビジネス変革の文脈を絡めると尚良い
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_candidates(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_TWEET_TEMPLATES}
{BUSINESS_AUDIENCE_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。投稿本文のみ（解説不要）
- 必ず上記8型のいずれかを使うこと
- Claude・GPT・医療AI・AIエージェント・AIと社会変革などのテーマを優先
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_candidates(raw)
