"""
X (Twitter) API v2 を使った直接投稿モジュール
"""
import os
import tweepy


def has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def post_tweet(text: str) -> str | None:
    """ツイートを投稿し、成功したらツイートIDを返す。失敗したらNone。"""
    if not has_x_credentials():
        print("[X] API認証情報未設定。LINEのみ通知します。")
        return None
    try:
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_SECRET"],
        )
        response = client.create_tweet(text=text)
        if response.data:
            tweet_id = str(response.data["id"])
            print(f"[X投稿成功] https://x.com/i/web/status/{tweet_id}")
            return tweet_id
        return None
    except tweepy.TweepyException as e:
        print(f"[X投稿失敗] {e}")
        return None
