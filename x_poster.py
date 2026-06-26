"""
X (Twitter) API v2 投稿モジュール
tweepy OAuth 1.0a を使用してツイートを送信する
"""

import os
import re
import requests
import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str) -> str | None:
    """ツイートを投稿し、tweet_id を返す。失敗時は None を返す。"""
    try:
        client = _get_client()
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        print(f"[X投稿成功] tweet_id={tweet_id}")
        return str(tweet_id)
    except tweepy.TweepyException as e:
        print(f"[X投稿失敗] {e}")
        return None


def build_tweet_url(tweet_id: str, username: str = "GAUCHE_cellist") -> str:
    return f"https://x.com/{username}/status/{tweet_id}"
