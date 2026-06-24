"""
X (Twitter) API v2 を使って投稿するモジュール
tweepy v4 使用 / 画像添付対応
"""

import io
import os
from typing import Optional

import tweepy


def _v2_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _v1_api() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def upload_image(image_bytes: bytes, filename: str = "ogp.jpg") -> Optional[int]:
    """OGP画像をXのメディアAPIにアップロードしてmedia_idを返す"""
    try:
        api = _v1_api()
        media = api.media_upload(filename=filename, file=io.BytesIO(image_bytes))
        return media.media_id
    except tweepy.TweepyException as e:
        print(f"[画像アップロードエラー] {e}")
        return None


def post_tweet(text: str, media_id: Optional[int] = None) -> Optional[str]:
    """ツイートを投稿し、成功時はツイートIDを返す"""
    client = _v2_client()
    try:
        kwargs: dict = {"text": text}
        if media_id:
            kwargs["media_ids"] = [str(media_id)]
        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        print(f"[X投稿成功] https://x.com/GAUCHE_cellist/status/{tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        print(f"[X投稿エラー] {e}")
        return None
