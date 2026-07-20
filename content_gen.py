"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語 AI ニュース
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=医療AI+ヘルスケアAI+AI診断&hl=ja&gl=JP&ceid=JP:ja",
    # 英語 AI ニュース（グローバルトレンドを把握）
    "https://news.google.com/rss/search?q=AI+agent+Claude+Anthropic+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+healthcare+medical+AI&hl=en&gl=US&ceid=US:en",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求
- 課題解決志向、グローバル視点（スイス研究経験、国連会議参加）
- 専門的知識を持ちながら、読者に考えさせる問いを投げかけるスタイル
- 押しつけがましくなく、静かに鋭い洞察を届ける
- ビジネス層（経営者・スタートアップ・医療関係者）がメインターゲット
"""

TWEET_STRATEGY = """
## バズるAI投稿の戦略（実証済みパターン）

### 構造パターン（いずれか1つを選ぶ）
A) 【逆説型】「AIは〇〇を〜した。でも本当の問いは△△だ。」
B) 【数字フック型】「XX年で変わったこと：◯◯が✕✕になった。」
C) 【問い型】「〜について、まだ誰も答えを持っていない。それでも我々は〜している。」
D) 【現実直視型】「〜という現実がある。これは〜の問題ではなく、〜の問題だ。」
E) 【格差・二極化型】「AIを使いこなす人と使われる人の差は、〜から生まれる。」

### エンゲージメント最大化のルール
1. 最初の15文字で「続きを読みたい」と思わせる
2. 医療・教育・格差・未来への問いかけを絡める（RTされやすい）
3. データや具体的事例を1つ入れる（信頼性+共有欲求）
4. 結論ではなく「問い」や「矛盾」で終わる（コメント誘発）
5. ハッシュタグは末尾に1〜2個のみ（#AI #医療AI #生成AI から選択）
6. ビジネス層が「転送したくなる」インサイトを含める
7. 絵文字は使わない（知性的な雰囲気を保つ）

### 避けるべきパターン
- 「〜のまとめ」「〜をご紹介」（コモディティ化した表現）
- 過度な励ましや動機付け（インフルエンサーっぽすぎる）
- 全ての情報を詰め込む（1ツイート1インサイトが鉄則）
"""

VIRAL_EXAMPLES = """
## 高エンゲージメント投稿の例（文体・温度感の参考）
AIが「考える」ようになっても、「感じる」ことができるのかはまだ誰も答えを持っていない。それでも私たちは医療にAIを使い始めている。 #AI
医療データは誰のものか。患者のものであるはずなのに、今は病院のサーバーに眠っている。ブロックチェーンはこれを変えられる。 #医療DX
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_best_tweet(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出し140文字以内に絞る"""
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+", l.strip())
    ]
    return [t for t in lines if 0 < len(t) <= MAX_TWEET_LENGTH]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を再現）\n{examples}\n"

    # NOTE_URL を記事から自動抽出（なければ引数を使用）
    if not note_url:
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break

    link_instruction = f"\n- 文末にNoteリンクを入れてもよい（URLは23文字換算）: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力（本文のみ、説明不要）
- ハッシュタグは末尾に1〜2個まで{link_instruction}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[str]:
    headlines: list[str] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                # Google Newsの「- メディア名」を除去
                title = re.sub(r"\s+-\s+\S+$", "", title).strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    # 重複除去してビジネス層に刺さりそうなキーワードを優先
    unique = list(dict.fromkeys(headlines))
    priority_keywords = ["医療", "規制", "格差", "雇用", "治療", "診断", "経営", "戦略", "healthcare", "regulation", "agent"]
    priority = [h for h in unique if any(k in h for k in priority_keywords)]
    others = [h for h in unique if h not in priority]
    return (priority + others)[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    headlines = fetch_rss_headlines()
    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最もビジネス層に刺さるトピックを1つ選び、
井出直毅らしい深い洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（本文のみ、説明不要）
- 医療×AI、社会変革、ビジネス格差、未来への問いを絡めると尚良い
- ハッシュタグは末尾に1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年7月のAI業界で最も重要なトピックについて、
井出直毅らしい深い洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}
{VIRAL_EXAMPLES}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力（本文のみ、説明不要）
- 優先テーマ: AIエージェント普及・医療AI・AI規制・教育格差・創薬AI
- ハッシュタグは末尾に1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
