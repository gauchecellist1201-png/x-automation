"""
毎日21:00 JST にAI投稿案を生成してXに自動投稿 + LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


# ─── ログ管理 ──────────────────────────────────────────────────────────────────
def load_posted_log() -> set[str]:
    """ログからファイル名（第1フィールド）のみ抽出"""
    if not LOG_FILE.exists():
        return set()
    posted: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts:
            posted.add(parts[0].strip())
    return posted


def already_posted_today() -> bool:
    """本日すでに投稿済みかチェック"""
    today_str = str(date.today())
    if not LOG_FILE.exists():
        return False
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if today_str in line:
            return True
    return False


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return [p for p in sorted(NOTES_DIR.glob("*.md")) if p.name not in posted]


# ─── X自動投稿 ────────────────────────────────────────────────────────────────
def post_to_x(tweet_text: str) -> str | None:
    """
    tweepy 経由でXに投稿。
    Returns: ツイートURL or None（認証情報がない場合も None）
    """
    try:
        import tweepy  # type: ignore
    except ImportError:
        return None

    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        return None

    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data["id"]
        return f"https://x.com/i/web/status/{tweet_id}"
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None


# ─── LINE通知 ─────────────────────────────────────────────────────────────────
def send_line_message(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response.status_code == 200


def build_line_message(
    posts: list[str],
    source: str,
    posted_url: str | None = None,
    news_items: list[dict] | None = None,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", "─" * 22]

    if posted_url:
        lines.append(f"\n✅ 自動投稿完了: {posted_url}")
        lines.append("─" * 22)

    for i, post in enumerate(posts[:3], 1):
        label = "【自動投稿済み】" if i == 1 and posted_url else f"【案{i}】"
        lines.append(f"\n{label}\n{post}")
        lines.append("─" * 22)

    if not posted_url:
        lines.append("\n✏️ 気に入った案をコピーしてXに投稿してください！")

    if news_items:
        lines.append("\n📰 参考ニュースソース（上位3件）")
        for item in news_items[:3]:
            title = item.get("title", "")[:40]
            url = item.get("url", "")
            if url:
                lines.append(f"・{title}\n  {url}")
            else:
                lines.append(f"・{title}")

    return "\n".join(lines)


# ─── メインロジック ────────────────────────────────────────────────────────────
def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")

    if already_posted_today():
        print(f"[スキップ] 本日({date.today()})はすでに投稿済みです。")
        sys.exit(0)

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    news_items: list[dict] = []

    # Note記事から生成（未投稿のものがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note本文中の NOTE_URL を抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            source = f"Note: {note_file.stem}"
            # Note使用を記録（次回は別のファイルを選ぶ）
            append_to_log(f"{note_file.name}\t{date.today()}\tgenerated")

    # Note未使用 or 生成失敗 → RSSトレンドから生成
    if not posts:
        posts, news_items = generate_posts_from_rss()
        source = "AIトレンド"

    if not posts:
        print("[警告] 投稿候補を生成できませんでした。")
        sys.exit(1)

    # X自動投稿（認証情報がある場合）
    posted_url = post_to_x(posts[0])
    if posted_url:
        print(f"[X投稿完了] {posted_url}")
        append_to_log(f"rss\t{date.today()}\tx_posted\t{posted_url}")
    else:
        print("[X投稿スキップ] 認証情報なし or エラー → LINE通知のみ")

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(posts, source, posted_url, news_items)
        if send_line_message(line_token, line_user_id, message):
            if not posted_url:
                append_to_log(f"rss\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] {source}")
        else:
            print("[LINE通知失敗]")
    else:
        # LINE未設定の場合はコンソール出力
        print(f"\n=== 今日の投稿案 [{source}] ===")
        for i, p in enumerate(posts[:3], 1):
            print(f"\n【案{i}】\n{p}")
        if not posted_url:
            append_to_log(f"rss\t{date.today()}\tgenerated")


if __name__ == "__main__":
    main()
