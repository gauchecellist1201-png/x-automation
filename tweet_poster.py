"""
X (Twitter) API v2 を使ったツイート投稿モジュール
必要な環境変数: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
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


def _get_v1_api() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def upload_media(image_path: str) -> str | None:
    """画像をXにアップロードしてmedia_idを返す"""
    try:
        api = _get_v1_api()
        media = api.media_upload(image_path)
        return str(media.media_id)
    except Exception as e:
        print(f"[メディアアップロード失敗] {e}")
        return None


def post_tweet(text: str, image_path: str | None = None) -> str | None:
    """Xに投稿し、成功したらツイートIDを返す"""
    try:
        media_id = upload_media(image_path) if image_path else None
        client = _get_client()
        kwargs: dict = {}
        if media_id:
            kwargs["media_ids"] = [media_id]
        response = client.create_tweet(text=text, **kwargs)
        tweet_id = str(response.data["id"])
        print(f"[ツイート投稿成功] https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except Exception as e:
        print(f"[ツイート投稿失敗] {e}")
        return None
