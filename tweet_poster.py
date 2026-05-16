"""
X (Twitter) API v2 投稿モジュール
OAuth 1.0a User Context を使用して自分のアカウントにツイートを投稿する
"""

import os
import requests
from requests_oauthlib import OAuth1


X_TWEET_URL = "https://api.twitter.com/2/tweets"
X_ACCOUNT = "GAUCHE_cellist"


def _build_auth() -> OAuth1:
    return OAuth1(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_tweet(text: str) -> dict:
    """X API v2 でツイートを投稿し、結果を返す"""
    try:
        auth = _build_auth()
        response = requests.post(
            X_TWEET_URL,
            auth=auth,
            json={"text": text},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if response.status_code == 201:
            tweet_id = response.json()["data"]["id"]
            return {
                "success": True,
                "tweet_id": tweet_id,
                "url": f"https://x.com/{X_ACCOUNT}/status/{tweet_id}",
            }
        return {
            "success": False,
            "error": response.text,
            "status_code": response.status_code,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def x_api_available() -> bool:
    """X API に必要な環境変数が揃っているか確認"""
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    return all(os.environ.get(k) for k in required)
