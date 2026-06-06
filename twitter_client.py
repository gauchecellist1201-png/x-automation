"""
X (Twitter) API v2 クライアント
投稿・スレッド投稿・バズツイート取得
"""

import os
from typing import Optional
import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def post_tweet(text: str) -> Optional[str]:
    """ツイートを投稿し tweet_id を返す。失敗時は None。"""
    try:
        client = _get_client()
        response = client.create_tweet(text=text)
        if response.data:
            return str(response.data["id"])
    except Exception as e:
        print(f"[X投稿エラー] {e}")
    return None


def post_thread(tweets: list[str]) -> list[str]:
    """スレッドとして複数ツイートを順番に投稿し tweet_id リストを返す。"""
    ids: list[str] = []
    reply_to: Optional[str] = None
    try:
        client = _get_client()
        for text in tweets:
            kwargs: dict = {"text": text}
            if reply_to:
                kwargs["reply"] = {"in_reply_to_tweet_id": reply_to}
            response = client.create_tweet(**kwargs)
            if response.data:
                tweet_id = str(response.data["id"])
                ids.append(tweet_id)
                reply_to = tweet_id
    except Exception as e:
        print(f"[Xスレッド投稿エラー] {e}")
    return ids


def fetch_viral_ai_tweets(max_results: int = 10) -> list[str]:
    """バズっているAI関連ツイートのテキストを取得（Basic+ アクセス要）。
    アクセス権限不足の場合は空リストを返す。"""
    try:
        client = _get_client()
        query = (
            "(AI OR 生成AI OR ChatGPT OR Claude OR LLM OR AIエージェント) "
            "lang:ja -is:retweet min_faves:200"
        )
        response = client.search_recent_tweets(
            query=query,
            max_results=max_results,
            tweet_fields=["public_metrics"],
            sort_order="relevancy",
        )
        if not response.data:
            return []
        sorted_tweets = sorted(
            response.data,
            key=lambda t: (t.public_metrics or {}).get("like_count", 0),
            reverse=True,
        )
        return [t.text for t in sorted_tweets if len(t.text) > 20]
    except Exception:
        return []
