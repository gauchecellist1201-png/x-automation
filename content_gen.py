"""
Claude API を使った戦略的投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
"""

import os
import re
import feedparser
import anthropic

RSS_FEEDS = [
    # Google News AI検索（日本語）
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+医療+ヘルスケア&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Gemini+Claude+2026&hl=ja&gl=JP&ceid=JP:ja",
    # 英語AI/Tech ニュース
    "https://news.google.com/rss/search?q=artificial+intelligence+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+DeepMind+2026&hl=en&gl=US&ceid=US:en",
    # 日本語テックメディア
    "https://feeds.feedburner.com/ledge-ai",
    "https://ainow.ai/feed/",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 3

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家
- 医療×テクノロジーの融合が最大のテーマ
- PHR/EHR×ブロックチェーン・非中央集権的医療データ管理を研究実装中
- スイスの大学での研究経験、国連会議参加などグローバル視点を持つ
- 課題解決志向、押しつけがましくなく静かに鋭い洞察を届けるスタイル
- 読者に「考えさせる問い」を投げかけることを得意とする
"""

VIRAL_PATTERNS = """
## バズるX投稿パターン（実証済み）

### パターン1: 数字で始まる衝撃の事実
「GPT-4は医師国家試験を合格点で通過した。でも免許は持てない。この矛盾が解消される日は近い #AI #医療DX」

### パターン2: 時間軸の対比（変化の可視化）
「2020年：医師が診断。2023年：AIが補助。2026年：AIが先に診断して医師が確認。あなたはこの変化をどう受け止める？ #AI」

### パターン3: 逆説・意外性でフック
「AIで最も置き換えられないのは、実は"専門家"じゃなく"コンテキストを持つ人間"だと気づいた #生成AI」

### パターン4: 業界の不都合な真実
「医療AI導入が最も遅い理由は技術じゃなく規制と利権。技術は10年前から存在している #医療DX」

### パターン5: 問いかけで終わる（RT・リプライ誘発）
「あなたの仕事、5年後にAIが代替すると思う？正直に教えてほしい #AI」

### パターン6: ビジネス層刺さる「知らなかったら損」型
「知らないと損。2026年にAIが変えたビジネスの常識3つ：」でスレッドを始める形式

### パターン7: 感情＋事実の組み合わせ
感情的な問いかけ → 具体的な事実 → 独自の洞察 の3ステップ構成

## 共通原則
- 最初の1行が命（スクロールで止まらせるフック）
- 専門的だが難解すぎない言葉選び
- 具体的な数字・事例・固有名詞を入れると信頼性UP
- 「なぜ？」「どう思う？」で終わるとリプライが増える
- 短い断言文は強い（「〇〇は△△だ」）
"""

TWEET_STRATEGY = """
## 投稿戦略ルール
1. 最初の1行で「止まらせる」フックを必ず入れる
2. ビジネス層（経営者・スタートアップ・専門職）が「シェアしたくなる」内容
3. 医療・社会変革・未来への問いを絡めると尚良い
4. ハッシュタグは #AI #生成AI #医療DX のうち1〜2個まで
5. URLは23文字換算（残り117文字で内容を書く）
6. 「問い」で終わるツイートはRTされやすい
7. スレッド形式の場合は1ツイート目が全て（続きへの誘導）
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_tweets(raw: str) -> list[str]:
    """番号付きリストから投稿文を抽出する（140字超も許容してトリミング）"""
    results = []
    lines = raw.splitlines()
    current = []

    for line in lines:
        stripped = line.strip()
        # 新しい番号付き項目の開始
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current:
                text = " ".join(current).strip()
                results.append(_trim_to_limit(text))
                current = []
            # 番号プレフィックスを除去
            text = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            if text:
                current.append(text)
        elif current and stripped and not stripped.startswith("#"):
            # 前の項目の続き行
            current.append(stripped)

    if current:
        text = " ".join(current).strip()
        results.append(_trim_to_limit(text))

    # 空でなく意味のあるツイートのみ返す
    return [t for t in results if len(t) >= 10][:NUM_CANDIDATES]


def _trim_to_limit(text: str, limit: int = MAX_TWEET_LENGTH) -> str:
    """URLを23文字換算して140文字以内に調整"""
    url_pattern = re.compile(r"https?://\S+")
    urls = url_pattern.findall(text)

    # URL除去した純文字列の長さを計算
    text_without_urls = url_pattern.sub("", text).strip()
    url_char_count = len(urls) * 23
    total = len(text_without_urls) + url_char_count

    if total <= limit:
        return text

    # 超過分だけ末尾をカット（ハッシュタグを保護）
    hashtags = re.findall(r"#\S+", text)
    hashtag_str = " ".join(hashtags)
    main_text = re.sub(r"#\S+", "", text_without_urls).strip()

    available = limit - url_char_count - len(hashtag_str) - (1 if hashtag_str else 0)
    if available > 10:
        trimmed_main = main_text[:available].rstrip()
        parts = [p for p in [trimmed_main, hashtag_str] if p]
        url_part = " ".join(urls)
        parts_with_url = parts + ([url_part] if url_part else [])
        return " ".join(parts_with_url)
    return text[:limit]


def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    """Note記事 + 過去実績 (few-shot) から戦略的投稿案を生成"""
    few_shot_section = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot_section = f"\n## 過去に反応が良かった投稿（この文体・温度感を参考に）\n{examples}\n"

    link_instruction = f"\n- 文末にNoteリンクを入れること: {note_url}" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
以下のNote記事を読み、ビジネス層・医療従事者・スタートアップ関係者に刺さるX投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 番号付きリスト（1. 2. 3.）で各案を出力
- 各案は140文字以内（URLは23文字換算）{link_instruction}
- それぞれ異なるバズパターンを使うこと
{few_shot_section}
## Note記事本文
{note_text[:4000]}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def fetch_rss_headlines(max_items: int = 10) -> list[dict]:
    """RSSから見出しとリンクを取得"""
    items: list[dict] = []
    seen_titles: set[str] = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and len(title) > 10 and title not in seen_titles:
                    seen_titles.add(title)
                    items.append({"title": title, "link": link})
        except Exception:
            continue

    return items[:max_items]


def generate_posts_from_rss() -> list[str]:
    """最新AIトレンドニュースを元に、@GAUCHE_cellist らしい意見投稿を生成"""
    items = fetch_rss_headlines()
    if not items:
        return _generate_original_ai_insight()

    headlines_text = "\n".join(f"- {it['title']}" for it in items)

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
以下の最新AIニュースから最も注目すべきトピックを選び、
ビジネス層・医療従事者・スタートアップ関係者にバズる投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 番号付きリスト（1. 2. 3.）で各案を出力
- 各案は140文字以内
- それぞれ異なるバズパターンを使うこと（パターン番号を案の頭に書かなくていい）
- 医療×AI、社会変革、ビジネス変革の視点を絡めると尚良い

## 今日の最新AIニュース（{len(items)}件）
{headlines_text}
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)


def generate_posts_from_rss_with_thread() -> tuple[list[str], str]:
    """スレッド形式の投稿（フック+本文）を生成して返す"""
    items = fetch_rss_headlines()
    headlines_text = "\n".join(f"- {it['title']}" for it in items) if items else "（ニュース取得失敗）"

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
以下のAIニュースから最も重要なトピックを1つ選び、スレッド形式の投稿セットを作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}

出力形式（必ずこの形式で）:
【フック】（140文字以内・これだけで止まらせる1文）
{(chr(10) + '【本文1】（続きの詳細、140文字以内）' + chr(10) + '【本文2】（まとめ・CTA、140文字以内）')}

## 今日の最新AIニュース
{headlines_text}
"""
    raw = _call_claude(prompt)

    hook = ""
    thread_body = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("【フック】"):
            hook = s.replace("【フック】", "").strip()
        elif s.startswith("【本文"):
            body = re.sub(r"^【本文\d+】", "", s).strip()
            if body:
                thread_body.append(body)

    return thread_body, hook


def _generate_original_ai_insight() -> list[str]:
    """RSSが取得できない場合のオリジナル洞察ツイート生成"""
    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の戦略的投稿担当AIです。
2026年のAI業界で最も重要なトピックについて、
ビジネス層・医療従事者に刺さるバズ投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}
{VIRAL_PATTERNS}
{TWEET_STRATEGY}

出力ルール:
- 番号付きリスト（1. 2. 3.）で各案を出力
- 各案は140文字以内
- Claude・GPT・Gemini・医療AI・AIと社会変革などのテーマを優先
- それぞれ異なるバズパターンを使うこと
"""
    raw = _call_claude(prompt)
    return _extract_tweets(raw)
