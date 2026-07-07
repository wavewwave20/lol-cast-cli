import json
from pathlib import Path

from lolcast.events import Event, diff, gold_update

FIXTURES = Path(__file__).parent / "fixtures"


def team(kills=0, gold=0, towers=0, inhibs=0, barons=0, dragons=None, parts=None):
    return {
        "totalGold": gold, "inhibitors": inhibs, "towers": towers,
        "barons": barons, "totalKills": kills, "dragons": dragons or [],
        "participants": parts or [],
    }


def part(pid, kills=0, deaths=0, assists=0):
    return {"participantId": pid, "kills": kills, "deaths": deaths,
            "assists": assists, "totalGold": 500, "level": 1,
            "creepScore": 0, "currentHealth": 1000, "maxHealth": 1000}


def frame(blue, red, ts="2026-07-06T06:25:01.000Z", state="in_game"):
    return {"rfc460Timestamp": ts, "gameState": state,
            "blueTeam": blue, "redTeam": red}


def test_no_change_no_events():
    f = frame(team(parts=[part(1)]), team(parts=[part(6)]))
    assert diff(f, f) == []


def test_kill_attribution():
    prev = frame(team(kills=0, parts=[part(1)]), team(parts=[part(6)]))
    new = frame(team(kills=1, parts=[part(1, kills=1)]),
                team(parts=[part(6, deaths=1)]))
    evs = diff(prev, new)
    assert len(evs) == 1
    assert evs[0].kind == "kill"
    assert evs[0].team == "blue"
    assert evs[0].data == {"killer": 1, "victim": 6}


def test_death_without_killer_is_execution():
    prev = frame(team(parts=[part(1)]), team(parts=[part(6)]))
    new = frame(team(parts=[part(1)]), team(parts=[part(6, deaths=1)]))
    evs = diff(prev, new)
    assert evs[0].kind == "execution"
    assert evs[0].team == "red"
    assert evs[0].data == {"victim": 6}


def test_dragon_baron_tower_inhibitor():
    prev = frame(team(), team(dragons=["cloud"]))
    new = frame(team(towers=1, barons=1, inhibs=1),
                team(dragons=["cloud", "infernal"]))
    kinds = {(e.kind, e.team) for e in diff(prev, new)}
    assert kinds == {("dragon", "red"), ("baron", "blue"),
                     ("tower", "blue"), ("inhibitor", "blue")}
    dragon = next(e for e in diff(prev, new) if e.kind == "dragon")
    assert dragon.data == {"element": "infernal", "stack": 2}


def test_game_state_transition():
    prev = frame(team(), team(), state="in_game")
    new = frame(team(), team(), state="finished")
    evs = diff(prev, new)
    assert evs[0].kind == "game_state"
    assert evs[0].data == {"from": "in_game", "to": "finished"}


def test_gold_update():
    f = frame(team(gold=52000), team(gold=48700))
    ev = gold_update(f)
    assert ev.kind == "gold"
    assert ev.data == {"blue": 52000, "red": 48700}


def test_real_fixture_kill():
    """T1 vs FUR 실경기 윈도우: 06:25:01에 블루팀 9->10킬."""
    frames = json.loads((FIXTURES / "window_kill.json").read_text())["frames"]
    all_events = []
    for prev, new in zip(frames, frames[1:]):
        all_events += diff(prev, new)
    kills = [e for e in all_events if e.kind == "kill"]
    assert len(kills) == 1
    assert kills[0].team == "blue"
    assert 1 <= kills[0].data["killer"] <= 5
    assert 6 <= kills[0].data["victim"] <= 10
