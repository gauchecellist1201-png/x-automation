"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト v2
- バグ修正: posted_log のパース修正（ノートが繰り返し選ばれていた問題）
- 改善: 7日間クールダウンで同じノートが連続しない
- 改善: LINEメッセージにパターン名・参照ニュースを表示
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import (
    generate_posts_from_notes_with_meta,
    generate_posts_from_rss_with_meta,
    _generate_original_ai_insight,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# 同じノートを再利用するまでの最低日数
NOTE_COOLDOWN_DAYS = 7


# ─────────────────────────────────────────
# ログ管理
# ─────────────────────────────────────────
def load_posted_log() -> list[dict]:
    """ログファイルをパースして辞書リストで返す"""
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append({"file": parts[0], "date": parts[1], "status": parts[2] if len(parts) > 2 else ""})
    return entries


def get_recently_used_notes(entries: list[dict], cooldown_days: int) -> set[str]:
    """クールダウン期間内に使ったノートファイル名のセットを返す"""
    cutoff = date.today() - timedelta(days=cooldown_days)
    recent: set[str] = set()
    for e in entries:
        try:
            posted_date = date.fromisoformat(e["date"])
            if posted_date >= cutoff:
                recent.add(e["file"])
        except ValueError:
            continue
    return recent


def append_to_log(file_name: str, status: str = "line_notified") -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{file_name}\t{date.today()}\t{status}\n")


def get_available_notes(recently_used: set[str]) -> list[Path]:
    """クールダウン期間外のノートを返す（なければ全ノートから選ぶ）"""
    if not NOTES_DIR.exists():
        return []
    all_notes = list(NOTES_DIR.glob("*.md"))
    available = [p for p in all_notes if p.name not in recently_used]
    # クールダウン外がなければ全ノートから（最後に使った日が最も古いものを優先）
    return available if available else all_notes


# ─────────────────────────────────────────
# LINE 通知
# ─────────────────────────────────────────
def send_line_message(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
    return response.status_code == 200


def build_line_message(
    posts_with_meta: list[tuple[str, str]],
    source: str,
    reference: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📰 ソース: {source}",
    ]
    if reference:
        lines.append(f"🔗 参照: {reference[:60]}{'...' if len(reference) > 60 else ''}")
    lines.append("─" * 22)

    for i, (post, pattern) in enumerate(posts_with_meta[:3], 1):
        lines.append(f"\n【案{i}】({pattern})")
        lines.append(post)
        lines.append(f"（{len(post)}文字）")
        lines.append("─" * 22)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 ハッシュタグや改行を微調整するとさらに伸びます")
    return "\n".join(lines)


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log_entries = load_posted_log()
    recently_used = get_recently_used_notes(log_entries, NOTE_COOLDOWN_DAYS)
    available_notes = get_available_notes(recently_used)

    # Note記事から生成（クールダウン期間外のファイルを優先）
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NoteのURL抽出（ファイル内に NOTE_URL: が書いてあれば使う）
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        posts_with_meta = generate_posts_from_notes_with_meta(note_text, feedback_text, note_url)
        if posts_with_meta:
            message = build_line_message(
                posts_with_meta,
                source=f"Note: {note_file.stem}",
                reference=note_url,
            )
            if send_line_message(line_token, line_user_id, message):
                append_to_log(note_file.name)
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts_with_meta, headline = generate_posts_from_rss_with_meta()
    if posts_with_meta:
        message = build_line_message(
            posts_with_meta,
            source="AIニュース（RSS）",
            reference=headline,
        )
        if send_line_message(line_token, line_user_id, message):
            append_to_log("rss")
            print("[LINE通知完了] RSSニュース")
            return

    # フォールバック：オリジナル洞察
    fallback_posts = _generate_original_ai_insight()
    if fallback_posts:
        fallback_with_meta = [(p, "オリジナル洞察") for p in fallback_posts]
        message = build_line_message(fallback_with_meta, source="オリジナル洞察")
        if send_line_message(line_token, line_user_id, message):
            append_to_log("original")
            print("[LINE通知完了] オリジナル洞察")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
