"""
X (Twitter) API v2 投稿モジュール
tweepy を使って実際にXへ投稿する
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
    """ツイートを投稿し tweet ID を返す。失敗時は None。"""
    try:
        client = _get_client()
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"[X投稿成功] https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except tweepy.errors.Forbidden as e:
        print(f"[X投稿エラー] 権限不足 (API v2 書き込み権限を確認): {e}")
        return None
    except tweepy.errors.TooManyRequests:
        print("[X投稿エラー] レート制限に達しました。時間をおいて再試行してください。")
        return None
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None
