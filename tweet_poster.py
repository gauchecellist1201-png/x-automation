"""
X (Twitter) 投稿モジュール
テキスト投稿 + 画像アップロード対応
"""

import os
import tempfile
import requests
import tweepy


def post_tweet(text: str, image_url: str | None = None) -> str | None:
    """
    Xにツイートを投稿する。
    成功した場合はtweet_idを返す。失敗した場合はNoneを返す。
    """
    consumer_key = os.environ.get("X_API_KEY")
    consumer_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("[tweet_poster] X API認証情報が不足しています")
        return None

    media_ids = None
    if image_url:
        media_ids = _upload_image(
            consumer_key, consumer_secret, access_token, access_token_secret, image_url
        )

    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    try:
        kwargs: dict = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids
        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"]) if response.data else None
        if tweet_id:
            print(f"[tweet_poster] 投稿成功: https://x.com/i/status/{tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        print(f"[tweet_poster] 投稿失敗: {e}")
        return None


def _upload_image(
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    image_url: str,
) -> list[int] | None:
    """画像URLからダウンロードしてX v1.1 media uploadで登録、media_idリストを返す"""
    try:
        resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or not resp.content:
            return None

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext = ".png" if "png" in content_type else ".jpg"

        auth = tweepy.OAuth1UserHandler(
            consumer_key, consumer_secret, access_token, access_token_secret
        )
        api = tweepy.API(auth)

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name

        media = api.media_upload(filename=tmp_path)
        return [media.media_id]

    except Exception as e:
        print(f"[tweet_poster] 画像アップロード失敗: {e}")
        return None
