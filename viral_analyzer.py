"""
X API v2 を使ってバズっているAI関連ツイートを分析するモジュール
エンゲージメントの高いツイートを取得し、Claude の生成プロンプトへの参考例として渡す
"""

import os
import requests
from dataclasses import dataclass

# ビジネス層向けに絞ったクエリ
SEARCH_QUERIES = [
    '(AI OR 生成AI OR ChatGPT OR Claude OR LLM OR "人工知能") (ビジネス OR 活用 OR DX OR 生産性 OR 経営) lang:ja -is:retweet -is:reply min_faves:30',
    '(AI OR "artificial intelligence" OR ChatGPT OR LLM) (business OR productivity OR ROI OR enterprise) lang:en -is:retweet -is:reply min_faves:100',
]


@dataclass
class ViralTweet:
    text: str
    likes: int
    retweets: int
    replies: int
    engagement_score: int


def _search_tweets(query: str, bearer_token: str, max_results: int = 20) -> list[ViralTweet]:
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "public_metrics,text",
        "sort_order": "relevancy",
    }
    try:
        r = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            headers=headers,
            params=params,
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[viral_analyzer] search failed: {r.status_code}")
            return []
        data = r.json().get("data", [])
    except Exception as e:
        print(f"[viral_analyzer] exception: {e}")
        return []

    result = []
    for t in data:
        m = t.get("public_metrics", {})
        likes = m.get("like_count", 0)
        rts = m.get("retweet_count", 0)
        replies = m.get("reply_count", 0)
        bookmarks = m.get("bookmark_count", 0)
        # リツイートを最重視（拡散力の指標）
        score = likes * 2 + rts * 5 + replies + bookmarks * 3
        result.append(ViralTweet(
            text=t.get("text", ""),
            likes=likes,
            retweets=rts,
            replies=replies,
            engagement_score=score,
        ))
    return sorted(result, key=lambda x: x.engagement_score, reverse=True)


def get_viral_ai_tweets(bearer_token: str = "") -> list[ViralTweet]:
    """バズっているAIツイートを取得してエンゲージメント順で返す"""
    if not bearer_token:
        bearer_token = os.environ.get("X_BEARER_TOKEN", "")
    if not bearer_token:
        return []

    all_tweets: list[ViralTweet] = []
    for query in SEARCH_QUERIES:
        all_tweets.extend(_search_tweets(query, bearer_token))

    # 重複（先頭50文字一致）を除去
    seen: set[str] = set()
    unique: list[ViralTweet] = []
    for t in sorted(all_tweets, key=lambda x: x.engagement_score, reverse=True):
        key = t.text[:50]
        if key not in seen and len(t.text) > 20:
            seen.add(key)
            unique.append(t)

    return unique[:8]
