"""중계 로직: Broadcaster(프레임 → 피드 라인 축적) + 리플레이/라이브 공급 루프.

UI에 독립적이다. 공급 루프는 ui 객체(thread-safe API: emit/update_scoreboard/
set_status, 속성 speed)와 worker(is_cancelled)를 받아 동작한다.
"""
import time
from datetime import datetime, timedelta, timezone

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
    """프레임을 소비해 피드 라인을 쌓는다. UI가 take()로 가져간다."""

    def __init__(self, ctx: render.GameContext):
        self.ctx = ctx
        self.pending: list[render.FeedLine] = []
        self.prev: dict | None = None
        self.last_frame: dict | None = None
        self.last_gold_at: float = 0.0  # 게임시간 초
        self.finished = False

    def info(self, text: str) -> None:
        clock = (render.game_clock(self.ctx, self.last_frame["rfc460Timestamp"])
                 if self.last_frame else "")
        self.pending.append(render.info_line(text, clock))

    def take(self) -> list[render.FeedLine]:
        out, self.pending = self.pending, []
        return out

    def process(self, frames: list[dict]) -> None:
        for f in frames:
            if self.ctx.game_start is None and f["gameState"] == "in_game":
                self.ctx.game_start = f["rfc460Timestamp"]
            if self.prev is not None:
                if f["rfc460Timestamp"] <= self.prev["rfc460Timestamp"]:
                    continue  # 윈도우 겹침/중복 프레임 스킵
                for ev in events.diff(self.prev, f):
                    self.pending.append(render.feed_line(self.ctx, ev))
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
            self.pending.append(
                render.feed_line(self.ctx, events.gold_update(frame)))


def _sleep(worker, secs: float) -> bool:
    """취소 가능 sleep. 취소되면 False."""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if worker.is_cancelled:
            return False
        time.sleep(min(0.2, max(0.0, end - time.monotonic())))
    return not worker.is_cancelled


def _flush(ui, bc: Broadcaster) -> None:
    ui.emit(bc.take())
    if bc.last_frame:
        ui.update_scoreboard(bc.ctx, bc.last_frame)


def replay_source(ui, worker, game_id: str, series: str = "") -> None:
    """완료된 게임을 처음부터 재생. ui.speed를 매 스텝 반영 (+/- 배속)."""
    ui.set_status("게임 데이터 불러오는 중...")
    first = api.get_window(game_id)  # 완료 게임: 첫 윈도우
    if first is None or not first.get("frames"):
        ui.set_status("게임 데이터를 찾을 수 없어. q 로 뒤로.")
        return
    ctx = build_context(first, series)
    bc = Broadcaster(ctx)
    cursor = _parse(first["frames"][0]["rfc460Timestamp"])
    bc.process(first["frames"])
    _flush(ui, bc)
    while not bc.finished:
        cursor += timedelta(seconds=10)
        win = api.get_window(game_id, api.align_ts(cursor))
        if win and win.get("frames"):
            # 종료 후엔 같은 마지막 윈도우가 반복 반환됨 → 진행 없으면 종료 처리
            new_last = win["frames"][-1]["rfc460Timestamp"]
            if bc.prev and new_last <= bc.prev["rfc460Timestamp"]:
                bc.finished = True
            bc.process(win["frames"])
            _flush(ui, bc)
        if not _sleep(worker, 10.0 / max(0.5, ui.speed)):
            return
    bc.info("중계 종료 — q 로 뒤로")
    _flush(ui, bc)


def live_source(ui, worker, match_id: str, poll: float = 10.0) -> None:
    """라이브 매치 중계. 세트 종료 시 다음 게임으로 자동 전환."""
    ui.set_status("매치 정보 불러오는 중...")
    detail = api.get_event_details(match_id)
    teams = " vs ".join(t["code"] for t in detail["match"]["teams"])
    done: set[str] = set()  # 종료를 본 게임 id (API 상태 갱신 지연 대응)
    while not worker.is_cancelled:
        game = _current_game(match_id)
        if game is None:
            ui.set_status(f"{teams} 매치 종료 — q 로 뒤로")
            return
        if game["id"] in done:
            ui.set_status(f"{teams} — 다음 게임 대기 중...")
            if not _sleep(worker, 15):
                return
            continue
        if not _broadcast_live_game(ui, worker, game, teams, poll):
            return
        done.add(game["id"])


def _current_game(match_id: str) -> dict | None:
    detail = api.get_event_details(match_id)
    teams = " vs ".join(t["code"] for t in detail["match"]["teams"])
    for g in detail["match"]["games"]:
        if g["state"] in ("inProgress", "unstarted"):
            g["_series"] = f"{teams} · Game {g['number']}"
            return g
    return None


def _broadcast_live_game(ui, worker, game: dict, teams: str, poll: float) -> bool:
    """라이브 게임 스트리밍.

    livestats는 startingTime 없이 요청하면 (라이브 게임이라도) 첫 윈도우를
    반환하므로, 첫 윈도우로 게임 시작 시각만 얻고 now-60s부터 10초 윈도우
    커서를 전진시키며 실시간을 따라간다. startingTime은 now-45s 이전이어야
    하므로(400), 따라잡으면 다음 윈도우가 유효해질 때까지 대기한다.
    """
    game_id = game["id"]
    bc: Broadcaster | None = None
    cursor: datetime | None = None
    while not worker.is_cancelled:
        if bc is None:
            first = api.get_window(game_id)  # 라이브도 첫 윈도우가 온다
            if first is None or not first.get("frames"):
                ui.set_status(f"{teams} · Game {game['number']} 시작 대기 중...")
                if not _sleep(worker, poll):
                    return False
                continue
            ctx = build_context(first, game.get("_series", ""))
            start_frame = next(
                (f for f in first["frames"] if f["gameState"] == "in_game"),
                first["frames"][0])
            ctx.game_start = start_frame["rfc460Timestamp"]
            bc = Broadcaster(ctx)
            bc.info(f"{ctx.series} 실시간 중계 합류")
            _flush(ui, bc)
            cursor = max(
                _parse(ctx.game_start),
                datetime.now(timezone.utc) - timedelta(seconds=60),
            ) - timedelta(seconds=10)

        cursor += timedelta(seconds=10)
        latest_allowed = datetime.now(timezone.utc) - timedelta(seconds=50)
        if cursor > latest_allowed:
            # 실시간까지 따라잡음 → 다음 윈도우가 유효해질 때까지 대기
            wait = (cursor - latest_allowed).total_seconds()
            cursor -= timedelta(seconds=10)
            if not _sleep(worker, min(poll, max(1.0, wait))):
                return False
            continue

        win = api.get_window(game_id, api.align_ts(cursor))
        if win and win.get("frames"):
            bc.process(win["frames"])
            _flush(ui, bc)
            last = _parse(win["frames"][-1]["rfc460Timestamp"])
            if last > cursor:
                cursor = last
        if bc.finished:
            bc.info("게임 종료 — 다음 게임 확인 중...")
            _flush(ui, bc)
            return _sleep(worker, 30)
        if not _sleep(worker, 0.3):  # 따라잡기 중 빠른 전진 (실시간이면 위에서 대기)
            return False
    return False
