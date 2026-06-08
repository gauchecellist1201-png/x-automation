"""X (Twitter) API v2 投稿モジュール"""

import os
from typing import Optional

import tweepy


def post_tweet(text: str) -> Optional[str]:
    """Tweet を投稿してツイートIDを返す。失敗時はNoneを返す。"""
    try:
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_SECRET"],
        )
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"[X投稿完了] tweet_id={tweet_id}")
        return tweet_id
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None
