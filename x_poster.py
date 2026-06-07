"""
X (Twitter) API 自動投稿モジュール
tweepy v4 (Twitter API v2) を使用
"""

import os
from typing import Optional

try:
    import tweepy
    _TWEEPY_AVAILABLE = True
except ImportError:
    _TWEEPY_AVAILABLE = False

_REQUIRED_ENV = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]


def is_configured() -> bool:
    return _TWEEPY_AVAILABLE and all(os.environ.get(k) for k in _REQUIRED_ENV)


def post_tweet(text: str) -> Optional[str]:
    """ツイートを投稿してtweet_idを返す（失敗・未設定時はNone）"""
    if not _TWEEPY_AVAILABLE:
        print("[X投稿スキップ] tweepy未インストール")
        return None

    if not all(os.environ.get(k) for k in _REQUIRED_ENV):
        print("[X投稿スキップ] X API認証情報が未設定")
        return None

    try:
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_SECRET"],
        )
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"[X投稿成功] https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None
