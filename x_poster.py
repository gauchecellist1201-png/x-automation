"""
X (Twitter) API v2 投稿モジュール
Tweepy v4 を使ってツイート・スレッドを自動投稿する
"""

import os
import tweepy


X_USERNAME = "GAUCHE_cellist"


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str) -> str | None:
    """単体ツイートを投稿してtweetIDを返す。失敗時はNone。"""
    try:
        client = _get_client()
        response = client.create_tweet(text=text)
        return str(response.data["id"])
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None


def post_thread(tweets: list[str]) -> str | None:
    """スレッドを投稿して先頭ツイートのIDを返す。失敗時はNone。"""
    if not tweets:
        return None
    try:
        client = _get_client()
        first_id: str | None = None
        reply_to: str | None = None
        for text in tweets:
            kwargs: dict = {"text": text}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to
            response = client.create_tweet(**kwargs)
            tweet_id = str(response.data["id"])
            if first_id is None:
                first_id = tweet_id
            reply_to = tweet_id
        return first_id
    except Exception as e:
        print(f"[Xスレッド投稿エラー] {e}")
        return None


def tweet_url(tweet_id: str) -> str:
    return f"https://x.com/{X_USERNAME}/status/{tweet_id}"


def is_configured() -> bool:
    keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in keys)
