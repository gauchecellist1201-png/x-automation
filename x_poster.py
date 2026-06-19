"""
X/Twitter API v2 自動投稿モジュール
tweepy を使い OAuth 1.0a で投稿する。画像添付もサポート。
"""

import os
from typing import Optional

import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.environ.get("X_BEARER_TOKEN"),
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def _get_api_v1() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def post_tweet(text: str, media_path: Optional[str] = None) -> Optional[str]:
    """ツイートを投稿し、成功したら tweet_id を返す。失敗時は None。"""
    try:
        media_ids = None
        if media_path:
            api = _get_api_v1()
            media = api.media_upload(filename=media_path)
            media_ids = [media.media_id]

        client = _get_client()
        kwargs: dict = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids

        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        print(f"[X投稿完了] https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None


def search_viral_ai_tweets(max_results: int = 20) -> list[dict]:
    """
    最近バイラルしたAIツイートを検索（Basic tier 以上が必要）。
    API 制限やプランの問題で失敗した場合は空リストを返す。
    """
    try:
        client = _get_client()
        query = "(AI OR 人工知能 OR 生成AI OR ChatGPT OR Claude) lang:ja -is:retweet min_faves:50"
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["public_metrics", "created_at", "text"],
            sort_order="relevancy",
        )
        if not tweets.data:
            return []
        results = [
            {
                "text": t.text,
                "likes": t.public_metrics.get("like_count", 0),
                "retweets": t.public_metrics.get("retweet_count", 0),
                "replies": t.public_metrics.get("reply_count", 0),
            }
            for t in tweets.data
        ]
        return sorted(results, key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)
    except Exception as e:
        print(f"[Twitter検索スキップ] {e}")
        return []


def is_x_configured() -> bool:
    """X API 認証情報がすべて設定されているか確認する。"""
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def build_tweet_url(tweet_id: str, username: str = "") -> str:
    if username:
        return f"https://x.com/{username}/status/{tweet_id}"
    return f"https://x.com/i/web/status/{tweet_id}"
