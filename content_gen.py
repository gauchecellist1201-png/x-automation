"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）

バズり分析に基づくビジネス層向けAI投稿自動生成
"""

import os
import re
import json
import feedparser
import anthropic
from dataclasses import dataclass, field

# ──────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

# ビジネス層向けAIニュースRSSフィード（拡充版）
RSS_FEEDS = [
    # Google News - AI全般（日本語）
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    # Google News - 生成AI・LLM
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    # Google News - AIビジネス活用
    "https://news.google.com/rss/search?q=AI+ビジネス+活用+生産性+DX&hl=ja&gl=JP&ceid=JP:ja",
    # Google News - AI規制・社会
    "https://news.google.com/rss/search?q=AI+規制+倫理+社会変革+2026&hl=ja&gl=JP&ceid=JP:ja",
    # Ledge AI（日本語AI専門メディア）
    "https://feeds.feedburner.com/ledge-ai",
    # Google News - 英語AI最新（グローバルトレンド）
    "https://news.google.com/rss/search?q=AI+artificial+intelligence+GPT+Claude+Gemini&hl=en&gl=US&ceid=US:en",
    # Google News - AI経営・スタートアップ
    "https://news.google.com/rss/search?q=AI+startup+funding+billion+2026&hl=en&gl=US&ceid=US:en",
]

# ──────────────────────────────────────────────
# データクラス
# ──────────────────────────────────────────────

@dataclass
class TweetCandidate:
    text: str
    viral_pattern: str      # 使用したバイラルパターン名
    source_headline: str    # 元ニュース見出し
    visual_hint: str        # 画像・ビジュアル提案
    buzz_score: int         # 推定バズスコア 1–10
    tags: list[str] = field(default_factory=list)

# ──────────────────────────────────────────────
# プロフィール & 戦略プロンプト
# ──────────────────────────────────────────────

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求（PHR/EHR・非中央集権型医療データ）
- スイス大学研究経験・国連会議参加などグローバル視点
- Claude Codeなど最先端AIツールを実務活用
- 押しつけがましくなく、静かに鋭い洞察を届けるスタイル
- 専門知識を平易な言葉で届け、読者に「考えさせる問い」を投げかける
"""

# バズる投稿パターン（ビジネス層向けAI特化・研究ベース）
VIRAL_PATTERNS = """
## バズるAI投稿の10パターン（ビジネス層向け）

【P1: 数字フック】
具体的な数字・比率・時間で「驚き」を生む。
例：「AIで作業時間が1/10に。8時間→45分になった仕事はこれ」

【P2: 逆張り（カウンターナラティブ）】
世間の常識や恐怖心に反論する切り口。
例：「AIに仕事を奪われる——これは間違いだ。正確には仕事の"形"が変わる」

【P3: リスト型（保存したくなる実用情報）】
「〇選」形式は保存・RT率が高い。
例：「経営者が今すぐ入れるべきAIツール5選（無料あり）」

【P4: 速報＋独自解釈】
ニュースを一言で要約し、自分の視点を加える。
例：「OpenAIがXXを発表。これが意味するのは〇〇——医療業界への影響は特に大きい」

【P5: 問いかけフック（エンゲージメント誘引）】
返信・RT・いいねを誘う問いで締める。
例：「あなたの会社のAI活用度は？まだ使っていないなら、競合との差は既に2年分」

【P6: Before/After（変化の可視化）】
導入前後の差分を示す。
例：「AI前：企画書作成に3日 → AI後：2時間。浮いた時間で何をするか、が経営者の差」

【P7: 予測・トレンド先読み】
未来を語る投稿はRT・引用RTされやすい。
例：「2年後、AIを使わないコンサル会社は存在できない。これは誇張ではない」

【P8: 警告・リスク訴求】
損失回避本能を刺激する。
例：「AIツールを何も考えずに使うと社内情報が学習データになる——知らない人が多すぎる」

【P9: 共感＋解決策】
「わかる」と思わせてから解決策を提示。
例：「ChatGPTを使ってみたけど、なんか薄い回答しか返ってこない——それ使い方の問題です」

【P10: スレッド予告（続きを読ませる）】
「(1/n)」で始め、深い洞察への期待感を生む。
例：「AIと医療について、誰も言わない真実を書く(1/5)↓」
"""

BUSINESS_AUDIENCE_GUIDE = """
## ビジネス層（経営者・マネージャー・起業家）が反応するテーマ
- コスト削減・ROI（「○○万円節約」「○倍の生産性」）
- 競合優位性・市場機会（「競合はもう使っている」）
- 意思決定の質向上（「AIで判断精度が上がった事例」）
- リスク管理（「知らないと損する」「法的リスク」）
- 採用・人材戦略（「AIスキルが採用基準になる時代」）
- 具体的なワークフロー改善事例
- 業界別インパクト（医療・製造・金融・小売）
"""

# ──────────────────────────────────────────────
# Claude API 呼び出し
# ──────────────────────────────────────────────

def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ──────────────────────────────────────────────
# ツイート抽出・パース
# ──────────────────────────────────────────────

def _parse_tweet_candidates(raw: str, source_headline: str = "") -> list[TweetCandidate]:
    """
    Claude の JSON 出力から TweetCandidate リストを生成。
    JSON パースに失敗した場合は番号付きリストからフォールバック抽出。
    """
    # JSON ブロックを探す
    json_match = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
    if not json_match:
        json_match = re.search(r"\[\s*\{[\s\S]+\}\s*\]", raw)

    if json_match:
        try:
            data = json.loads(json_match.group(1) if "```" in raw else json_match.group(0))
            candidates = []
            for item in data:
                text = item.get("text", "").strip()
                if not text or len(text) > MAX_TWEET_LENGTH + 30:  # URL込みの余裕
                    continue
                candidates.append(TweetCandidate(
                    text=text,
                    viral_pattern=item.get("viral_pattern", ""),
                    source_headline=item.get("source_headline", source_headline),
                    visual_hint=item.get("visual_hint", ""),
                    buzz_score=int(item.get("buzz_score", 5)),
                    tags=item.get("tags", []),
                ))
            if candidates:
                return sorted(candidates, key=lambda c: c.buzz_score, reverse=True)
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # フォールバック：番号付きリストから抽出
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", l).strip()
        for l in raw.splitlines()
        if re.match(r"^\d+[\.\)]\s*", l.strip())
    ]
    return [
        TweetCandidate(
            text=t,
            viral_pattern="不明",
            source_headline=source_headline,
            visual_hint="",
            buzz_score=5,
        )
        for t in lines
        if 0 < len(t) <= MAX_TWEET_LENGTH + 30
    ]


# ──────────────────────────────────────────────
# RSS フェッチ
# ──────────────────────────────────────────────

def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """
    複数RSSから最新ニュースを取得。
    戻り値: [{"title": ..., "link": ..., "source": ...}, ...]
    """
    seen_titles: set[str] = set()
    results: list[dict] = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0"})
            source_name = feed.feed.get("title", feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                # Google Newsの余分な「- メディア名」を除去
                title = re.sub(r"\s+-\s+[^\-]+$", "", title).strip()
                link = entry.get("link", "")
                if title and len(title) > 8 and title not in seen_titles:
                    seen_titles.add(title)
                    results.append({"title": title, "link": link, "source": source_name})
                if len(results) >= max_items * 2:
                    break
        except Exception:
            continue

    return results[:max_items]


# ──────────────────────────────────────────────
# 投稿生成：Note記事から
# ──────────────────────────────────────────────

def generate_posts_from_notes(
    note_text: str,
    feedback_text: str,
    note_url: str = "",
) -> list[TweetCandidate]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""

    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines()
            if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = (
                f"\n## 過去に反応が良かった投稿（文体・温度感を再現）\n{examples}\n"
            )

    link_note = f"文末にNoteリンクを入れてもよい: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、ビジネス層に刺さるバズりやすいX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_AUDIENCE_GUIDE}

## 出力ルール
- 各投稿は140文字以内（URLは23文字換算）
- {link_note}
- ハッシュタグは1〜2個まで（#AI #生成AI #AIビジネス から選ぶ）
- 以下のJSON形式で出力すること

```json
[
  {{
    "text": "投稿本文（140文字以内）",
    "viral_pattern": "P1: 数字フック",
    "source_headline": "元記事のテーマを一言で",
    "visual_hint": "推奨する画像・ビジュアルの方向性（例：グラフ、スクショ、図解など）",
    "buzz_score": 8,
    "tags": ["#AI", "#生成AI"]
  }}
]
```
{few_shot_section}

## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)


# ──────────────────────────────────────────────
# 投稿生成：RSSニュースから
# ──────────────────────────────────────────────

def generate_posts_from_rss() -> list[TweetCandidate]:
    """最新AIニュースを元に、@GAUCHE_cellist らしいビジネス向け意見投稿を生成"""
    headlines = fetch_rss_headlines()

    if not headlines:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(
        f"- {h['title']}（{h['source']}）" for h in headlines
    )

    # 最も注目度の高いニュースを選ばせる
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースの中から**最もビジネス層に刺さるトピック1つ**を選び、
井出直毅らしい洞察・意見をX投稿として{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_AUDIENCE_GUIDE}

## 出力ルール
- 各投稿は140文字以内
- ハッシュタグは1〜2個まで
- 医療×AI、社会変革、ビジネスインパクトを絡めると尚良い
- 以下のJSON形式で出力すること（選んだニュースの見出しをsource_headlineに入れる）

```json
[
  {{
    "text": "投稿本文（140文字以内）",
    "viral_pattern": "P4: 速報＋独自解釈",
    "source_headline": "選んだニュース見出し",
    "visual_hint": "推奨するビジュアルの方向性（例：ニュースのスクショ、比較表、チャートなど）",
    "buzz_score": 8,
    "tags": ["#AI", "#生成AI"]
  }}
]
```

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    top_headline = headlines[0]["title"] if headlines else ""
    return _parse_tweet_candidates(raw, source_headline=top_headline)


# ──────────────────────────────────────────────
# 投稿生成：オリジナル洞察（RSS取得失敗時）
# ──────────────────────────────────────────────

def _generate_original_ai_insight() -> list[TweetCandidate]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層に刺さる洞察を持つX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{BUSINESS_AUDIENCE_GUIDE}

## 出力ルール
- 各投稿は140文字以内
- Claude、GPT、医療AI、AIと経営、AIと社会変革などのテーマを優先
- ハッシュタグは1〜2個まで
- 以下のJSON形式で出力すること

```json
[
  {{
    "text": "投稿本文（140文字以内）",
    "viral_pattern": "P7: 予測・トレンド先読み",
    "source_headline": "（オリジナル洞察）",
    "visual_hint": "推奨するビジュアルの方向性",
    "buzz_score": 7,
    "tags": ["#AI"]
  }}
]
```
"""
    raw = _call_claude(prompt)
    return _parse_tweet_candidates(raw)
