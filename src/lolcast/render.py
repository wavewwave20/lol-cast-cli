"""이벤트 → 미니멀 컬럼 피드 라인, 스코어보드 렌더링."""
from dataclasses import dataclass
from datetime import datetime

from rich.table import Table
from rich.text import Text

from .events import Event

DRAGON_KO = {
    "ocean": "바다", "mountain": "대지", "infernal": "화염", "cloud": "바람",
    "hextech": "마공학", "chemtech": "화학공학", "elder": "장로",
}
# 변형 선택자(VS16) 없는 안전한 2칸 이모지만 사용 (터미널 폭 계산 문제 방지)
DRAGON_EMOJI = {
    "ocean": "🌊", "mountain": "🗻", "infernal": "🔥", "cloud": "🌀",
    "hextech": "⚡", "chemtech": "🧪", "elder": "👴",
}


def _dragons_str(dragons: list[str]) -> str:
    return "".join(DRAGON_EMOJI.get(d, "🐉") for d in dragons) or "-"


TEAM_STYLE = {"blue": "bold bright_blue", "red": "bold red"}


ROLE_KO = {"top": "탑", "jungle": "정글", "mid": "미드",
           "bottom": "원딜", "support": "서폿"}


@dataclass
class GameContext:
    blue_code: str
    red_code: str
    names: dict[int, str]        # participantId -> "Faker" (팀 접두어 제거)
    champions: dict[int, str]    # participantId -> 챔피언 한글명
    roles: dict[int, str] | None = None  # participantId -> top/jungle/...
    game_start: str | None = None  # 첫 in_game 프레임의 rfc460Timestamp
    series: str = ""             # 예: "T1 vs FUR · Game 2"


@dataclass
class FeedLine:
    clock: str
    tag: str
    tag_style: str
    body: Text


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def game_clock(ctx: GameContext, ts: str) -> str:
    if not ctx.game_start:
        return "--:--"
    delta = _parse(ts) - _parse(ctx.game_start)
    total = max(0, int(delta.total_seconds()))
    return f"{total // 60:02d}:{total % 60:02d}"


def _who(ctx: GameContext, pid: int) -> str:
    name = ctx.names.get(pid, f"#{pid}")
    champ = ctx.champions.get(pid)
    return f"{name}({champ})" if champ else name


def _team_code(ctx: GameContext, side: str | None) -> str:
    return ctx.blue_code if side == "blue" else ctx.red_code


def _side_of(ctx: GameContext, pid: int) -> str:
    return "blue" if pid <= 5 else "red"


def info_line(text: str, clock: str = "") -> FeedLine:
    return FeedLine(clock, "정보", "dim", Text(text, style="dim"))


def feed_line(ctx: GameContext, ev: Event) -> FeedLine:
    clock = game_clock(ctx, ev.ts)
    t = _team_code(ctx, ev.team)
    style = TEAM_STYLE.get(ev.team or "", "")
    d = ev.data
    match ev.kind:
        case "kill":
            body = Text.assemble(
                (_who(ctx, d["killer"]), TEAM_STYLE[_side_of(ctx, d["killer"])]),
                " → ",
                (_who(ctx, d["victim"]), TEAM_STYLE[_side_of(ctx, d["victim"])]),
            )
            if d.get("assists"):
                champs = ", ".join(ctx.champions.get(p, f"#{p}")
                                   for p in d["assists"])
                body.append(f"  (어시 {champs})", style="dim")
            if d.get("first_blood"):
                return FeedLine(clock, "퍼블", "bold yellow", body)
            return FeedLine(clock, "킬", style, body)
        case "execution":
            return FeedLine(clock, "처형", "dim",
                            Text(f"{_who(ctx, d['victim'])} 사망"))
        case "dragon":
            elem = DRAGON_KO.get(d["element"], d["element"])
            return FeedLine(clock, "용", style,
                            Text(f"{t} {elem} 드래곤 ({d['stack']}스택)"))
        case "baron":
            return FeedLine(clock, "바론", style, Text(f"{t} 바론 처치"))
        case "tower":
            return FeedLine(clock, "타워", style,
                            Text(f"{t} {d['count']}번째 파괴"))
        case "inhibitor":
            return FeedLine(clock, "억제기", style,
                            Text(f"{t} 억제기 파괴 ({d['count']}번째)"))
        case "gold":
            gap = d["blue"] - d["red"]
            side = "blue" if gap >= 0 else "red"
            leader = _team_code(ctx, side)
            body = Text.assemble(
                (f"{leader} +{abs(gap) / 1000:.1f}k", TEAM_STYLE[side]),
                (f" ({d['blue'] / 1000:.1f} : {d['red'] / 1000:.1f})", "dim"),
            )
            return FeedLine(clock, "골드", "yellow", body)
        case "game_state":
            if d["to"] == "finished":
                if d.get("winner"):
                    code = _team_code(ctx, d["winner"])
                    suffix = " 승리 (추정)" if d.get("estimated") else " 승리!"
                    body = Text.assemble(
                        "게임 종료 — ", (f"{code}{suffix}", TEAM_STYLE[d["winner"]]))
                    return FeedLine(clock, "종료", "bold", body)
                return FeedLine(clock, "종료", "bold", Text("게임 종료", style="bold"))
            if d["to"] == "paused":
                return FeedLine(clock, "중지", "dim", Text("경기 일시 정지"))
            if d["from"] == "paused":
                return FeedLine(clock, "재개", "dim", Text("경기 재개"))
            return info_line(d["to"], clock)
        case _:
            return info_line(ev.kind, clock)


def winner_line(ctx: GameContext, side: str, score: str | None = None,
                estimated: bool = False) -> FeedLine:
    code = _team_code(ctx, side)
    txt = f"{code} 승리"
    if score:
        txt += f" — 세트 {score}"
    txt += " (추정)" if estimated else "!"
    return FeedLine("", "승리", TEAM_STYLE[side], Text(txt, style=TEAM_STYLE[side]))


def gold_bar(ctx: GameContext, blue: int, red: int, width: int = 20) -> Text:
    total = blue + red
    filled = round(width * (blue / total)) if total else width // 2
    return Text.assemble(
        (ctx.blue_code + " ", TEAM_STYLE["blue"]),
        ("▓" * filled, "bright_blue"),
        ("░" * (width - filled), "red"),
        (" " + ctx.red_code, TEAM_STYLE["red"]),
    )


WIDE_SCORE_MIN = 92  # 이 폭 이상이면 팀 지표를 좌우 대결 구도로


def scoreboard(ctx: GameContext, frame: dict, speed: float | None = None,
               width: int = 0):
    """상단 스코어보드: 제목/시계(+배속), 팀 지표, 골드 우위 바.

    넓은 터미널에서는 팀 지표를 좌(블루)/우(레드) 미러로 배치한다.
    """
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right")

    title = ctx.series or f"{ctx.blue_code} vs {ctx.red_code}"
    clock = game_clock(ctx, frame["rfc460Timestamp"])
    right = Text(clock, style="bold")
    if speed is not None:
        right = Text.assemble((f"x{speed:g}  ", "yellow"), (clock, "bold"))
    grid.add_row(Text(title, style="dim"), right)

    parts = [grid]
    if width >= WIDE_SCORE_MIN:
        parts.append(_teams_wide(ctx, frame))
    else:
        parts.append(_teams_stacked(ctx, frame))

    # 골드 우위 바: 가운데 정렬, 폭에 비례해 길게, 차이 라벨은 바 바로 옆에
    blue_g, red_g = frame["blueTeam"]["totalGold"], frame["redTeam"]["totalGold"]
    gap = blue_g - red_g
    side = "blue" if gap >= 0 else "red"
    bar_width = max(20, min(70, (width or 60) - 26))
    line = gold_bar(ctx, blue_g, red_g, width=bar_width)
    line.append("  ")
    line.append_text(Text(f"+{abs(gap) / 1000:.1f}k", style=TEAM_STYLE[side]))
    bar = Table.grid(expand=True)
    bar.add_column(justify="center")
    bar.add_row(line)
    parts.append(bar)

    from rich.console import Group
    return Group(*parts)


def _team_stats(tm: dict) -> tuple[int, float, int, str, int]:
    return (tm["totalKills"], tm["totalGold"] / 1000, tm["towers"],
            _dragons_str(tm["dragons"]), tm["barons"])


def _teams_stacked(ctx: GameContext, frame: dict) -> Table:
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(justify="left", ratio=1)
    for key, side in (("blueTeam", "blue"), ("redTeam", "red")):
        k, g, t, d, b = _team_stats(frame[key])
        stats = f"{k:>2}킬   {g:>5.1f}k   타워 {t:<2}  바론 {b}  용 {d}"
        grid.add_row(Text.assemble(
            (f"{_team_code(ctx, side):<5}", TEAM_STYLE[side]), stats))
    return grid


def _teams_wide(ctx: GameContext, frame: dict) -> Table:
    """블루 | vs | 레드 — 좌우 대결 구도 (레드는 미러 순서)."""
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", width=4)
    grid.add_column(justify="right", ratio=1)
    bk, bg, bt, bd, bb = _team_stats(frame["blueTeam"])
    rk, rg, rt, rd, rb = _team_stats(frame["redTeam"])
    left = Text.assemble(
        (f"{ctx.blue_code}", "bold bright_blue"),
        f"   {bk}킬   {bg:.1f}k   타워 {bt}  바론 {bb}  용 {bd}")
    right = Text.assemble(
        f"용 {rd}  바론 {rb}  타워 {rt}   {rg:.1f}k   {rk}킬   ",
        (f"{ctx.red_code}", "bold red"))
    grid.add_row(left, Text("vs", style="dim"), right)
    return grid


WIDE_DETAIL_MIN = 104  # 이 폭 이상이면 라인별 좌우 비교 레이아웃


def detail_board(ctx: GameContext, detail_frame: dict, width: int = 0) -> Table:
    """선수별 상세. 터미널이 넓으면 라인별 좌우 비교, 좁으면 위아래 나열."""
    if width >= WIDE_DETAIL_MIN:
        return _detail_wide(ctx, detail_frame)
    return _detail_stacked(ctx, detail_frame)


def _detail_table(**kwargs) -> Table:
    """상세 보드 공통 표 스타일: 헤더 밑줄, 세로선 없음, 여백 일정."""
    from rich import box
    # 컬럼 사이 간격은 box.SIMPLE의 구분 공백으로 충분 — 패딩 추가 시 폭 초과
    return Table(box=box.SIMPLE, show_edge=False, pad_edge=False,
                 padding=(0, 0), header_style="dim", **kwargs)


def _detail_stacked(ctx: GameContext, detail_frame: dict) -> Table:
    """세로 나열: 블루 5명 → 레드 5명."""
    by_id = {p["participantId"]: p for p in detail_frame["participants"]}
    table = _detail_table()
    table.add_column("", width=5)
    table.add_column("선수", width=24)
    for h, w in (("KDA", 8), ("Lv", 3), ("CS", 4), ("골드", 6),
                 ("딜%", 4), ("킬%", 4), ("와드", 5)):
        table.add_column(h, width=w, justify="right")
    for pid in range(1, 11):
        p = by_id.get(pid)
        if p is None:
            continue
        side = "blue" if pid <= 5 else "red"
        role = ROLE_KO.get((ctx.roles or {}).get(pid, ""), "")
        name = f"{ctx.names.get(pid, f'#{pid}')}({ctx.champions.get(pid, '?')})"
        table.add_row(
            Text(role, style="dim"),
            Text(name, style=TEAM_STYLE[side]),
            _kda(p), str(p["level"]), str(p["creepScore"]),
            f"{p['totalGoldEarned'] / 1000:.1f}k",
            _pct(p, "championDamageShare"), _pct(p, "killParticipation"),
            f"{p.get('wardsPlaced', 0)}/{p.get('wardsDestroyed', 0)}",
        )
        if pid == 5:
            table.add_section()  # 팀 사이 구분선
    return table


def _detail_wide(ctx: GameContext, detail_frame: dict) -> Table:
    """라인별 좌우 비교: 블루 | 스탯 | 롤 | 스탯 | 레드. 선수명은 양쪽 끝."""
    by_id = {p["participantId"]: p for p in detail_frame["participants"]}
    table = _detail_table()
    stat_cols = (("KDA", 8), ("Lv", 3), ("CS", 4), ("골드", 6), ("딜%", 4))
    table.add_column(Text(ctx.blue_code, style="bold bright_blue"), width=21)
    for h, w in stat_cols:
        table.add_column(h, width=w, justify="right")
    table.add_column("", width=4, justify="center")      # 롤
    for h, w in stat_cols:
        table.add_column(h, width=w, justify="right")
    table.add_column(Text(ctx.red_code, style="bold red"), width=21,
                     justify="right")

    def stats(p):
        if p is None:
            return ("-",) * 5
        return (_kda(p), str(p["level"]), str(p["creepScore"]),
                f"{p['totalGoldEarned'] / 1000:.1f}k",
                _pct(p, "championDamageShare"))

    def name(pid):
        if pid not in by_id and pid not in ctx.names:
            return Text("")
        side = "blue" if pid <= 5 else "red"
        return Text(f"{ctx.names.get(pid, f'#{pid}')}({ctx.champions.get(pid, '?')})",
                    style=TEAM_STYLE[side])

    for i in range(1, 6):
        b_pid, r_pid = i, i + 5
        role = ROLE_KO.get((ctx.roles or {}).get(b_pid, ""), "")
        table.add_row(
            name(b_pid), *stats(by_id.get(b_pid)),
            Text(role, style="dim"),
            *stats(by_id.get(r_pid)), name(r_pid),
        )
    return table


def _kda(p: dict) -> str:
    return f"{p['kills']}/{p['deaths']}/{p['assists']}"


def _pct(p: dict, key: str) -> str:
    return f"{p.get(key, 0) * 100:.0f}%"
