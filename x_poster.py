"""
X (Twitter) API v2 自動投稿モジュール
tweepy を使った投稿・メディアアップロード対応
"""

import os
import tweepy

ACCOUNT_HANDLE = "GAUCHE_cellist"


def _create_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def post_tweet(text: str) -> str | None:
    """ツイートを投稿し、ツイートIDを返す。失敗時はNone。"""
    client = _create_client()
    try:
        response = client.create_tweet(text=text)
        if response.data:
            tweet_id = str(response.data["id"])
            print(f"[X投稿成功] ID: {tweet_id}")
            return tweet_id
    except tweepy.TweepyException as e:
        print(f"[X投稿エラー] {e}")
    return None


def get_tweet_url(tweet_id: str) -> str:
    return f"https://x.com/{ACCOUNT_HANDLE}/status/{tweet_id}"


def x_credentials_available() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)
