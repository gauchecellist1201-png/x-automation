"""
Claude API を使ったバイラル投稿文生成モジュール
ターゲット: ビジネス層（経営者・マネージャー・DX推進担当）
アカウント: @GAUCHE_cellist（井出直毅）
"""
import os
import re

import anthropic

from viral_analyzer import VIRAL_PATTERNS, fetch_trends, format_for_prompt

# Xの文字数上限は280。URLは23文字換算。絵文字は2文字換算のため余裕を持たせる。
MAX_TWEET_LENGTH = 260
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合を追求（PHR/EHRへのブロックチェーン活用など）
- スイスの大学での研究経験、国連会議参加のグローバル視点
- 2026年現在、Claude Codeなど最新AIツールを活用した医療×AI×ブロックチェーンの価値創出
- 文体：押しつけがましくなく、静かに鋭い洞察を届けるスタイル
"""

VIRAL_STRATEGY = """
## ビジネス層を動かすバイラル投稿の設計原則

### ターゲット読者
経営者・役員、マネージャー層、DX推進担当、コンサルタント、スタートアップ創業者

### バイラル要素（重要度順）
1. **冒頭1行が命**: スクロールが止まる強烈なフック（疑問・数字・衝撃・FOMO）
2. **具体的な数字・事例**: 「〇〇%向上」「〇〇社が導入」など抽象論より事実
3. **ビジネス課題との直結**: ROI・コスト・競合・生産性など経営視点
4. **行動喚起の終わり方**: 問い掛け or 強烈な一言でRT・リプライを誘発
5. **FOMO演出**: 「今知らないと遅い」「3年後に後悔する」系の緊張感

### 使えるフック表現例
- 「正直に話します。〇〇について」（信頼感）
- 「まだ〇〇していない企業は危ない」（FOMO）
- 「〇〇を試した結果→衝撃的だった」（好奇心）
- 「AIで変わった3つのこと（数字）」（リスト期待）
- 「2027年、〇〇はどうなるか」（未来不安）
- 「みんな誤解している〇〇の話」（反論欲求）

### 形式ルール
- 単発ツイート：200〜260文字（URLは自動で23文字換算される）
- 改行を使って視覚的に読みやすく（特にリスト形式は効果的）
- ハッシュタグは文末に1〜2個まで（多すぎは逆効果）
- 絵文字は1〜2個まで、効果的な場所に限定
"""


def _call_claude(prompt: str, max_tokens: int = 1500) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_numbered_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出（複数行対応）"""
    tweets: list[str] = []

    # 1. / 2. / 3. または ① ② ③ などで区切られたブロックを分割
    blocks = re.split(r"\n(?=[①②③④⑤]|[1-9][\.\)]\s)", raw)

    for block in blocks:
        clean = re.sub(r"^[①②③④⑤]\s*", "", block.strip())
        clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
        clean = re.sub(r"^【案\d+】\s*", "", clean)
        clean = clean.strip()

        if 10 <= len(clean) <= MAX_TWEET_LENGTH:
            tweets.append(clean)

    return tweets[:NUM_CANDIDATES]


def _extract_thread_tweets(raw: str) -> list[str]:
    """スレッド形式（1/n、2/n...）から個別ツイートを抽出"""
    tweets: list[str] = []

    # "1/4:" "2/4:" など
    pattern = re.compile(
        r"(?:^|\n)\s*(?:🧵\s*)?(\d+/\d+\s*[：:・]?\s*)(.*?)(?=\n\s*(?:🧵\s*)?\d+/\d+|\Z)",
        re.DOTALL,
    )
    for _, content in pattern.findall(raw):
        tweet = content.strip()
        if 10 <= len(tweet) <= MAX_TWEET_LENGTH:
            tweets.append(tweet)

    # フォールバック: 空行区切りの段落
    if not tweets:
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        tweets = [p for p in paragraphs if 10 <= len(p) <= MAX_TWEET_LENGTH]

    return tweets[:6]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドからビジネス層向けバイラル投稿案を生成"""
    trends = fetch_trends(max_items=8)

    if not trends:
        return _generate_original_insight()

    top = trends[0]
    trends_text = format_for_prompt(trends, max_items=6)

    viral_examples = "\n".join(f"- {v}" for v in list(VIRAL_PATTERNS.values())[:4])

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。

{AUTHOR_PROFILE}

{VIRAL_STRATEGY}

## バイラル構造パターン（参考）
{viral_examples}

## 今日の最新AIニュース（バイラリティスコア順）
{trends_text}

---

上記ニュースの中から**ビジネス層に最も刺さるトピック**を1つ選び、
バイラルを意識したX投稿を{NUM_CANDIDATES}案作成してください。

条件：
- 番号付きリスト（1. 2. 3.）で出力
- 各投稿：200〜260文字（URLは23文字換算）
- 冒頭1行で読者のスクロールを止めること（最重要）
- 最も注目度の高いニュースのURL（{top.url}）を文末に1つ自然に組み込む
- ビジネス層が「RT・保存」したくなる内容に
- ハッシュタグは文末に1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw)


def generate_viral_thread() -> list[str]:
    """バイラルスレッド（連続ツイート）を生成"""
    trends = fetch_trends(max_items=5)

    if not trends:
        top_topic = "生成AIのビジネス活用"
        top_url = ""
    else:
        top = trends[0]
        top_topic = top.title
        top_url = top.url

    url_note = f"\n- 最後のツイートにURL: {top_url}" if top_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。

{AUTHOR_PROFILE}

{VIRAL_STRATEGY}

## テーマ
{top_topic}

---

このテーマで、ビジネス層に刺さるXスレッド（連続ツイート4〜5本）を作成してください。

スレッド構成：
1/n: 衝撃・好奇心を誘う冒頭フック（🧵絵文字必須）
2/n: 核心的な事実・データ・具体的事例
3/n: ビジネスへの直接的影響と活用法
4/n: 未来予測または経営者への問い掛け
5/n（任意）: まとめ + URL{url_note}

形式：
- 「1/4」「2/4」形式で各ツイートを区切る
- 各ツイートは200文字以内（短めに保つ）
- 全体で「保存・RT・フォロー」したくなる流れに
"""
    raw = _call_claude(prompt, max_tokens=2000)
    return _extract_thread_tweets(raw)


def generate_posts_from_notes(
    note_text: str, feedback_text: str, note_url: str = ""
) -> list[str]:
    """Note記事からバイラル投稿案を生成（フィードバック学習付き）"""
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line
            for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = (
                f"\n## 過去に反応が良かった投稿（文体・温度感を参考に）\n{examples}\n"
            )

    url_note = f"\n- 文末にNoteリンクを自然に組み込む: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。

{AUTHOR_PROFILE}

{VIRAL_STRATEGY}

{few_shot}

## Note記事本文
{note_text[:4000]}

---

この記事を元に、ビジネス層向けバイラルX投稿を{NUM_CANDIDATES}案作成してください。

条件：
- 番号付きリスト（1. 2. 3.）で出力
- 各投稿：200〜260文字{url_note}
- 記事の最も「刺さる」洞察を冒頭1行に凝縮
- ハッシュタグは文末に1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw)


def _generate_original_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察投稿生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。

{AUTHOR_PROFILE}

{VIRAL_STRATEGY}

---

2026年のAI×ビジネスで最も重要なテーマについて、
ビジネス層向けバイラルX投稿を{NUM_CANDIDATES}案作成してください。

優先テーマ（いずれか1つを選ぶ）：
- エージェントAI × 業務自動化のビジネスインパクト
- AIによる医療・ヘルスケアの民主化
- LLMコスト低下が中小企業にもたらす競合優位の逆転
- AIリテラシー格差と企業間競争力

条件：
- 番号付きリスト（1. 2. 3.）で出力
- 各投稿：200〜260文字
- ハッシュタグは文末に1〜2個まで
"""
    raw = _call_claude(prompt)
    return _extract_numbered_tweets(raw)
