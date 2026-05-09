"""
X (Twitter) API v2 投稿モジュール
OAuth 1.0a User Context でツイート投稿 + メディアアップロードを行う
"""

import io
import os

import requests
import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _get_api_v1() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def upload_media_from_url(image_url: str) -> int | None:
    """OGP画像URLをダウンロードしてXにアップロードし media_id を返す"""
    try:
        resp = requests.get(
            image_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            return None
        api = _get_api_v1()
        media = api.media_upload(
            filename="ogp_image.jpg",
            file=io.BytesIO(resp.content),
        )
        return media.media_id
    except Exception as e:
        print(f"[メディアアップロード失敗] {e}")
        return None


def post_tweet(text: str, media_ids: list[int] | None = None) -> str | None:
    """ツイートを投稿し tweet_id (str) を返す。失敗時は None"""
    try:
        client = _get_client()
        kwargs: dict = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids
        response = client.create_tweet(**kwargs)
        if response.data:
            return str(response.data["id"])
        return None
    except Exception as e:
        print(f"[投稿失敗] {e}")
        return None
