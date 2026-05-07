"""
OpenAI DALL-E 3 を使ったX投稿用画像生成モジュール
生成されたURLは約1時間有効。その間にダウンロードしてXに添付してください。
"""

import os
from openai import OpenAI


def generate_tweet_image(prompt: str) -> str | None:
    """
    DALL-E 3 で画像を生成し、一時URLを返す。
    OPENAI_API_KEY が未設定、または生成失敗時は None を返す。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[画像生成スキップ] OPENAI_API_KEY が未設定")
        return None

    client = OpenAI(api_key=api_key)

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        print(f"[画像生成完了] {url[:60]}...")
        return url
    except Exception as e:
        print(f"[画像生成エラー] {e}")
        return None
