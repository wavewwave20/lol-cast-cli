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
TEAM_STYLE = {"blue": "bold bright_blue", "red": "bold red"}


@dataclass
class GameContext:
    blue_code: str
    red_code: str
    names: dict[int, str]        # participantId -> "Faker" (팀 접두어 제거)
    champions: dict[int, str]    # participantId -> 챔피언 한글명
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
                return FeedLine(clock, "종료", "bold", Text("게임 종료", style="bold"))
            if d["to"] == "paused":
                return FeedLine(clock, "중지", "dim", Text("경기 일시 정지"))
            if d["from"] == "paused":
                return FeedLine(clock, "재개", "dim", Text("경기 재개"))
            return info_line(d["to"], clock)
        case _:
            return info_line(ev.kind, clock)


def gold_bar(ctx: GameContext, blue: int, red: int, width: int = 20) -> Text:
    total = blue + red
    filled = round(width * (blue / total)) if total else width // 2
    return Text.assemble(
        (ctx.blue_code + " ", TEAM_STYLE["blue"]),
        ("▓" * filled, "bright_blue"),
        ("░" * (width - filled), "red"),
        (" " + ctx.red_code, TEAM_STYLE["red"]),
    )


def scoreboard(ctx: GameContext, frame: dict) -> Table:
    """상단 스코어보드: 제목/시계, 팀 지표 2줄, 골드 우위 바."""
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right")

    title = ctx.series or f"{ctx.blue_code} vs {ctx.red_code}"
    clock = game_clock(ctx, frame["rfc460Timestamp"])
    grid.add_row(Text(title, style="dim"), Text(clock, style="bold"))

    for key, side in (("blueTeam", "blue"), ("redTeam", "red")):
        tm = frame[key]
        stats = (f"{tm['totalKills']:>2}킬   {tm['totalGold'] / 1000:>5.1f}k   "
                 f"타워 {tm['towers']:<2}  용 {len(tm['dragons'])}  바론 {tm['barons']}")
        grid.add_row(Text.assemble(
            (f"{_team_code(ctx, side):<5}", TEAM_STYLE[side]), stats), "")

    blue_g, red_g = frame["blueTeam"]["totalGold"], frame["redTeam"]["totalGold"]
    gap = blue_g - red_g
    side = "blue" if gap >= 0 else "red"
    label = Text(f"+{abs(gap) / 1000:.1f}k", style=TEAM_STYLE[side])
    grid.add_row(gold_bar(ctx, blue_g, red_g), label)
    return grid
