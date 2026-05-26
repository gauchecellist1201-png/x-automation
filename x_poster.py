"""
X (Twitter) API v2 を使って自動投稿するモジュール
tweepy v4 (OAuth 1.0a) ベース
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
    """単体ツイートを投稿し、ツイートIDを返す（失敗時はNone）"""
    try:
        client = _get_client()
        response = client.create_tweet(text=text)
        if response.data:
            return str(response.data["id"])
    except Exception as e:
        print(f"[X投稿エラー] {e}")
    return None


def post_thread(tweets: list[str]) -> list[str]:
    """スレッドを順番に投稿し、ツイートIDリストを返す"""
    client = _get_client()
    tweet_ids: list[str] = []
    reply_to: str | None = None

    for text in tweets:
        try:
            if reply_to:
                resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
            else:
                resp = client.create_tweet(text=text)
            if resp.data:
                reply_to = str(resp.data["id"])
                tweet_ids.append(reply_to)
        except Exception as e:
            print(f"[スレッド投稿エラー] {e}")
            break

    return tweet_ids
