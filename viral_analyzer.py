"""
バズりAIツイートのパターン分析モジュール
X API v2が使用可能な場合は実データを取得、なければ実績ベースの定型パターンを返す
"""

import os

try:
    import tweepy
    _TWEEPY_AVAILABLE = True
except ImportError:
    _TWEEPY_AVAILABLE = False


_HEURISTIC_PATTERNS = """## バズるAIツイートの構造パターン（日本語・ビジネス層向け）

### 高エンゲージメントな型
1. **数字＋驚き型**: "GPT-5は前モデル比3倍の速度で、コスト1/10。この変化に気づいていない企業は危ない。"
2. **逆説型**: "AIに仕事を奪われると思っていたら、逆に新しい仕事が増えた。奪われたのは『退屈な作業』だった。"
3. **問いかけ型**: "医師とAIが同じ診断をしたとき、あなたはどちらを信じる？その答えが医療の未来を決める。"
4. **知識格差型**: "Claude Codeを使いこなすと開発速度が10倍になる。使えない人との差はもう埋められない。 #生成AI"
5. **比較・対比型**: "ChatGPTを使う経営者 vs 使わない経営者。3年後の差は想像以上に大きい。"
6. **タイムリー型**: "今日リリースされた○○が医療現場を変える可能性。詳しくは→"
7. **社会批判型**: "AIが差別を学習する。問題はアルゴリズムじゃなく、そこに込められた人間の偏見だ。 #AI"
8. **具体的数字型**: "AI診断の精度が医師を上回る分野が15領域に拡大。でも「最終判断」を誰がするかは未解決のまま。"

### 共通要素
- 冒頭の1文で「え？」「本当に？」と思わせる
- 専門用語1つ＋平易な言い換え
- 最後を「問い」か「余白」で終わらせるとRTされやすい
- ハッシュタグは末尾に1〜2個だけ
- URLリンクは文字数を消費するが信頼性を上げる
"""


def fetch_viral_patterns() -> str:
    """バズりパターンを返す。X APIが使えれば実ツイートデータを使用。"""
    bearer_token = os.environ.get("X_BEARER_TOKEN")
    if bearer_token and _TWEEPY_AVAILABLE:
        patterns = _fetch_from_x_api(bearer_token)
        if patterns:
            return patterns
    return _HEURISTIC_PATTERNS


def _fetch_from_x_api(bearer_token: str) -> str | None:
    """X API v2で直近の高エンゲージメントAIツイートを取得・フォーマット"""
    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        response = client.search_recent_tweets(
            query="(AI OR 生成AI OR ChatGPT OR Claude) -is:retweet lang:ja",
            tweet_fields=["public_metrics", "text"],
            max_results=20,
        )
        if not response.data:
            return None

        ranked = sorted(
            response.data,
            key=lambda t: (
                t.public_metrics.get("like_count", 0)
                + t.public_metrics.get("retweet_count", 0) * 3
            ),
            reverse=True,
        )[:5]

        lines = ["## 直近の高エンゲージメントAIツイート（参考）"]
        for t in ranked:
            m = t.public_metrics
            lines.append(
                f"- ❤️{m.get('like_count',0)} 🔁{m.get('retweet_count',0)}: "
                f"{t.text[:120].replace(chr(10), ' ')}"
            )
        lines.append("\n上記の文体・構造を参考に、同等かそれ以上にバズる投稿を作成してください。")
        return "\n".join(lines)

    except Exception as e:
        print(f"[viral_analyzer] X API取得失敗: {e}")
        return None
