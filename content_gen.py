"""
Claude API を使った戦略的バズり投稿文生成モジュール
対象アカウント: @GAUCHE_cellist（井出直毅）
ターゲット: ビジネス層・経営者・AI関心層
"""

import os
import re
import feedparser
import anthropic
from datetime import date
from pathlib import Path

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+人工知能+Claude+OpenAI&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+LLM+大規模言語モデル+ビジネス&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+経営+DX+自動化+効率化&hl=ja&gl=JP&ceid=JP:ja",
    "https://feeds.feedburner.com/ledge-ai",
]

MAX_TWEET_LENGTH = 140
NUM_CANDIDATES = 5

AUTHOR_PROFILE = """
## 著者プロフィール：井出直毅 (@GAUCHE_cellist)
- 医学生 × AI/ブロックチェーン起業家（次世代医療テック）
- 医療×AI×ブロックチェーンの交差点で価値創出中
- スイス大学での研究・国連会議登壇などグローバル視点
- PHR/EHRブロックチェーン活用を実装・研究中
- Claude Code等の最新AIツールを日常的に活用
- 「静かに鋭い洞察を届ける」スタイル
- 押しつけがましくなく、読者に考えさせる問いを投げかける
- ターゲット読者: 経営者・スタートアップ創業者・AI関心層・医療従事者
"""

# 7種類のバズりフォーマット（曜日別ローテーション）
BUZZ_FORMATS = {
    "shocking_stat": {
        "name": "衝撃スタッツ系",
        "instruction": """
冒頭に具体的な数字・データを入れ、その意味するビジネスインパクトを述べる。
数値は必ず入れること（〇%、〇倍、〇ヶ月、〇人など）。
最後は「自分ごと」に感じられる洞察か問いで締める。
NG: 「すごい」「驚き」など感情ワードの多用
OK: データ→意味→洞察の3段構成
例: 「日本企業のAI導入率はまだ28%。先進国最下位水準。
でも視点を変えると、今動けば残り72%より先行できる。
遅れではなく、チャンスとして見る企業が次の10年を作る。」
""",
    },
    "future_prediction": {
        "name": "未来予測系",
        "instruction": """
3〜5年後の具体的な未来像を断定的に描き、今すぐ動く理由を示す。
「〇〇する人/企業」vs「しない人/企業」の対比が効果的。
恐怖よりも機会・希望の文脈で語ると経営者層に刺さる。
例: 「3年後、AIを使いこなす医師と使わない医師では
診断精度に明確な差が生まれる。
問題は技術ではなく、学ぼうとする意志だ。
医学生の今、その差を縮めに行く。」
""",
    },
    "contrarian": {
        "name": "反常識系",
        "instruction": """
「実は〇〇」「逆に〇〇」「誤解されているが〇〇」という反常識から始める。
多くの人が信じている思い込みを一文で否定し、正しい理解を示す。
「なるほど」と思わせ、シェアしたくなる内容にする。
例: 「『AIに仕事を奪われる』は間違い。
正確には『AIを使う人に仕事が移る』。
この違いを理解しているかで、5年後が全く変わる。 #AI」
""",
    },
    "practical_tips": {
        "name": "実用Tips系",
        "instruction": """
今すぐ試せるAI活用法を①②③のリスト形式で提示する（3〜4個）。
各項目は具体的・短く。時短効果を数値で示すとなお良い。
最後に「今週から変わる」「明日から使える」などの実現可能感で締める。
改行を使ってリスト形式にしてよい（合計で140文字以内）。
例: 「経営者がClaudeで時間を取り戻す3つの使い方
①議事録→要点/アクション抽出（30分→3分）
②企画書の初稿（3h→30分）
③競合リサーチ（半日→20分）
ツールではなく習慣にした人が変わる。 #AI活用」
""",
    },
    "philosophical": {
        "name": "哲学的問いかけ系",
        "instruction": """
AIと人間の本質的な問いを2〜3文で鋭く投げかける。
「〇〇とは何か」「〇〇に価値はあるか」で終わると拡散されやすい。
医療・創造性・仕事の意味など普遍的テーマを絡める。
答えを出さず、読者が考えたくなる問いを立てることが大事。
例: 「AIが全ての診断を出せるようになった時、
医師の『経験と勘』に値段はつくか。
技術の進歩は、人間の価値を問い直す哲学だ。 #医療AI」
""",
    },
    "news_reaction": {
        "name": "ニュース鋭評系",
        "instruction": """
最新ニュースを受けて、表面的な事実ではなく
ビジネス・産業・医療への具体的インパクトを鋭く指摘する。
「これが意味するのは〇〇」「多くの人が見ていないのは〇〇」という視点。
ニュース名は出さず、自分の洞察として語る（読者が追体験できるように）。
例: 「新AIモデルのニュースより重要なこと。
企業が『AI導入を検討』している間に、競合は意思決定速度を3倍にした。
ツールの性能差より、使う人の覚悟の差のほうが、ずっと大きい。」
""",
    },
    "personal_insight": {
        "name": "体験・洞察系",
        "instruction": """
「〇〇をやってみたら〇〇だった」という具体的な一人称体験から始め、
そこから得た洞察・教訓を語る。
医療×AIの実体験があると説得力が増す。「私も試したい」と思わせること。
嘘や誇張はNG。リアルな体験談として書く。
例: 「Claude Codeに医療論文50本の要約を頼んだら
3時間が15分になった。
浮いた時間で患者と向き合える。
AIは仕事を奪うのではなく、本来やるべき仕事に集中させてくれる。」
""",
    },
}

WEEKLY_THEMES = [
    ("future_prediction", "月: AI×ビジネス未来予測"),
    ("practical_tips",    "火: 今すぐ使えるAI実践"),
    ("contrarian",        "水: AI常識を疑う視点"),
    ("shocking_stat",     "木: AIの衝撃データ"),
    ("philosophical",     "金: AI×社会の本質的問い"),
    ("news_reaction",     "土: 最新AIニュース鋭評"),
    ("personal_insight",  "日: AI活用体験シェア"),
]

AI_BUSINESS_CONTEXT_FILE = Path("data/ai_business_context.md")


def _call_claude(prompt: str, max_tokens: int = 1500) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def get_today_format() -> tuple[str, str]:
    """今日の曜日に基づいてバズりフォーマットを返す (format_key, theme_label)"""
    weekday = date.today().weekday()  # 0=月曜日
    return WEEKLY_THEMES[weekday]


def _extract_tweets(raw: str) -> list[str]:
    """===区切りまたは番号付きリストから投稿文を抽出し140文字以内に絞る"""
    tweets = []

    # ===区切り形式（優先）
    if raw.count("===") >= 2:
        parts = [p.strip() for p in raw.split("===") if p.strip()]
        for p in parts:
            # 【案N】や番号プレフィックスを除去
            clean = re.sub(r"^【?[案\d]+[】\.\)：:]\s*", "", p).strip()
            clean = re.sub(r"^\*{1,2}[^*]+\*{1,2}\s*\n?", "", clean).strip()
            if 10 <= len(clean) <= MAX_TWEET_LENGTH:
                tweets.append(clean)

    # フォールバック: 番号付きリスト（複数行対応）
    if not tweets:
        lines = raw.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if re.match(r"^\d+[\.\)]", line):
                tweet = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
                # 連続する非番号行を結合（リスト型投稿の改行対応）
                while (
                    i + 1 < len(lines)
                    and lines[i + 1].strip()
                    and not re.match(r"^\d+[\.\)]", lines[i + 1].strip())
                    and not lines[i + 1].strip().startswith("===")
                ):
                    i += 1
                    tweet += "\n" + lines[i].strip()
                if 10 <= len(tweet) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet)
            i += 1

    return tweets


def fetch_rss_headlines(max_items: int = 12) -> list[str]:
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
    return list(dict.fromkeys(headlines))[:18]


def _load_business_context() -> str:
    if AI_BUSINESS_CONTEXT_FILE.exists():
        return AI_BUSINESS_CONTEXT_FILE.read_text(encoding="utf-8")
    return ""


def generate_viral_posts(
    format_key: str = "",
    note_text: str = "",
    feedback_text: str = "",
    note_url: str = "",
) -> tuple[list[str], str]:
    """
    バズり投稿を生成して (投稿リスト, テーマラベル) を返す。
    format_keyが空の場合、今日の曜日に基づいて自動選択。
    note_textが空の場合、RSSニュースをソースとする。
    """
    if not format_key or format_key not in BUZZ_FORMATS:
        format_key, theme_label = get_today_format()
    else:
        theme_label = BUZZ_FORMATS[format_key]["name"]

    fmt = BUZZ_FORMATS[format_key]
    business_context = _load_business_context()

    # few-shot例の準備
    few_shot = ""
    if feedback_text.strip():
        examples = "\n".join(
            line for line in feedback_text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        if examples:
            few_shot = f"\n## 過去に反応が良かった投稿（文体・温度感の参考）\n{examples}\n"

    # ソースコンテンツの準備
    source_section = ""
    source_label = "AIニュース"
    if note_text.strip():
        link_hint = f"（文末にNoteリンクを入れてもよい: {note_url}）" if note_url else ""
        source_section = f"\n## 参考記事{link_hint}\n{note_text[:3000]}\n"
        source_label = "Note記事"
    else:
        headlines = fetch_rss_headlines()
        if headlines:
            headlines_text = "\n".join(f"- {h}" for h in headlines)
            source_section = (
                f"\n## 今日の最新AIニュース（最も注目すべきトピックを1〜2個選んで活用）\n"
                f"{headlines_text}\n"
            )

    context_section = ""
    if business_context:
        context_section = f"\n## 2026年AIビジネス動向（参考知識）\n{business_context[:2000]}\n"

    url_note = "\n- URLを含む場合、URLは23文字として換算してください" if note_url else ""

    prompt = f"""あなたはXアカウント @GAUCHE_cellist（井出直毅）の投稿担当AIです。
ビジネス層・経営者・AI関心層に刺さる、バズりやすい投稿を{NUM_CANDIDATES}案作成してください。

{AUTHOR_PROFILE}

## 今日のバズりフォーマット: 【{fmt['name']}】
{fmt['instruction']}

## 投稿の共通ルール
- 各投稿は140文字以内（改行・スペースも含む合計文字数）{url_note}
- ハッシュタグは0〜2個（多すぎるとスパム感が出る、なくてもよい）
- 「専門的だが難解すぎない」言葉選び
- AIがビジネスに与える実際のインパクトを軸に
- 医療・社会変革・未来への視点を絡めると尚良い
- 押しつけがましくなく、読者に考えさせる内容
- 結論より「問い」や「洞察」で終わるとRTされやすい
- 冒頭1〜2文で勝負が決まる。最初の一文を特に磨くこと

## 出力フォーマット（厳守）
各投稿案を「===」で区切って出力してください。番号やラベルは不要です。
===
（投稿案1の本文のみ、140文字以内）
===
（投稿案2の本文のみ、140文字以内）
===
（{NUM_CANDIDATES}案分）
{few_shot}{context_section}{source_section}"""

    raw = _call_claude(prompt)
    posts = _extract_tweets(raw)

    # 候補が3件未満なら補完生成
    if len(posts) < 3:
        posts.extend(_generate_fallback_posts(format_key, business_context))

    return posts[:NUM_CANDIDATES], theme_label


def _generate_fallback_posts(format_key: str, business_context: str = "") -> list[str]:
    """候補が不足した場合の補完生成"""
    fmt = BUZZ_FORMATS.get(format_key, BUZZ_FORMATS["future_prediction"])
    ctx = f"\n## 参考知識\n{business_context[:1000]}" if business_context else ""

    prompt = f"""@GAUCHE_cellist（医学生×AI起業家）として、
2026年の最新AIトレンドについて「{fmt['name']}」スタイルで
140文字以内のX投稿を3案作成してください。

{fmt['instruction']}

===区切りで出力（本文のみ）:
===
[投稿1]
===
[投稿2]
===
[投稿3]
==={ctx}"""

    raw = _call_claude(prompt)
    return _extract_tweets(raw)


# 後方互換性のために旧関数を残す
def generate_posts_from_notes(note_text: str, feedback_text: str, note_url: str = "") -> list[str]:
    posts, _ = generate_viral_posts(
        note_text=note_text,
        feedback_text=feedback_text,
        note_url=note_url,
    )
    return posts


def generate_posts_from_rss() -> list[str]:
    posts, _ = generate_viral_posts()
    return posts
