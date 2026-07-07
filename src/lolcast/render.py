"""이벤트 → 담백한 정보형 한 줄 텍스트, 스코어보드 렌더링."""
from dataclasses import dataclass
from datetime import datetime

from rich.table import Table
from rich.text import Text

from .events import Event

DRAGON_KO = {
    "ocean": "바다", "mountain": "대지", "infernal": "화염", "cloud": "바람",
    "hextech": "마공학", "chemtech": "화학공학", "elder": "장로",
}
STATE_KO = {
    "in_game": "게임 진행 중", "paused": "일시 정지", "finished": "게임 종료",
}


@dataclass
class GameContext:
    blue_code: str
    red_code: str
    names: dict[int, str]        # participantId -> "T1 Faker"
    champions: dict[int, str]    # participantId -> championId
    game_start: str | None = None  # 첫 in_game 프레임의 rfc460Timestamp
    series: str = ""             # 예: "T1 vs FUR — Game 2"


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


def format_event(ctx: GameContext, ev: Event) -> str:
    clock = game_clock(ctx, ev.ts)
    t = _team_code(ctx, ev.team)
    d = ev.data
    match ev.kind:
        case "kill":
            return f"⚔️ [{clock}] {_who(ctx, d['killer'])} → {_who(ctx, d['victim'])} 킬"
        case "execution":
            return f"💀 [{clock}] {_who(ctx, d['victim'])} 사망 (처형)"
        case "dragon":
            elem = DRAGON_KO.get(d["element"], d["element"])
            return f"🐉 [{clock}] {t} {elem} 드래곤 처치 ({d['stack']}스택)"
        case "baron":
            return f"👹 [{clock}] {t} 바론 처치"
        case "tower":
            return f"🏰 [{clock}] {t} 타워 파괴 ({d['count']}번째)"
        case "inhibitor":
            return f"💥 [{clock}] {t} 억제기 파괴 ({d['count']}번째)"
        case "gold":
            gap = d["blue"] - d["red"]
            leader = ctx.blue_code if gap >= 0 else ctx.red_code
            return (f"💰 [{clock}] 골드: {leader} +{abs(gap) / 1000:.1f}k "
                    f"({d['blue'] / 1000:.1f}k : {d['red'] / 1000:.1f}k)")
        case "game_state":
            if d["to"] == "finished":
                return f"🏁 [{clock}] 게임 종료"
            if d["to"] == "paused":
                return f"⏸️ [{clock}] 경기 일시 정지"
            if d["from"] == "paused":
                return f"▶️ [{clock}] 경기 재개"
            return f"ℹ️ [{clock}] {STATE_KO.get(d['to'], d['to'])}"
        case _:
            return f"ℹ️ [{clock}] {ev.kind}"


def scoreboard(ctx: GameContext, frame: dict) -> Table:
    """상단 고정 스코어보드. rich Table 반환."""
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="right")
    clock = game_clock(ctx, frame["rfc460Timestamp"])
    for key, side, emoji, style in (
        ("blueTeam", "blue", "🔵", "bold blue"),
        ("redTeam", "red", "🔴", "bold red"),
    ):
        tm = frame[key]
        dragons = "".join("🐉" for _ in tm["dragons"]) or "-"
        line = Text.assemble(
            (f"{emoji} {_team_code(ctx, side):<4}", style),
            f" ⚔️{tm['totalKills']:>2}  💰{tm['totalGold'] / 1000:.1f}k"
            f"  🏰{tm['towers']}  👹{tm['barons']}  {dragons}",
        )
        right = f"⏱ {clock}" if side == "blue" else (ctx.series or "")
        table.add_row(line, right)
    return table
