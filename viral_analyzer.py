"""
バイラルツイートパターン分析・ビジネスAIトレンドニュース取得モジュール
"""

import feedparser
from dataclasses import dataclass

BUSINESS_AI_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+ビジネス+企業+活用&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=生成AI+業務効率化+導入事例&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=ChatGPT+Claude+Gemini+企業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+経営+DX+自動化+投資&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+business+enterprise+productivity&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=LLM+AGI+AI+agent+2026&hl=en&gl=US&ceid=US:en",
]

# バイラルツイートの6つの黄金パターン
# 出典: X上でエンゲージメント上位のビジネス系AI投稿分析より
VIRAL_TWEET_PATTERNS = [
    {
        "id": "shock_stat",
        "name": "衝撃数字",
        "desc": "具体的な統計・数字で驚かせる（冒頭に数字を置く）",
        "engagement": "驚き・いいね・シェア",
        "image_hint": "📊 統計グラフ or インフォグラフィック",
        "example": "ChatGPTが3ヶ月で1億ユーザー。Netflixは10年かかった。AI普及の速さは全産業の前提を変えている。 #AI",
    },
    {
        "id": "contrarian",
        "name": "逆説洞察",
        "desc": "常識を覆す反直感的な真実（「実は〇〇じゃない」）",
        "engagement": "引用RT・議論・リプライ爆増",
        "image_hint": "💡 従来の認識 vs 実態の比較図",
        "example": "AIに仕事を奪われる、は半分間違い。正確には「AIを使いこなせる人に仕事が集まる」。競争相手はAIじゃなく、AIを使う人間。 #生成AI",
    },
    {
        "id": "prediction",
        "name": "大胆予測",
        "desc": "具体的な年数・シナリオで未来を断言する",
        "engagement": "ブックマーク・議論・引用RT",
        "image_hint": "🔮 タイムライン図 or 未来シナリオ図",
        "example": "2027年、会議の議事録を手動で取る企業は競争力を失う。今AIを使わない選択は電卓より算盤を選ぶのと同じ。 #AI",
    },
    {
        "id": "practical_tip",
        "name": "実践ノウハウ",
        "desc": "今日から使える具体的なAI活用術・時短術",
        "engagement": "保存・引用・シェア（役立つ系）",
        "image_hint": "📝 ステップ図 or チェックリスト",
        "example": "週報作成をAIに任せた→所要時間90%減、質は向上。コツはアウトラインだけ自分で書いてAIに肉付けさせること。 #生成AI",
    },
    {
        "id": "question",
        "name": "問いかけ",
        "desc": "読者を引き込む問いで締める（返信・議論を誘発）",
        "engagement": "リプライ・エンゲージメント急増",
        "image_hint": "❓ シンプルな質問カード（白背景 + 大文字テキスト）",
        "example": "あなたの会社でAIを日常的に使っている人は何%ですか？その数字が3年後の競争力を決める気がしています。 #AI",
    },
    {
        "id": "thread_hook",
        "name": "スレッドフック",
        "desc": "続きを読ませるスレッド冒頭ツイート（🧵で始める）",
        "engagement": "クリック・フォロー・エンゲージメント総合",
        "image_hint": "🎯 内容を一言で表すアイキャッチ画像",
        "example": "AIで営業コストを60%削減した会社の話を聞いた。やってることがシンプルすぎて怖かった🧵（5つにまとめます）",
    },
]


@dataclass
class TrendingTopic:
    title: str
    url: str
    source: str
    relevance_score: float = 1.0


def fetch_trending_ai_news(max_items: int = 10) -> list[TrendingTopic]:
    """最新ビジネスAIニュースを取得し、ビジネス関連度でスコアリングして返す"""
    topics: list[TrendingTopic] = []
    seen: set[str] = set()

    BUSINESS_KEYWORDS = [
        "企業", "経営", "ビジネス", "業務", "効率", "導入", "活用",
        "生産性", "コスト", "売上", "自動化", "DX", "戦略", "投資", "競争",
        "business", "enterprise", "productivity", "revenue", "ROI", "workforce",
        "cost", "efficiency", "strategy", "investment",
    ]

    for feed_url in BUSINESS_AI_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                source = feed.feed.get("title", "AI News")

                if not title or title in seen or len(title) < 10:
                    continue

                score = 1.0
                title_lower = title.lower()
                for kw in BUSINESS_KEYWORDS:
                    if kw in title_lower:
                        score += 0.3

                seen.add(title)
                topics.append(TrendingTopic(
                    title=title,
                    url=url,
                    source=source,
                    relevance_score=score,
                ))
        except Exception:
            continue

    topics.sort(key=lambda t: t.relevance_score, reverse=True)
    return topics[:max_items]


def format_patterns_for_prompt(pattern_ids: list[str]) -> str:
    """選択したパターンをプロンプト用テキストに変換"""
    selected = [p for p in VIRAL_TWEET_PATTERNS if p["id"] in pattern_ids]
    lines = []
    for i, p in enumerate(selected, 1):
        lines.append(f"{i}. 【{p['name']}】 {p['desc']}")
        lines.append(f"   参考例: {p['example']}")
    return "\n".join(lines)
