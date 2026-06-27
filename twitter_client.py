"""
X (Twitter) API v2 クライアント
tweepy を使って投稿・画像アップロードを行う
"""

import os
import re
import time
import requests
import tweepy
from pathlib import Path

_SCRATCHPAD = Path("/tmp/claude-0")
_SCRATCHPAD.mkdir(parents=True, exist_ok=True)


def _build_client() -> tuple[tweepy.Client, tweepy.API]:
    """v2 Client (投稿) と v1.1 API (メディアアップロード) を返す"""
    consumer_key = os.environ["X_API_KEY"]
    consumer_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_token_secret = os.environ["X_ACCESS_TOKEN_SECRET"]

    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    auth = tweepy.OAuth1UserHandler(
        consumer_key, consumer_secret, access_token, access_token_secret
    )
    api_v1 = tweepy.API(auth)
    return client, api_v1


def _download_image(url: str, dest: Path) -> bool:
    """URLから画像をダウンロード。成功時True"""
    try:
        resp = requests.get(url, timeout=10, stream=True)
        if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
            dest.write_bytes(resp.content)
            return True
    except Exception:
        pass
    return False


def _upload_media(api_v1: tweepy.API, image_url: str) -> str | None:
    """画像URLをダウンロードしてX v1.1 APIでアップロード、media_idを返す"""
    img_path = _SCRATCHPAD / "tweet_image.jpg"
    if not _download_image(image_url, img_path):
        return None
    try:
        media = api_v1.media_upload(str(img_path))
        return str(media.media_id)
    except Exception as e:
        print(f"[画像アップロード失敗] {e}")
        return None


def post_tweet(text: str, image_url: str | None = None) -> str | None:
    """
    テキスト（+任意で画像）をXに投稿。
    成功時はツイートURLを返す。失敗時はNone。
    """
    client, api_v1 = _build_client()

    media_ids = None
    if image_url:
        media_id = _upload_media(api_v1, image_url)
        if media_id:
            media_ids = [media_id]

    try:
        response = client.create_tweet(text=text, media_ids=media_ids)
        tweet_id = response.data["id"]
        me = client.get_me()
        username = me.data.username
        return f"https://x.com/{username}/status/{tweet_id}"
    except tweepy.TweepyException as e:
        print(f"[投稿失敗] {e}")
        return None


def post_thread(posts: list[str], image_url: str | None = None) -> list[str]:
    """
    複数テキストをスレッドとして投稿。
    最初のツイートにのみ画像を添付する。
    成功した各ツイートのURLリストを返す。
    """
    client, api_v1 = _build_client()
    urls: list[str] = []
    reply_to_id: str | None = None

    me = client.get_me()
    username = me.data.username

    for i, text in enumerate(posts):
        media_ids = None
        if i == 0 and image_url:
            media_id = _upload_media(api_v1, image_url)
            if media_id:
                media_ids = [media_id]

        kwargs: dict = {"text": text}
        if reply_to_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_id
        if media_ids:
            kwargs["media_ids"] = media_ids

        try:
            response = client.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            reply_to_id = tweet_id
            urls.append(f"https://x.com/{username}/status/{tweet_id}")
        except tweepy.TweepyException as e:
            print(f"[スレッド投稿失敗 {i+1}件目] {e}")
            break

        if i < len(posts) - 1:
            time.sleep(1)

    return urls
