"""lolcast CLI 진입점. 인자 없이 실행하면 인터랙티브 TUI."""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import api
from .tui import LolcastApp

KST = timezone(timedelta(hours=9))
STATE_LABEL = {"completed": ("완료", "dim"), "inProgress": ("LIVE", "bold red"),
               "unstarted": ("예정", "yellow")}


def _kst(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
    return dt.strftime("%m/%d %H:%M")


def cmd_schedule(args) -> None:
    console = Console()
    events = api.league_events(args.league.split(","))
    now = datetime.now(timezone.utc).isoformat()
    # 최근 완료 5개 + 이후 전부
    past = [e for e in events if e["startTime"] < now and e["state"] == "completed"]
    rest = [e for e in events if e not in past]
    rows = past[-5:] + rest
    table = Table(title="국제대회 일정 (KST)", title_style="bold",
                  header_style="dim", border_style="dim")
    for col in ("시간", "리그", "매치", "상태", "matchId"):
        table.add_column(col)
    for e in rows:
        m = e.get("match", {})
        teams = " vs ".join(t.get("code", "TBD") for t in m.get("teams", []))
        result = ""
        if e["state"] == "completed":
            ws = [str(t.get("result", {}).get("gameWins", "")) for t in m.get("teams", [])]
            result = f" ({'-'.join(ws)})"
        label, style = STATE_LABEL.get(e["state"], (e["state"], ""))
        table.add_row(_kst(e["startTime"]), e["_league"], teams + result,
                      Text(label, style=style), Text(m.get("id", ""), style="dim"))
    console.print(table)


def cmd_watch(args) -> None:
    console = Console()
    live = [e for e in api.get_live() if e.get("type") == "match"]
    slugs = set(args.league.split(","))
    live = [e for e in live if e.get("league", {}).get("slug") in slugs] or live
    if not live:
        console.print("지금 라이브 경기가 없어. 다음 예정 경기:")
        events = api.league_events(sorted(slugs))
        now = datetime.now(timezone.utc).isoformat()
        for e in [e for e in events if e["startTime"] > now][:3]:
            teams = " vs ".join(t.get("code", "TBD")
                                for t in e.get("match", {}).get("teams", []))
            # [msi] 같은 대괄호가 rich 마크업으로 해석되지 않도록 markup=False
            console.print(f"  {_kst(e['startTime'])} [{e['_league']}] {teams}",
                          markup=False, style="dim")
        return
    if len(live) > 1:
        for i, e in enumerate(live, 1):
            teams = " vs ".join(t["code"] for t in e["match"]["teams"])
            console.print(f"  {i}. [{e['league']['slug']}] {teams}", markup=False)
        idx = int(input("중계할 경기 번호: ")) - 1
    else:
        idx = 0
    _run_app(LolcastApp(initial=("live", live[idx]["match"]["id"])))


def cmd_replay(args) -> None:
    console = Console()
    if args.query.isdigit() and len(args.query) > 12:
        _run_app(LolcastApp(initial=("replay", args.query, args.speed, "")))
        return
    events = api.league_events(list(api.INTL_SLUGS))
    q = args.query.lower()
    done = [e for e in events if e["state"] == "completed"
            and any(q in (t.get("code", "") + t.get("name", "")).lower()
                    for t in e.get("match", {}).get("teams", []))]
    if not done:
        console.print(f"'{args.query}' 완료 경기를 못 찾았어.", style="red")
        sys.exit(1)
    e = done[-1]
    teams = " vs ".join(t["code"] for t in e["match"]["teams"])
    detail = api.get_event_details(e["match"]["id"])
    games = [g for g in detail["match"]["games"] if g["state"] == "completed"]
    if not games:
        console.print(f"{teams}: 완료된 게임 데이터가 없어.", style="red")
        sys.exit(1)
    g = games[args.game - 1] if 0 < args.game <= len(games) else games[-1]
    series = f"{teams} · Game {g['number']} (replay)"
    # 확정 가능한 승자: 마지막 게임=매치 승자, 스윕이면 전 게임
    wins = [t.get("result", {}).get("gameWins", 0) for t in e["match"]["teams"]]
    winner_code = None
    if wins[0] != wins[1] and (g is games[-1] or min(wins) == 0):
        winner_code = e["match"]["teams"][0 if wins[0] > wins[1] else 1].get("code")
    _run_app(LolcastApp(initial=("replay", g["id"], args.speed, series,
                                 winner_code)))


GIT_URL = "git+https://github.com/wavewwave20/lol-cast-cli.git"


def _version() -> str:
    try:
        return version("lol-cast-cli")
    except PackageNotFoundError:
        return "dev"


def cmd_update(args) -> None:
    console = Console()
    prefix = str(Path(sys.prefix))
    if "uv/tools" in prefix or "uv\\tools" in prefix:
        cmd = ["uv", "tool", "install", "--force", GIT_URL]
    elif "pipx" in prefix:
        cmd = ["pipx", "install", "--force", GIT_URL]
    elif shutil.which("uv"):
        cmd = ["uv", "tool", "install", "--force", GIT_URL]
    elif shutil.which("pipx"):
        cmd = ["pipx", "install", "--force", GIT_URL]
    else:
        console.print("uv나 pipx를 못 찾았어. 수동으로 업데이트해줘:", style="red")
        console.print(f"  pip install --upgrade {GIT_URL}", style="dim")
        sys.exit(1)
    console.print(f"현재 버전: {_version()}", style="dim")
    console.print("$ " + " ".join(cmd), style="dim")
    if sys.platform == "win32":
        # 윈도우는 실행 중인 lolcast.exe가 잠겨 있어 이 프로세스가 살아있는 동안
        # 교체가 불가(WinError 32). 새 콘솔에서 잠깐 기다렸다 업데이트하게 하고
        # 즉시 종료해서 잠금을 푼다.
        script = ("timeout /t 3 /nobreak >nul & " + " ".join(cmd)
                  + " & echo. & echo === lolcast update complete === & pause")
        subprocess.Popen(["cmd", "/c", script],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        console.print("새 콘솔 창에서 업데이트를 계속할게. 이 창은 닫아도 돼.",
                      style="bold green")
        sys.exit(0)
    result = subprocess.run(cmd)
    if result.returncode == 0:
        console.print("업데이트 완료. 새 버전은 다음 실행부터 적용돼.", style="bold green")
    sys.exit(result.returncode)


def _run_app(app: LolcastApp) -> None:
    """앱 실행. c(종료+클리어)로 나오면 터미널을 지운다."""
    if app.run() == "clear":
        Console().clear()  # rich가 윈도우 포함 플랫폼별 클리어 처리


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lolcast",
        description="LoL 이스포츠 CLI 텍스트 중계 — 인자 없이 실행하면 인터랙티브 모드")
    parser.add_argument("--version", action="version",
                        version=f"lol-cast-cli {_version()}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("schedule", help="경기 일정 출력")
    p.add_argument("--league", default="first_stand,msi,worlds")
    p.set_defaults(func=cmd_schedule)

    p = sub.add_parser("watch", help="라이브 중계 바로 시작")
    p.add_argument("--league", default="first_stand,msi,worlds")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("replay", help="지난 경기 리플레이 바로 시작")
    p.add_argument("query", help="팀 검색어 또는 gameId")
    p.add_argument("--speed", type=float, default=8.0)
    p.add_argument("--game", type=int, default=0, help="세트 번호 (기본: 마지막)")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("update", help="lolcast 최신 버전으로 업데이트")
    p.set_defaults(func=cmd_update)

    args = parser.parse_args()
    try:
        if args.command is None:
            _run_app(LolcastApp())
        else:
            args.func(args)
    except KeyboardInterrupt:
        print("\n중계 종료")


if __name__ == "__main__":
    main()
