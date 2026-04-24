"""
毎日21:00 JST にAI投稿を自動生成・X投稿 + LINE通知するスクリプト

環境変数:
  AUTO_POST_TO_X=true   → X (Twitter) に自動投稿
  USE_THREAD_POST=true  → スレッド形式で投稿
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import (
    TweetContent,
    fetch_rss_headlines,
    generate_posts_from_notes,
    generate_viral_single_posts,
    generate_viral_thread,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    return set(LOG_FILE.read_text(encoding="utf-8").splitlines())


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted]


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


def post_to_x(tweet_text: str) -> str | None:
    """X に単発ツイートを投稿。成功時はツイートIDを返す"""
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        response = client.create_tweet(text=tweet_text)
        return str(response.data["id"])
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None


def post_thread_to_x(tweets: list[str]) -> list[str]:
    """X にスレッドを投稿。成功したツイートIDのリストを返す"""
    if not tweets:
        return []
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        tweet_ids: list[str] = []
        reply_to: str | None = None
        for tweet_text in tweets:
            kwargs: dict = {"text": tweet_text}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to
            response = client.create_tweet(**kwargs)
            tweet_id = str(response.data["id"])
            tweet_ids.append(tweet_id)
            reply_to = tweet_id
        return tweet_ids
    except Exception as e:
        print(f"[Xスレッド投稿エラー] {e}")
        return []


def _x_status_url(tweet_id: str) -> str:
    return f"https://x.com/GAUCHE_cellist/status/{tweet_id}"


def build_line_posted_notification(content: TweetContent, tweet_id: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n✅ {today} X投稿完了！",
        _x_status_url(tweet_id),
        "─" * 20,
    ]
    if content.is_thread:
        lines.append(f"【スレッド {len(content.tweets)}件】")
        for i, tweet in enumerate(content.tweets, 1):
            lines.append(f"\n[{i}/{len(content.tweets)}]\n{tweet}")
            lines.append("─" * 10)
    else:
        lines.append(f"\n{content.tweets[0]}")
        lines.append("─" * 20)
    return "\n".join(lines)


def build_line_candidates_message(contents: list[TweetContent]) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案",
        "─" * 20,
    ]
    for i, content in enumerate(contents[:3], 1):
        tag = "スレッド" if content.is_thread else "単発"
        lines.append(f"\n【案{i} / {tag}】")
        if content.is_thread:
            for j, tweet in enumerate(content.tweets, 1):
                lines.append(f"[{j}] {tweet}")
        else:
            lines.append(content.tweets[0])
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def _has_x_credentials() -> bool:
    return all(
        os.environ.get(k)
        for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    )


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    auto_post = os.environ.get("AUTO_POST_TO_X", "false").lower() == "true"
    use_thread = os.environ.get("USE_THREAD_POST", "false").lower() == "true"

    if auto_post and not _has_x_credentials():
        print("[警告] AUTO_POST_TO_X=true ですが X API キーが未設定です。LINE通知モードに切り替えます。")
        auto_post = False

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    # Note記事から生成（優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        tweets = generate_posts_from_notes(note_text, feedback_text)
        if tweets:
            best_text = random.choice(tweets)
            content = TweetContent(tweets=[best_text], is_thread=False, topic=note_file.stem)

            if auto_post:
                tweet_id = post_to_x(best_text)
                if tweet_id:
                    append_to_log(f"{note_file.name}\t{date.today()}\tx_posted\t{tweet_id}")
                    print(f"[X投稿完了] {_x_status_url(tweet_id)}")
                    if line_token and line_user_id:
                        send_line_message(line_token, line_user_id,
                                          build_line_posted_notification(content, tweet_id))
                    return

            if line_token and line_user_id:
                send_line_message(line_token, line_user_id,
                                  build_line_candidates_message([content]))
            append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] Note: {note_file.name}")
            return

    # RSSニュースから生成
    headlines = fetch_rss_headlines()

    if auto_post:
        if use_thread:
            thread = generate_viral_thread(headlines, feedback_text)
            if thread and thread.tweets:
                tweet_ids = post_thread_to_x(thread.tweets)
                if tweet_ids:
                    append_to_log(f"thread\t{date.today()}\tx_posted\t{tweet_ids[0]}")
                    print(f"[Xスレッド投稿完了] {len(thread.tweets)}件 → {_x_status_url(tweet_ids[0])}")
                    if line_token and line_user_id:
                        send_line_message(line_token, line_user_id,
                                          build_line_posted_notification(thread, tweet_ids[0]))
                    return

        candidates = generate_viral_single_posts(headlines, feedback_text)
        if candidates:
            best = candidates[0]
            tweet_id = post_to_x(best.tweets[0])
            if tweet_id:
                append_to_log(f"rss\t{date.today()}\tx_posted\t{tweet_id}")
                print(f"[X投稿完了] {_x_status_url(tweet_id)}")
                if line_token and line_user_id:
                    send_line_message(line_token, line_user_id,
                                      build_line_posted_notification(best, tweet_id))
                return

    # LINE通知モード（手動投稿）
    single_candidates = generate_viral_single_posts(headlines, feedback_text)
    thread_candidate = generate_viral_thread(headlines, feedback_text)

    all_candidates: list[TweetContent] = []
    if thread_candidate:
        all_candidates.append(thread_candidate)
    all_candidates.extend(single_candidates)

    if all_candidates and line_token and line_user_id:
        message = build_line_candidates_message(all_candidates)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] AIニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
