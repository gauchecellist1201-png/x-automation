"""
Pillow を使ったAI投稿用ビジュアルカード生成モジュール
サイズ: 1200x675 (16:9) — X/Twitter 推奨サイズ
フォント: Noto Sans CJK JP (Ubuntu: sudo apt-get install fonts-noto-cjk)
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CARD_W, CARD_H = 1200, 675
OUTPUT_DIR = Path("data/posted_images")

# カラーパレット（ダークネイビー × シアン）
BG_DARK = (8, 8, 22)
BG_MID = (18, 12, 40)
ACCENT = (0, 210, 255)
TEXT_WHITE = (240, 240, 255)
TEXT_MUTED = (140, 140, 170)
ACCENT_DARK = (0, 100, 130)

# フォントパス候補（GitHub Actions Ubuntu + ローカル）
_FONT_CANDIDATES_BOLD = [
    os.environ.get("FONT_PATH_BOLD", ""),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
]
_FONT_CANDIDATES_REG = [
    os.environ.get("FONT_PATH", ""),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
]

# TTC内のフォントインデックス (0=SC, 1=TC, 2=JP, 3=KR)
_TTC_JP_INDEX = 2


def _find_font(candidates: list[str]) -> str:
    for path in candidates:
        if path and Path(path).exists():
            return path
    return ""


def _load_font(path: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not path:
        return ImageFont.load_default()
    try:
        if path.endswith(".ttc"):
            return ImageFont.truetype(path, size, index=_TTC_JP_INDEX)
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int = 24) -> list[str]:
    """日本語・英語混在テキストを指定文字数で折り返す"""
    punctuation = set("。、！？.!?,　 ")
    result: list[str] = []
    while len(text) > max_chars:
        pos = max_chars
        for i in range(max_chars, max(max_chars - 6, 0), -1):
            if i < len(text) and text[i] in punctuation:
                pos = i + 1
                break
        result.append(text[:pos].strip())
        text = text[pos:].strip()
    if text:
        result.append(text)
    return result[:4]


def _draw_background(draw: ImageDraw.ImageDraw) -> None:
    for y in range(CARD_H):
        t = y / CARD_H
        r = int(BG_DARK[0] + (BG_MID[0] - BG_DARK[0]) * t)
        g = int(BG_DARK[1] + (BG_MID[1] - BG_DARK[1]) * t)
        b = int(BG_DARK[2] + (BG_MID[2] - BG_DARK[2]) * t)
        draw.line([(0, y), (CARD_W, y)], fill=(r, g, b))


def _draw_decorations(draw: ImageDraw.ImageDraw) -> None:
    # 左側のアクセントバー
    draw.rectangle([(0, 0), (6, CARD_H)], fill=ACCENT)
    # 下部のライン
    draw.rectangle([(0, CARD_H - 5), (CARD_W, CARD_H)], fill=ACCENT_DARK)
    # 右下のドットパターン
    for dx in range(8):
        for dy in range(5):
            cx = CARD_W - 90 + dx * 18
            cy = CARD_H - 100 + dy * 18
            alpha = max(30, 80 - (dx + dy) * 8)
            draw.ellipse([(cx - 2, cy - 2), (cx + 2, cy + 2)], fill=(*ACCENT, alpha))
    # 右上のAIバッジ
    badge_x1, badge_y1 = CARD_W - 170, 28
    badge_x2, badge_y2 = CARD_W - 28, 72
    draw.rounded_rectangle([(badge_x1, badge_y1), (badge_x2, badge_y2)], radius=18, fill=ACCENT)


def create_ai_card(
    headline: str,
    author: str = "@GAUCHE_cellist",
    date_str: str = "",
) -> Path | None:
    """ビジュアルカードを生成してパスを返す。失敗時は None。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "card_latest.png"

    bold_path = _find_font(_FONT_CANDIDATES_BOLD)
    reg_path = _find_font(_FONT_CANDIDATES_REG)

    try:
        img = Image.new("RGB", (CARD_W, CARD_H), BG_DARK)
        draw = ImageDraw.Draw(img)

        _draw_background(draw)
        _draw_decorations(draw)

        # フォント
        f_badge = _load_font(bold_path, 22, bold=True)
        f_headline = _load_font(bold_path, 54, bold=True)
        f_author = _load_font(bold_path, 30, bold=True)
        f_date = _load_font(reg_path, 22)

        # バッジテキスト
        draw.text((CARD_W - 158, 40), "AI  NEWS", font=f_badge, fill=BG_DARK)

        # ヘッドライン（折り返し）
        lines = _wrap_text(headline, max_chars=22)
        y = 110
        for line in lines:
            draw.text((60, y), line, font=f_headline, fill=TEXT_WHITE)
            y += 70

        # 著者
        draw.text((60, CARD_H - 80), author, font=f_author, fill=ACCENT)
        if date_str:
            draw.text((60, CARD_H - 44), date_str, font=f_date, fill=TEXT_MUTED)

        img.save(str(output_path), "PNG", optimize=True)
        print(f"[画像生成完了] {output_path}")
        return output_path
    except Exception as e:
        print(f"[画像生成失敗] {e}")
        return None
