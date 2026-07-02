"""
X (Twitter) API v2 自動投稿モジュール
tweepy を使用して OAuth 1.0a で認証・投稿
"""

import os
import tweepy


def get_x_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_tweet(text: str) -> str | None:
    """Xに投稿し、成功時は tweet_id を返す。失敗時は None。"""
    client = get_x_client()
    try:
        response = client.create_tweet(text=text)
        tweet_id = response.data.get("id") if response.data else None
        return str(tweet_id) if tweet_id else None
    except tweepy.TweepyException as e:
        print(f"[X投稿エラー] {e}")
        return None


def build_tweet_url(tweet_id: str, username: str = "GAUCHE_cellist") -> str:
    return f"https://x.com/{username}/status/{tweet_id}"
