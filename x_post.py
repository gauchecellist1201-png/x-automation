"""
X (Twitter) API v2 投稿モジュール
tweepy を使ってスレッド・単発ツイートを直接投稿
"""

import os
import time
import tweepy
from typing import Optional


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def post_tweet(text: str) -> Optional[str]:
    """単発ツイートを投稿し tweet_id を返す"""
    client = _get_client()
    response = client.create_tweet(text=text)
    if response.data:
        return str(response.data["id"])
    return None


def post_thread(tweets: list[str]) -> Optional[str]:
    """スレッドを順番に投稿し、先頭ツイートの tweet_id を返す"""
    if not tweets:
        return None

    client = _get_client()
    first_id: Optional[str] = None
    reply_to_id: Optional[str] = None

    for i, text in enumerate(tweets):
        kwargs: dict = {"text": text}
        if reply_to_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_id

        response = client.create_tweet(**kwargs)
        if response.data:
            tweet_id = str(response.data["id"])
            if first_id is None:
                first_id = tweet_id
            reply_to_id = tweet_id

        if i < len(tweets) - 1:
            time.sleep(2)

    return first_id


def tweet_url(tweet_id: str, username: str = "GAUCHE_cellist") -> str:
    return f"https://x.com/{username}/status/{tweet_id}"
