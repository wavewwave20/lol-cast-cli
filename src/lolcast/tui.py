"""Textual 기반 인터랙티브 TUI.

lolcast 하나로 실행 → 홈(경기 목록)에서 단일키 조작으로 라이브/리플레이 중계.
  홈:     ↑↓ 이동 · Enter 선택 · r 새로고침 · q 종료
  세트:   ↑↓/숫자키 선택 · Enter 재생 · q 뒤로
  중계:   휠/↑↓/PgUp 스크롤 · f 자동스크롤 · +/- 배속(리플레이) · q 뒤로
"""
from datetime import datetime, timedelta, timezone

from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, ListItem, ListView, RichLog, Static
from textual.worker import get_current_worker

from . import api, app as cast, render

KST = timezone(timedelta(hours=9))
TAG_WIDTH = 8
STATE_LABEL = {"completed": ("완료", "dim"), "inProgress": ("LIVE", "bold red"),
               "unstarted": ("예정", "yellow")}


def _kst(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
    return dt.strftime("%m/%d %H:%M")


def feed_row(line: render.FeedLine) -> Text:
    row = Text()
    row.append(f"{line.clock:>6}", style="dim")
    row.append("  ")
    row.append(line.tag, style=line.tag_style)
    row.append(" " * max(1, TAG_WIDTH - cell_len(line.tag)))
    row.append_text(line.body)
    return row


class CastScreen(Screen):
    """중계 화면: 고정 스코어보드 + 스크롤 가능한 피드."""

    BINDINGS = [
        Binding("q,escape", "back", "뒤로"),
        Binding("c", "quit_clear", "종료"),
        Binding("f", "toggle_follow", "자동스크롤"),
        Binding("plus,equals_sign", "faster", "배속+"),
        Binding("minus", "slower", "배속-"),
        Binding("end", "to_end", "맨 아래로", show=False),
    ]
    CSS = """
    #scoreboard { height: auto; padding: 0 1; }
    #feed { border-top: solid $panel; padding: 0 1; scrollbar-size-vertical: 1; }
    """

    def __init__(self, source, replay: bool = False, speed: float = 8.0):
        """source(ui, worker): 블로킹 공급 루프 (스레드 워커에서 실행)."""
        super().__init__()
        self._source = source
        self._replay = replay
        self.speed = speed
        self.follow = True
        self._worker = None

    def compose(self) -> ComposeResult:
        yield Static(Text("연결 중...", style="dim"), id="scoreboard")
        yield RichLog(id="feed", auto_scroll=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#feed", RichLog).focus()
        self._worker = self.run_worker(self._work, thread=True)

    def on_unmount(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _work(self) -> None:
        self._source(self, get_current_worker())

    # ---- 워커 스레드에서 호출하는 thread-safe API ----
    def emit(self, lines: list[render.FeedLine]) -> None:
        if lines:
            self.app.call_from_thread(self._emit, lines)

    def update_scoreboard(self, ctx, frame) -> None:
        self.app.call_from_thread(self._scoreboard, ctx, frame)

    def set_status(self, text: str) -> None:
        self.app.call_from_thread(self._status, text)

    # ---- UI 스레드 ----
    def _emit(self, lines) -> None:
        if not self.is_mounted:
            return
        log = self.query_one("#feed", RichLog)
        for line in lines:
            log.write(feed_row(line), scroll_end=self.follow)

    def _scoreboard(self, ctx, frame) -> None:
        if self.is_mounted:
            self.query_one("#scoreboard", Static).update(
                render.scoreboard(ctx, frame))

    def _status(self, text: str) -> None:
        if self.is_mounted:
            self.query_one("#scoreboard", Static).update(
                Text(text, style="yellow"))

    # ---- 액션 ----
    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit_clear(self) -> None:
        # 앱 전체 즉시 종료. cli.main이 result를 보고 터미널을 클리어한다.
        self.app.exit(result="clear")

    def action_toggle_follow(self) -> None:
        self.follow = not self.follow
        if self.follow:
            self.query_one("#feed", RichLog).scroll_end(animate=False)
        self.notify("자동 스크롤 " + ("켜짐" if self.follow else "꺼짐 (f로 재개)"),
                    timeout=2)

    def action_to_end(self) -> None:
        self.follow = True
        self.query_one("#feed", RichLog).scroll_end(animate=False)

    def action_faster(self) -> None:
        self._set_speed(self.speed * 2)

    def action_slower(self) -> None:
        self._set_speed(self.speed / 2)

    def _set_speed(self, value: float) -> None:
        if not self._replay:
            self.notify("배속은 리플레이에서만 돼", timeout=2)
            return
        self.speed = min(256.0, max(1.0, value))
        self.notify(f"배속 x{self.speed:g}", timeout=2)


class GamePickScreen(Screen):
    """완료된 매치의 세트 선택."""

    BINDINGS = [Binding("q,escape", "back", "뒤로")]
    CSS = "#title { padding: 0 1; height: auto; } ListView { padding: 0 1; }"

    def __init__(self, match_event: dict):
        super().__init__()
        self._event = match_event
        self._games: list[dict] = []

    def compose(self) -> ComposeResult:
        teams = " vs ".join(t.get("code", "?")
                            for t in self._event["match"]["teams"])
        self._teams = teams
        yield Static(Text(f"{teams} — 세트 선택", style="bold"), id="title")
        yield ListView(id="games")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load, thread=True)

    def _load(self) -> None:
        detail = api.get_event_details(self._event["match"]["id"])
        games = [g for g in detail["match"]["games"] if g["state"] == "completed"]
        self.app.call_from_thread(self._fill, games)

    def _fill(self, games: list[dict]) -> None:
        self._games = games
        lv = self.query_one("#games", ListView)
        for g in games:
            lv.append(ListItem(Label(f"Game {g['number']}")))
        if not games:
            lv.append(ListItem(Label("완료된 게임 데이터가 없어")))
        lv.index = 0  # 하이라이트가 없으면 Enter 선택 이벤트가 발생하지 않음
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#games", ListView).index or 0
        self._play(idx)

    def on_key(self, event) -> None:
        if event.key.isdigit():
            n = int(event.key)
            for i, g in enumerate(self._games):
                if g["number"] == n:
                    self._play(i)
                    return

    def _play(self, idx: int) -> None:
        if not self._games or idx >= len(self._games):
            return
        g = self._games[idx]
        series = f"{self._teams} · Game {g['number']} (replay)"
        self.app.push_screen(CastScreen(
            lambda ui, worker: cast.replay_source(ui, worker, g["id"], series),
            replay=True))

    def action_back(self) -> None:
        self.app.pop_screen()


class HomeScreen(Screen):
    """홈: 국제대회 경기 목록. Enter로 라이브 중계/리플레이 진입."""

    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("r", "refresh", "새로고침"),
    ]
    CSS = """
    #title { padding: 0 1; height: auto; }
    DataTable { padding: 0 1; }
    """

    def __init__(self):
        super().__init__()
        self._events: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static(Text("lolcast — 국제대회 (KST)", style="bold"), id="title")
        yield DataTable(id="matches", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#matches", DataTable)
        table.add_columns("상태", "시간", "리그", "매치")
        table.focus()
        self.action_refresh()

    def action_refresh(self) -> None:
        self.query_one("#title", Static).update(
            Text("일정 불러오는 중...", style="dim"))
        self.run_worker(self._load, thread=True, exclusive=True)

    def _load(self) -> None:
        events = api.league_events(list(api.INTL_SLUGS))
        live_ids = {e["match"]["id"] for e in api.get_live()
                    if e.get("type") == "match" and "match" in e}
        now = datetime.now(timezone.utc).isoformat()
        past = [e for e in events
                if e["startTime"] < now and e["state"] == "completed"]
        rest = [e for e in events if e not in past]
        rows = past[-8:] + rest
        self.app.call_from_thread(self._fill, rows, live_ids)

    def _fill(self, rows: list[dict], live_ids: set) -> None:
        if not self.is_mounted:
            return
        self.query_one("#title", Static).update(
            Text("lolcast — 국제대회 (KST)  ·  Enter: 중계/리플레이",
                 style="bold"))
        table = self.query_one("#matches", DataTable)
        table.clear()
        self._events = rows
        for i, e in enumerate(rows):
            m = e.get("match", {})
            teams = " vs ".join(t.get("code", "TBD") for t in m.get("teams", []))
            state = e["state"]
            if m.get("id") in live_ids:
                state = "inProgress"
            if state == "completed":
                ws = [str(t.get("result", {}).get("gameWins", ""))
                      for t in m.get("teams", [])]
                teams += f" ({'-'.join(ws)})"
            label, style = STATE_LABEL.get(state, (state, ""))
            e["_state"] = state
            table.add_row(Text(label, style=style), _kst(e["startTime"]),
                          e["_league"], teams, key=str(i))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(event.row_key.value)
        e = self._events[idx]
        state = e.get("_state", e["state"])
        match_id = e.get("match", {}).get("id")
        if state == "inProgress" and match_id:
            self.app.push_screen(CastScreen(
                lambda ui, worker: cast.live_source(ui, worker, match_id)))
        elif state == "completed":
            self.app.push_screen(GamePickScreen(e))
        else:
            self.notify(f"{_kst(e['startTime'])} 시작 예정이야", timeout=3)

    def action_quit(self) -> None:
        self.app.exit()


class LolcastApp(App):
    """진입점. initial 지정 시 홈 대신 바로 중계 화면으로."""

    TITLE = "lolcast"
    # 자체 배경을 칠하지 않고 터미널 기본 배경/전경색을 그대로 사용
    ansi_color = True

    def __init__(self, initial: tuple | None = None):
        super().__init__()
        self._initial = initial

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())
        if self._initial:
            kind, *rest = self._initial
            if kind == "live":
                self.push_screen(CastScreen(
                    lambda ui, worker: cast.live_source(ui, worker, rest[0])))
            elif kind == "replay":
                game_id, speed, series = rest
                self.push_screen(CastScreen(
                    lambda ui, worker: cast.replay_source(
                        ui, worker, game_id, series),
                    replay=True, speed=speed))
