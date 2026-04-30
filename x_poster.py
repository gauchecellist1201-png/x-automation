"""
X (Twitter) API v2 自動投稿モジュール
tweepy v4 を使用
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
    """ツイートを投稿し、tweet_id を返す。失敗時は None"""
    client = _get_client()
    response = client.create_tweet(text=text)
    if response.data:
        return str(response.data["id"])
    return None


def post_thread(tweets: list[str]) -> list[str]:
    """スレッドとして複数ツイートを連投し、tweet_id リストを返す"""
    client = _get_client()
    ids: list[str] = []
    reply_to: str | None = None

    for text in tweets:
        kwargs: dict = {"text": text}
        if reply_to:
            kwargs["reply"] = {"in_reply_to_tweet_id": reply_to}
        response = client.create_tweet(**kwargs)
        if response.data:
            tweet_id = str(response.data["id"])
            ids.append(tweet_id)
            reply_to = tweet_id
        else:
            break

    return ids


def tweet_url(tweet_id: str, username: str = "GAUCHE_cellist") -> str:
    return f"https://x.com/{username}/status/{tweet_id}"
