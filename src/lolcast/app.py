"""중계 루프: Broadcaster(TUI 상태) + 리플레이/라이브 프레임 공급."""
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from rich.console import Console, Group
from rich.live import Live
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import api, events, render

GOLD_INTERVAL = 60  # 게임시간 기준 골드 현황 주기 (초)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def build_context(window: dict, series: str = "") -> render.GameContext:
    md = window["gameMetadata"]
    champ_ko = api.champion_names_ko()
    codes = {}
    names, champs = {}, {}
    for meta_key in ("blueTeamMetadata", "redTeamMetadata"):
        parts = md[meta_key]["participantMetadata"]
        code = parts[0]["summonerName"].split()[0]
        codes[meta_key] = code
        for p in parts:
            pid = p["participantId"]
            names[pid] = p["summonerName"].removeprefix(code + " ")
            champs[pid] = champ_ko.get(p["championId"], p["championId"])
    return render.GameContext(
        blue_code=codes["blueTeamMetadata"], red_code=codes["redTeamMetadata"],
        names=names, champions=champs, series=series)


class Broadcaster:
    def __init__(self, ctx: render.GameContext, max_feed: int = 300):
        self.ctx = ctx
        self.feed: deque[render.FeedLine] = deque(maxlen=max_feed)
        self.prev: dict | None = None
        self.last_frame: dict | None = None
        self.last_gold_at: float = 0.0  # 게임시간 초
        self.finished = False

    def info(self, text: str) -> None:
        clock = (render.game_clock(self.ctx, self.last_frame["rfc460Timestamp"])
                 if self.last_frame else "")
        self.feed.append(render.info_line(text, clock))

    def process(self, frames: list[dict]) -> None:
        for f in frames:
            if self.ctx.game_start is None and f["gameState"] == "in_game":
                self.ctx.game_start = f["rfc460Timestamp"]
            if self.prev is not None:
                if f["rfc460Timestamp"] <= self.prev["rfc460Timestamp"]:
                    continue  # 윈도우 겹침/중복 프레임 스킵
                for ev in events.diff(self.prev, f):
                    self.feed.append(render.feed_line(self.ctx, ev))
                self._maybe_gold(f)
            if f["gameState"] == "finished":
                self.finished = True
            self.prev = f
            self.last_frame = f

    def _maybe_gold(self, frame: dict) -> None:
        if not self.ctx.game_start:
            return
        elapsed = (_parse(frame["rfc460Timestamp"])
                   - _parse(self.ctx.game_start)).total_seconds()
        if elapsed - self.last_gold_at >= GOLD_INTERVAL:
            self.last_gold_at = elapsed
            self.feed.append(
                render.feed_line(self.ctx, events.gold_update(frame)))

    def renderable(self, height: int):
        body_h = max(3, height - 7)
        lines = list(self.feed)[-body_h:]
        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="right", width=6)   # 시간
        grid.add_column(width=6)                    # 태그
        grid.add_column(ratio=1)                    # 내용
        for i, line in enumerate(lines):
            old = i < len(lines) - 10
            grid.add_row(Text(line.clock, style="dim"),
                         Text(line.tag, style=line.tag_style),
                         line.body,
                         style="dim" if old else None)
        parts = []
        if self.last_frame:
            parts.append(render.scoreboard(self.ctx, self.last_frame))
        parts.append(Rule(style="dim"))
        parts.append(grid)
        return Group(*parts)


def run_replay(game_id: str, speed: float = 8.0, series: str = "") -> None:
    console = Console()
    first = api.get_window(game_id)  # 완료 게임: 첫 윈도우
    if first is None or not first.get("frames"):
        console.print("게임 데이터를 찾을 수 없어.", style="red")
        return
    ctx = build_context(first, series)
    bc = Broadcaster(ctx)
    cursor = _parse(first["frames"][0]["rfc460Timestamp"])
    with Live(console=console, refresh_per_second=4, screen=False) as live:
        bc.process(first["frames"])
        while not bc.finished:
            cursor += timedelta(seconds=10)
            win = api.get_window(game_id, api.align_ts(cursor))
            if win and win.get("frames"):
                # 종료 후엔 같은 마지막 윈도우가 반복 반환됨 → 진행 없으면 종료 처리
                new_last = win["frames"][-1]["rfc460Timestamp"]
                if bc.prev and new_last <= bc.prev["rfc460Timestamp"]:
                    bc.finished = True
                bc.process(win["frames"])
            live.update(bc.renderable(console.size.height))
            time.sleep(10.0 / speed)
        live.update(bc.renderable(console.size.height))
    console.print("중계 종료", style="bold")


def run_live(match_id: str, poll: float = 10.0) -> None:
    console = Console()
    detail = api.get_event_details(match_id)
    teams = " vs ".join(t["code"] for t in detail["match"]["teams"])
    with Live(console=console, refresh_per_second=4, screen=False) as live:
        while True:
            game = _current_game(match_id)
            if game is None:
                break
            _broadcast_live_game(game, teams, live, console, poll)
    console.print(f"{teams} 매치 종료", style="bold")


def _current_game(match_id: str) -> dict | None:
    detail = api.get_event_details(match_id)
    teams = " vs ".join(t["code"] for t in detail["match"]["teams"])
    for g in detail["match"]["games"]:
        if g["state"] in ("inProgress", "unstarted"):
            g["_series"] = f"{teams} · Game {g['number']}"
            return g
    return None


def _broadcast_live_game(game: dict, teams: str, live, console, poll: float) -> None:
    game_id = game["id"]
    bc: Broadcaster | None = None
    while True:
        win = api.get_window(game_id)
        if win is None or not win.get("frames"):
            live.update(Text(
                f"{teams} · Game {game['number']} 시작 대기 중...",
                style="yellow"))
            time.sleep(poll)
            continue
        if bc is None:
            ctx = build_context(win, game.get("_series", ""))
            ctx.game_start = api.find_game_start(
                game_id, datetime.now(timezone.utc) - timedelta(hours=3))
            bc = Broadcaster(ctx)
            bc.info(f"{ctx.series} 중계 시작")
        bc.process(win["frames"])
        live.update(bc.renderable(console.size.height))
        if bc.finished:
            bc.info("다음 게임 확인 중...")
            live.update(bc.renderable(console.size.height))
            time.sleep(30)
            return
        time.sleep(poll)
