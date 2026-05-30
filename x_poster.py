"""
X (Twitter) API v2 投稿モジュール
tweepy を使ってツイートの投稿とバズりツイートの取得を行う
"""

import os
import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str) -> str | None:
    """ツイートを投稿してtweet IDを返す。失敗時はNone。"""
    client = _get_client()
    response = client.create_tweet(text=text)
    if response.data:
        return str(response.data["id"])
    return None


def build_tweet_url(tweet_id: str) -> str:
    return f"https://x.com/i/web/status/{tweet_id}"


def fetch_viral_ai_tweets(max_results: int = 10) -> list[str]:
    """
    日本語の最新AIツイートを取得し、バズりパターン分析に活用する。
    APIエラー時は空リストを返してフォールバック。
    """
    client = _get_client()
    try:
        response = client.search_recent_tweets(
            query="生成AI OR ChatGPT OR Claude AI -is:retweet lang:ja",
            max_results=max_results,
            tweet_fields=["public_metrics", "text"],
            sort_order="relevancy",
        )
        if not response.data:
            return []
        tweets = sorted(
            response.data,
            key=lambda t: (t.public_metrics or {}).get("like_count", 0),
            reverse=True,
        )
        return [t.text for t in tweets[:5] if len(t.text) > 20]
    except Exception:
        return []
