"""프레임 diff 엔진: livestats 프레임 쌍에서 중계 이벤트를 추출한다."""
from dataclasses import dataclass, field


@dataclass
class Event:
    ts: str          # 이벤트를 발생시킨 프레임의 rfc460Timestamp
    kind: str        # kill | execution | dragon | baron | tower | inhibitor | gold | game_state
    team: str | None = None  # "blue" | "red" | None
    data: dict = field(default_factory=dict)


_SIDES = (("blueTeam", "blue"), ("redTeam", "red"))


def diff(prev: dict, new: dict) -> list[Event]:
    events: list[Event] = []
    ts = new["rfc460Timestamp"]

    if prev["gameState"] != new["gameState"]:
        events.append(Event(ts, "game_state", None,
                            {"from": prev["gameState"], "to": new["gameState"]}))

    for key, side in _SIDES:
        p, n = prev[key], new[key]
        if len(n["dragons"]) > len(p["dragons"]):
            events.append(Event(ts, "dragon", side,
                                {"element": n["dragons"][-1], "stack": len(n["dragons"])}))
        if n["barons"] > p["barons"]:
            events.append(Event(ts, "baron", side))
        if n["towers"] > p["towers"]:
            events.append(Event(ts, "tower", side, {"count": n["towers"]}))
        if n["inhibitors"] > p["inhibitors"]:
            events.append(Event(ts, "inhibitor", side, {"count": n["inhibitors"]}))

    events += _kills(prev, new, ts)
    return events


def _kills(prev: dict, new: dict, ts: str) -> list[Event]:
    killers: list[tuple[str, int]] = []   # (side, participantId)
    victims: list[tuple[str, int]] = []
    for key, side in _SIDES:
        for pp, np in zip(prev[key]["participants"], new[key]["participants"]):
            if np["kills"] > pp["kills"]:
                killers.append((side, np["participantId"]))
            if np["deaths"] > pp["deaths"]:
                victims.append((side, np["participantId"]))

    # 이전 프레임까지 양 팀 0킬이었다면 이번 킬이 퍼스트 블러드
    no_kills_yet = (prev["blueTeam"]["totalKills"] == 0
                    and prev["redTeam"]["totalKills"] == 0)

    events = []
    for v_side, v_id in victims:
        killer = next((k for k in killers if k[0] != v_side), None)
        if killer:
            data = {"killer": killer[1], "victim": v_id}
            if no_kills_yet:
                data["first_blood"] = True
                no_kills_yet = False
            events.append(Event(ts, "kill", killer[0], data))
        else:
            events.append(Event(ts, "execution", v_side, {"victim": v_id}))
    return events


def gold_update(frame: dict) -> Event:
    return Event(frame["rfc460Timestamp"], "gold", None,
                 {"blue": frame["blueTeam"]["totalGold"],
                  "red": frame["redTeam"]["totalGold"]})
