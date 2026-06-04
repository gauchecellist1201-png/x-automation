"""
X (Twitter) API v2 経由で投稿するモジュール
"""

import os
import tweepy


def post_to_x(text: str) -> str | None:
    """X APIを使って投稿。成功したらツイートIDを返す。失敗時はNone。"""
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    try:
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"✅ X投稿成功: ID={tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        print(f"❌ X投稿エラー: {e}")
        return None
