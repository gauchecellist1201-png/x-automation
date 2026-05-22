"""
X(Twitter) 投稿モジュール
tweepy v4 + OAuth 1.0a（OGP画像添付対応）
"""
import io
import os
import re
import time

import requests
import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def _get_api_v1() -> tweepy.API:
    """メディアアップロード用 v1.1 API クライアント"""
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def get_og_image_url(article_url: str) -> str | None:
    """記事のOGP画像URLを取得（失敗時はNone）"""
    if not article_url:
        return None
    try:
        resp = requests.get(
            article_url,
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = resp.text
        # property="og:image" または property='og:image'
        for pattern in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]:
            m = re.search(pattern, html)
            if m:
                url = m.group(1).strip()
                if url.startswith("http"):
                    return url
    except Exception:
        pass
    return None


def upload_image(image_url: str) -> str | None:
    """画像URLからX用メディアIDを返す（失敗時はNone）"""
    if not image_url:
        return None
    try:
        resp = requests.get(
            image_url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
        if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
            ext = "jpg"

        img_bytes = io.BytesIO(resp.content)
        img_bytes.name = f"ogimage.{ext}"

        api_v1 = _get_api_v1()
        media = api_v1.media_upload(filename=img_bytes.name, file=img_bytes)
        return str(media.media_id)
    except Exception as e:
        print(f"[画像アップロードエラー] {e}")
        return None


def post_tweet(text: str, media_id: str | None = None) -> str | None:
    """1件ツイートを投稿し、ツイートIDを返す（失敗時はNone）"""
    client = _get_client()
    try:
        kwargs: dict = {"text": text}
        if media_id:
            kwargs["media_ids"] = [media_id]
        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        print(f"[X投稿成功] ID: {tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        print(f"[X投稿エラー] {e}")
        return None


def post_thread(tweets: list[str], media_id: str | None = None) -> list[str]:
    """スレッド投稿。先頭ツイートにのみ画像を添付。成功したIDリストを返す"""
    if not tweets:
        return []

    client = _get_client()
    posted_ids: list[str] = []
    reply_to_id: str | None = None

    for i, text in enumerate(tweets):
        try:
            kwargs: dict = {"text": text}
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id
            if i == 0 and media_id:
                kwargs["media_ids"] = [media_id]

            response = client.create_tweet(**kwargs)
            tweet_id = str(response.data["id"])
            posted_ids.append(tweet_id)
            reply_to_id = tweet_id
            print(f"[Xスレッド {i + 1}/{len(tweets)}] ID: {tweet_id}")

            if i < len(tweets) - 1:
                time.sleep(1)  # レート制限回避

        except tweepy.TweepyException as e:
            print(f"[Xスレッドエラー tweet {i + 1}] {e}")
            break

    return posted_ids
