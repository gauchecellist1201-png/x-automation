"""
トレンドAIトピック分析モジュール
バズりやすいX投稿のパターンを分析し、投稿戦略に活かす
"""

import os
import re
import feedparser
import anthropic

TREND_RSS_SOURCES = [
    # 英語トレンド（グローバル最前線）
    "https://news.google.com/rss/search?q=AI+AGI+breakthrough+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+Anthropic+Google+DeepMind+2026&hl=en&gl=US&ceid=US:en",
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    # 日本語ビジネス
    "https://news.google.com/rss/search?q=AI+経営+ビジネス+2026&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+活用事例+業務効率&hl=ja&gl=JP&ceid=JP:ja",
]

# バズりやすいツイートパターン（日本語ビジネス層向け）
VIRAL_PATTERNS = {
    "shock_fact": "【衝撃】〇〇が〇〇に。これが意味することは──",
    "number_impact": "〇〇を知らないと損する「3つの変化」",
    "question_hook": "なぜ〇〇は〇〇を選ばないのか。",
    "paradox": "AIは〇〇しない。ただし──",
    "conclusion_first": "結論: 〇〇。理由は3つある──",
    "before_after": "1年前: 〇〇 / 今: 〇〇 / 来年: ？",
    "confession": "正直に言う。〇〇は〇〇だった。",
    "warning": "〇〇経営者は今すぐ知るべきこと──",
}

BUSINESS_ANGLES = [
    "コスト削減・ROI",
    "競合優位性",
    "人材・採用への影響",
    "医療・ヘルスケア変革",
    "意思決定の高速化",
    "リスクと倫理",
    "グローバル競争",
    "実装事例・成功例",
]


def fetch_trend_headlines(max_items: int = 15) -> list[dict]:
    """トレンドニュースを幅広く収集"""
    items: list[dict] = []
    seen: set[str] = set()

    for url in TREND_RSS_SOURCES:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()
                published = entry.get("published", "").strip()

                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    items.append({
                        "title": title,
                        "link": link,
                        "summary": summary[:200] if summary else "",
                        "published": published,
                    })
        except Exception:
            continue
        if len(items) >= max_items:
            break

    return items[:max_items]


def analyze_hot_topic(headlines: list[dict]) -> dict:
    """Claudeを使って最もホットなトピックを分析・選定"""
    if not headlines:
        return {"topic": "2026年のAI業界トレンド", "angle": "総合", "reason": "デフォルト"}

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    headlines_text = "\n".join(
        f"{i+1}. {item['title']}" + (f"\n   概要: {item['summary']}" if item.get("summary") else "")
        for i, item in enumerate(headlines[:12])
    )

    prompt = f"""以下の最新AIニュース一覧から、日本のビジネス層・経営者が最も関心を持つであろう
「今日のホットトピック」を1つ選び、JSON形式で回答してください。

ニュース一覧:
{headlines_text}

ビジネス層が関心を持つ観点:
{chr(10).join(f'- {a}' for a in BUSINESS_ANGLES)}

出力形式（JSONのみ、他のテキスト不要）:
{{
  "selected_index": <1始まりの番号>,
  "topic": "<選んだトピックの日本語要約（30文字以内）>",
  "angle": "<ビジネス観点（上記リストから1つ）>",
  "why_viral": "<なぜこれがバズりやすいか（50文字以内）>",
  "key_fact": "<投稿に使える核心的な事実・数字・変化（60文字以内）>"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # JSON抽出
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        import json
        try:
            result = json.loads(json_match.group())
            # 対応するニュースのリンクを付与
            idx = result.get("selected_index", 1) - 1
            if 0 <= idx < len(headlines):
                result["source_title"] = headlines[idx]["title"]
                result["source_link"] = headlines[idx]["link"]
            return result
        except Exception:
            pass

    return {
        "topic": "最新AI動向",
        "angle": "総合",
        "why_viral": "常に注目度が高い",
        "key_fact": "",
        "source_title": headlines[0]["title"] if headlines else "",
        "source_link": headlines[0]["link"] if headlines else "",
    }


def suggest_viral_format(topic_analysis: dict) -> str:
    """トピック分析に基づいて最適な投稿フォーマットを提案"""
    angle = topic_analysis.get("angle", "")

    if "コスト" in angle or "ROI" in angle:
        return "number_impact"
    elif "リスク" in angle or "倫理" in angle:
        return "warning"
    elif "競合" in angle or "グローバル" in angle:
        return "before_after"
    elif "医療" in angle:
        return "question_hook"
    else:
        return "shock_fact"


def get_today_strategy() -> dict:
    """今日の投稿戦略を返す（トレンド分析 + フォーマット提案）"""
    headlines = fetch_trend_headlines()
    analysis = analyze_hot_topic(headlines)
    format_key = suggest_viral_format(analysis)

    return {
        "analysis": analysis,
        "recommended_format": format_key,
        "format_template": VIRAL_PATTERNS.get(format_key, ""),
        "all_headlines": headlines,
    }
