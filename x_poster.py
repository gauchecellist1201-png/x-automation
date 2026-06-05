"""
X (Twitter) API v2 投稿モジュール
tweepy を使ったツイート・メディアアップロード・スレッド投稿
"""

import os
import requests
import tweepy
from io import BytesIO


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _get_v1_api() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def upload_media_from_url(image_url: str) -> str | None:
    """画像URLからX Mediaにアップロードしてmedia_idを返す"""
    try:
        resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        api = _get_v1_api()
        media = api.media_upload(filename="article_image.jpg", file=BytesIO(resp.content))
        return str(media.media_id)
    except Exception as e:
        print(f"[画像アップロード失敗] {e}")
        return None


def post_tweet(text: str, media_id: str | None = None) -> dict | None:
    """ツイートを投稿する。成功したら {"id": ..., "text": ...} を返す"""
    try:
        client = _get_client()
        kwargs: dict = {"text": text}
        if media_id:
            kwargs["media_ids"] = [media_id]
        resp = client.create_tweet(**kwargs)
        tweet_id = resp.data["id"]
        print(f"[X投稿成功] tweet_id={tweet_id}")
        return {"id": tweet_id, "text": text}
    except Exception as e:
        print(f"[X投稿失敗] {e}")
        return None


def post_thread(tweets: list[str]) -> str | None:
    """スレッド形式でツイートを連続投稿し、最初のtweet_idを返す"""
    try:
        client = _get_client()
        reply_to_id: str | None = None
        first_id: str | None = None

        for text in tweets:
            kwargs: dict = {"text": text}
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id
            resp = client.create_tweet(**kwargs)
            tweet_id = resp.data["id"]
            if first_id is None:
                first_id = tweet_id
            reply_to_id = tweet_id

        print(f"[スレッド投稿成功] {len(tweets)}ツイート, first_id={first_id}")
        return first_id
    except Exception as e:
        print(f"[スレッド投稿失敗] {e}")
        return None
