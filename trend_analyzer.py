"""
バズりAI投稿パターン分析モジュール
- X API (bearer token あり): 直近の高エンゲージメント投稿を取得して分析
- フォールバック: 実績ベースのバズりパターン定数を返す
"""

import os
import anthropic

try:
    import tweepy
    _TWEEPY_AVAILABLE = True
except ImportError:
    _TWEEPY_AVAILABLE = False


# ---- フォールバック用・実績ベースのバズりパターン --------------------------------

VIRAL_PATTERNS_FALLBACK = """
・衝撃的な数字・統計から始まる（例: 「AIで年間1000時間削減」「精度93%達成」）
・「○○を知らないと損」「○○してる人がやってること」の形式
・問いかけで終わらせてリプライ・RTを促す
・専門家ならではの「意外な本音」「実は○○だった」の逆張り
・ビフォーアフターの対比（AI導入前 vs 後、従来 vs 最新）
・「1/」から始まるスレッド予告（読み続けたいと思わせる）
・医療・教育・働き方など身近な課題とAIを直結させる
"""

VIRAL_FORMATS = """
【A: 衝撃スタート型】
「[驚きの事実・数字]。[それが意味すること]。[問い]」

【B: 逆張り洞察型】
「[一般常識]は間違いかもしれない。[理由・自分の視点]。#AI」

【C: リスト型（保存率高い）】
「[テーマ]で知っておくべきこと：
①…
②…
③…」

【D: 問いかけ型（RT・リプ促進）】
「[考えさせる問い]？
自分は[立場・考え]。あなたはどう思う？」

【E: 体験・実証型（信頼性高い）】
「実際に[行動]した。結果: [驚きの結果]。学び: [一言]」

【F: 予測・警告型（拡散しやすい）】
「[X年後]、[大胆な予測]。今できることは[具体アクション]」
"""


# ---- X API での取得 -----------------------------------------------------------

def _fetch_viral_tweets_from_api(max_results: int = 10) -> list[dict]:
    """X API v2 で直近のバズりAI投稿を取得（bearer_token 必須）"""
    if not _TWEEPY_AVAILABLE:
        return []

    bearer_token = os.environ.get("X_BEARER_TOKEN", "")
    if not bearer_token:
        return []

    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        query = (
            "(AI OR 人工知能 OR 生成AI OR ChatGPT OR Claude OR LLM) "
            "lang:ja -is:retweet min_faves:50"
        )
        response = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["public_metrics", "text"],
            sort_order="relevancy",
        )
        if not response.data:
            return []

        tweets = []
        for tweet in response.data:
            m = tweet.public_metrics or {}
            tweets.append({
                "text": tweet.text,
                "likes": m.get("like_count", 0),
                "retweets": m.get("retweet_count", 0),
                "engagement": m.get("like_count", 0) + m.get("retweet_count", 0) * 3,
            })
        return sorted(tweets, key=lambda x: x["engagement"], reverse=True)
    except Exception:
        return []


def _analyze_patterns_with_claude(tweets: list[dict]) -> str:
    """Claude でバズりパターンを抽出"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    samples = "\n---\n".join(
        f"いいね:{t['likes']} RT:{t['retweets']}\n{t['text']}"
        for t in tweets[:5]
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                "以下のバズったAI投稿を分析し、共通するバズりパターンを"
                "箇条書き（・）で3〜5個挙げてください。説明は最小限に。\n\n"
                f"{samples}"
            ),
        }],
    )
    return message.content[0].text


# ---- 公開インターフェース -------------------------------------------------------

def get_viral_patterns() -> str:
    """バズりパターン文字列を返す（X APIあれば動的、なければ定数）"""
    tweets = _fetch_viral_tweets_from_api()
    if tweets:
        return _analyze_patterns_with_claude(tweets)
    return VIRAL_PATTERNS_FALLBACK


def get_viral_formats() -> str:
    """バズりフォーマット定数を返す"""
    return VIRAL_FORMATS
