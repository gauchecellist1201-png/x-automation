"""
X (Twitter) への自動投稿モジュール
tweepy v4 / X API v2 を使用
"""

import os
import tweepy
from typing import Optional


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str, reply_to_id: Optional[str] = None) -> Optional[str]:
    """単一ツイートを投稿してツイートIDを返す。失敗時はNone。"""
    client = _get_client()
    kwargs: dict = {"text": text}
    if reply_to_id:
        kwargs["in_reply_to_tweet_id"] = reply_to_id
    try:
        response = client.create_tweet(**kwargs)
        if response.data:
            return str(response.data["id"])
    except tweepy.TweepyException as e:
        print(f"[X投稿エラー] {e}")
    return None


def post_thread(posts: list[str]) -> Optional[str]:
    """複数ツイートをスレッドとして投稿。先頭ツイートのIDを返す。"""
    if not posts:
        return None
    first_id = post_tweet(posts[0])
    if not first_id or len(posts) == 1:
        return first_id
    reply_id = first_id
    for text in posts[1:]:
        new_id = post_tweet(text, reply_to_id=reply_id)
        if new_id:
            reply_id = new_id
    return first_id


def tweet_url(tweet_id: str, username: str = "GAUCHE_cellist") -> str:
    return f"https://x.com/{username}/status/{tweet_id}"
