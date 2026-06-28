"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ビジネス層向けバズり投稿・ユーザー獲得に特化
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # 日本語：AIビジネス活用・最新動向
    "https://news.google.com/rss/search?q=生成AI+ビジネス+業務効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業+活用事例&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+自動化+DX+コスト削減+生産性&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア+テクノロジー&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
    # 英語：グローバル最新AIブレイキングニュース
    "https://venturebeat.com/ai/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家（スイス大学研究・国連会議登壇経験）
- ターゲット読者：AIに関心を持つビジネス層（経営者・マネージャー・起業家・意識高い会社員）
- スタイル：専門知識を平易な言葉で、読者に「使える気づき」と「なるほど感」を与える
- 医療×AI×社会変革の交差点から独自の洞察を静かに・鋭く発信
- Claude Codeなど最前線のAIツールを実際に使いこなす実践者
"""

TWEET_STRATEGY = """
## バズるAI投稿戦略（ビジネス層向けフォロワー獲得）

### 高エンゲージメントフックパターン（冒頭を必ずこれで始める）：
- 数字フック：「〇〇%の企業が既に〇〇」「〇時間→〇分に短縮」「月〇万円削減」
- 問いフック：「AIで本当に消える仕事は何だと思いますか？」
- 常識破壊：「プロンプトより大事なAI活用の鍵は、実は〇〇だった」
- 共感フック：「まだ〇〇を手作業でやってますか？」
- FOMO：「競合はもうAIで〇〇している。あなたは？」
- リスト系：「AIで生産性が10倍上がった習慣5選」

### 投稿構成テンプレート（A〜Eから選ぶ）：
A) [驚く事実/数字] → [具体的証拠・例] → [あなたへの問い]
B) [現状の課題共感] → [AI活用後の変化・Before→After] → [行動促進]
C) [反直感的な気づき] → [理由・背景] → [洞察・問い]
D) [すぐ使えるAI Tip] → [具体的なツール名・手順] → [試してほしい]
E) [最新AIニュース] → [ビジネスへの影響] → [機会・リスクの問い]

### 必須チェックリスト：
✓ 具体的な数字・ツール名（Claude/ChatGPT/Gemini等）・企業名を入れる
✓ ビジネスパーソンの日常業務に絡める（会議・メール・資料作成・採用等）
✓ リプライ・RTしたくなる終わり方（問い・驚き・共感・シェアしたい情報）
✓ ハッシュタグは #AI #生成AI #ChatGPT のうち最大2個

### NGパターン（絶対避ける）：
✗ 「AIは重要です」等の抽象的主張だけ
✗ 技術用語の羅列（読者が離脱）
✗ 弱い文末（「〜だと思います」「〜かもしれません」）
✗ 業界内向けの内輪ネタ
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
    """番号付きリストから投稿文を抽出し140文字以内に絞る（複数行対応）"""
    # 番号付きリストの区切りで分割（"1." "2)" など）
    segments = re.split(r'(?m)^\s*\d+[\.\)]\s+', raw)

    tweets = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # 空行の前（最初の段落）だけを使用
        first_para = seg.split('\n\n')[0]
        # 改行をスペースに統一して1行化
        tweet = re.sub(r'\s+', ' ', first_para).strip()
        # 【画像提案】等の注記を除去
        tweet = re.sub(r'【(画像|添付|補足).*?】.*$', '', tweet).strip()
        if 0 < len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    return tweets[:NUM_CANDIDATES]


def _extract_image_suggestions(raw: str) -> list[str]:
    """Claude出力から画像提案を抽出する"""
    suggestions = re.findall(r'【画像提案[：:]?\s*(.*?)】', raw)
    return suggestions


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSからタイトルとURLを取得する"""
    items: list[dict] = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10:
                    items.append({"title": title, "link": link})
        except Exception:
            continue
    # 重複除去（タイトルベース）
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:max_items]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            l for l in feedback_text.splitlines() if l.strip() and not l.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感・構成を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを自然に添える: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下のNote記事を読み、Xに投稿する文章を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内（URLは23文字換算）
- 番号付きリスト（1. 2. 3.）で出力。各案は1行で完結させる
- ビジネス層に刺さる切り口で、RTしたくなる内容にする
- ハッシュタグは1〜2個まで{link_instruction}
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、ビジネス層に刺さる意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {item['title']}" for item in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層に刺さる・RTされやすい洞察ツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。各案は1行で完結
- 医療×AI、ビジネス変革、未来への問いを絡めると尚良い
- 「知らないと損」「気づかなかった」と思わせる切り口を優先
- ハッシュタグは1〜2個まで

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
2026年現在のAI業界で最もホットなトピックについて、
ビジネス層に刺さる・RTされやすい洞察ツイートを{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{TWEET_STRATEGY}

ルール:
- 各投稿は140文字以内
- 番号付きリスト（1. 2. 3.）で出力。各案は1行で完結
- Claude Code・GPT-4o・Gemini、医療AI、AIと雇用・生産性などのテーマを優先
- 2026年現在の最新動向（エージェントAI、マルチモーダル、AI規制等）を踏まえる
- ハッシュタグは1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_best_tweet(raw)
