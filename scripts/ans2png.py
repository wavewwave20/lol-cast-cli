"""tmux capture-pane -e 출력(ANSI) → PNG. 문자별 폰트 폴백으로 한글/이모지/블록 정확 렌더."""
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont
from rich.cells import cell_len
from rich.text import Text

from rich.terminal_theme import TerminalTheme

CW, CH, FS = 24, 52, 40          # 셀폭/셀높이/폰트크기 (2x 스케일)
PAD = 36
BG = (24, 24, 24)
FG = (222, 222, 222)

# Windows Terminal Campbell 팔레트 — ANSI 색을 보기 좋은 톤으로
THEME = TerminalTheme(
    BG, FG,
    [(12, 12, 12), (197, 15, 31), (19, 161, 14), (193, 156, 0),
     (0, 95, 218), (136, 23, 152), (58, 150, 221), (204, 204, 204)],
    [(118, 118, 118), (231, 72, 86), (22, 198, 12), (249, 241, 165),
     (59, 120, 255), (180, 0, 158), (97, 214, 214), (242, 242, 242)],
)

DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono{}.ttf"
CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"
EMOJI_FONT = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)

# CJK는 전각 advance가 1em이라 2셀(2*CW)에 딱 맞게 폰트 크기를 키운다
FONTS = {
    ("latin", False): ImageFont.truetype(DEJAVU.format(""), FS),
    ("latin", True): ImageFont.truetype(DEJAVU.format("-Bold"), FS),
    ("cjk", False): ImageFont.truetype(CJK.format("Regular"), CW * 2, index=6),
    ("cjk", True): ImageFont.truetype(CJK.format("Bold"), CW * 2, index=6),
}


def char_class(ch: str) -> str:
    o = ord(ch)
    if 0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF and unicodedata.category(ch) == "So":
        return "emoji"
    if cell_len(ch) == 2:  # 한글/CJK 전각
        return "cjk"
    return "latin"


def main(src: str, dst: str) -> None:
    lines = open(src, encoding="utf-8", errors="replace").read().splitlines()
    rows = [Text.from_ansi(l) for l in lines]
    width_cells = max((cell_len(r.plain) for r in rows), default=80)
    img = Image.new("RGB", (PAD * 2 + width_cells * CW, PAD * 2 + len(rows) * CH), BG)
    draw = ImageDraw.Draw(img)

    for row_i, text in enumerate(rows):
        x = 0
        y = PAD + row_i * CH
        for span_text, style in _segments(text):
            fg, bold, dim = FG, False, False
            bg = None
            if style:
                if style.color:
                    c = style.color.get_truecolor(THEME)
                    fg = (c.red, c.green, c.blue)
                if style.bgcolor:
                    c = style.bgcolor.get_truecolor(THEME, foreground=False)
                    bg = (c.red, c.green, c.blue)
                bold = bool(style.bold)
                dim = bool(style.dim)
            if dim:
                fg = tuple((f + b) // 2 for f, b in zip(fg, BG))
            for ch in span_text:
                w = cell_len(ch)
                if w == 0:
                    continue
                px = PAD + x * CW
                if bg:
                    draw.rectangle((px, y, px + w * CW, y + CH), fill=bg)
                cls = char_class(ch)
                if cls == "emoji":
                    tile = Image.new("RGBA", (137, 137))
                    ImageDraw.Draw(tile).text((0, 0), ch, font=EMOJI_FONT,
                                              embedded_color=True)
                    tile = tile.resize((CH - 6, CH - 6), Image.LANCZOS)
                    img.paste(tile, (px, y + 3), tile)
                elif ch.strip():
                    f = FONTS[(cls, bold)]
                    draw.text((px, y + CH // 2), ch, font=f, fill=fg, anchor="lm")
                x += w
    img.save(dst)


def _segments(text: Text):
    """rich Text의 (문자열, 스타일) 세그먼트."""
    from rich.console import Console
    console = Console(color_system="truecolor")
    for seg in text.render(console):
        yield seg.text, seg.style


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
    print("rendered")
