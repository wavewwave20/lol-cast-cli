"""lolesports 비공식 API 클라이언트."""
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
PERSISTED = "https://esports-api.lolesports.com/persisted/gw"
FEED = "https://feed.lolesports.com/livestats/v1"
INTL_SLUGS = ("first_stand", "msi", "worlds")

_session = requests.Session()
_session.headers["x-api-key"] = API_KEY


def align_ts(dt: datetime) -> str:
    """livestats startingTime용: 10초 배수로 내림, ISO8601 Z 포맷."""
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    dt -= timedelta(seconds=dt.second % 10)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, params: dict | None = None, retries: int = 5):
    """GET + 지수 백오프. 204는 None 반환."""
    delay = 2.0
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=15)
            if r.status_code == 204:
                return None
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(min(delay, 60))
            delay *= 2


def get_leagues() -> list[dict]:
    d = _get(f"{PERSISTED}/getLeagues", {"hl": "ko-KR"})
    return d["data"]["leagues"]


def intl_league_ids() -> dict[str, str]:
    """{slug: leagueId} — first_stand/msi/worlds만."""
    return {lg["slug"]: lg["id"] for lg in get_leagues() if lg["slug"] in INTL_SLUGS}


def get_schedule(league_id: str) -> list[dict]:
    d = _get(f"{PERSISTED}/getSchedule", {"hl": "ko-KR", "leagueId": league_id})
    return d["data"]["schedule"]["events"]


def league_events(slugs: list[str]) -> list[dict]:
    """지정한 리그들의 일정을 시간순 병합. 각 이벤트에 _league 슬러그 부착."""
    ids = intl_league_ids()
    events = []
    for slug in slugs:
        if slug not in ids:
            continue
        for e in get_schedule(ids[slug]):
            e["_league"] = slug
            events.append(e)
    events.sort(key=lambda e: e["startTime"])
    return events


def get_live() -> list[dict]:
    d = _get(f"{PERSISTED}/getLive", {"hl": "ko-KR"})
    return d["data"]["schedule"]["events"]


def get_event_details(match_id: str) -> dict:
    d = _get(f"{PERSISTED}/getEventDetails", {"hl": "ko-KR", "id": match_id})
    return d["data"]["event"]


def get_window(game_id: str, starting_time: str | None = None) -> dict | None:
    params = {"startingTime": starting_time} if starting_time else None
    return _get(f"{FEED}/window/{game_id}", params)


def get_details(game_id: str, starting_time: str | None = None) -> dict | None:
    """선수별 상세 프레임 (KDA/CS/딜지분/와드/아이템 등)."""
    params = {"startingTime": starting_time} if starting_time else None
    return _get(f"{FEED}/details/{game_id}", params)


_champ_ko: dict[str, str] | None = None


def champion_names_ko() -> dict[str, str]:
    """Data Dragon에서 {영문 챔피언 id: 한글명} 매핑. 실패 시 빈 dict (영문 표기 폴백)."""
    global _champ_ko
    if _champ_ko is None:
        try:
            vers = _get("https://ddragon.leagueoflegends.com/api/versions.json",
                        retries=1)
            data = _get("https://ddragon.leagueoflegends.com/cdn/"
                        f"{vers[0]}/data/ko_KR/champion.json", retries=1)
            _champ_ko = {k: v["name"] for k, v in data["data"].items()}
        except Exception:
            _champ_ko = {}
    return _champ_ko
