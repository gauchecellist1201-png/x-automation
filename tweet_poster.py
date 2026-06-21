"""
X (Twitter) API v2 自動投稿モジュール
画像アップロードは v1.1 メディアエンドポイントを使用
"""
import io
import os
import tweepy


def _client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _api_v1() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def upload_image(image_bytes: bytes) -> int | None:
    """画像を X Media としてアップロードし media_id を返す"""
    try:
        api = _api_v1()
        media = api.media_upload(filename="ogp.jpg", file=io.BytesIO(image_bytes))
        return media.media_id
    except Exception as e:
        print(f"[画像アップロード失敗] {e}")
        return None


def post_tweet(text: str, image_bytes: bytes | None = None) -> str:
    """X に投稿して tweet_id を返す"""
    client = _client()

    media_ids = None
    if image_bytes:
        media_id = upload_image(image_bytes)
        if media_id:
            media_ids = [media_id]

    kwargs: dict = {"text": text}
    if media_ids:
        kwargs["media_ids"] = media_ids

    resp = client.create_tweet(**kwargs)
    tweet_id = str(resp.data["id"])
    print(f"[X投稿完了] https://x.com/i/web/status/{tweet_id}")
    return tweet_id
