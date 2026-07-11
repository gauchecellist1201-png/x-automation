"""
X (Twitter) API v2 を使って投稿するモジュール
"""

import os
import tweepy


def get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str) -> str | None:
    """投稿してツイートIDを返す。失敗時はNone。"""
    client = get_client()
    response = client.create_tweet(text=text)
    tweet_id = str(response.data["id"])
    return tweet_id
