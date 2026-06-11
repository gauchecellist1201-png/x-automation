"""
X (Twitter) API v2 投稿モジュール
テキスト投稿 + 画像アップロード（v1.1 media/upload）に対応
"""

import os
import requests
from requests_oauthlib import OAuth1Session


def _make_session() -> OAuth1Session:
    return OAuth1Session(
        client_key=os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_SECRET"],
    )


def post_tweet(text: str, media_ids: list[str] | None = None) -> dict:
    """テキスト（+オプションで画像）をXに投稿"""
    session = _make_session()
    payload: dict = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    r = session.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
        timeout=15,
    )
    return {
        "ok": r.status_code == 201,
        "status_code": r.status_code,
        "data": r.json(),
    }


def upload_image_from_url(image_url: str) -> str | None:
    """URLから画像をダウンロードしてX media_id を返す"""
    if not image_url:
        return None
    try:
        r = requests.get(
            image_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code != 200:
            return None
        content_type = r.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            return None
        return upload_image_bytes(r.content, content_type.split(";")[0].strip())
    except Exception as e:
        print(f"[x_poster] image download failed: {e}")
        return None


def upload_image_bytes(image_bytes: bytes, mime_type: str = "image/jpeg") -> str | None:
    """画像バイト列をアップロードして media_id_string を返す（v1.1）"""
    session = _make_session()
    try:
        r = session.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            files={"media": ("image.jpg", image_bytes, mime_type)},
            timeout=30,
        )
        if r.status_code == 200:
            media_id = str(r.json().get("media_id_string", ""))
            return media_id or None
    except Exception as e:
        print(f"[x_poster] media upload failed: {e}")
    return None
