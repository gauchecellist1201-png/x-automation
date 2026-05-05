"""
X (Twitter) API v2 投稿モジュール
tweepy を使った OAuth 1.0a 認証での自動投稿
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client():
    import tweepy
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )


def _get_v1_api():
    """メディアアップロード用のv1.1 API"""
    import tweepy
    auth = tweepy.OAuth1UserHandler(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"],
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )
    return tweepy.API(auth)


def post_tweet(text: str, image_path: str | None = None) -> dict:
    """
    Xにツイートを投稿する。
    Returns: {"id": str, "text": str, "url": str}
    Raises: Exception on failure
    """
    client = _get_client()

    if image_path and Path(image_path).exists():
        api = _get_v1_api()
        media = api.media_upload(filename=image_path)
        response = client.create_tweet(text=text, media_ids=[media.media_id_string])
    else:
        response = client.create_tweet(text=text)

    tweet_id = response.data["id"]
    return {
        "id": tweet_id,
        "text": text,
        "url": f"https://x.com/GAUCHE_cellist/status/{tweet_id}",
    }


def is_x_api_configured() -> bool:
    """X API環境変数が設定されているか確認"""
    required = [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ]
    return all(os.environ.get(k) for k in required)
