from lolcast.events import Event
from lolcast.render import GameContext, format_event, game_clock


def make_ctx():
    return GameContext(
        blue_code="T1", red_code="FUR",
        names={1: "T1 Faker", 6: "FUR Tutsz"},
        champions={1: "Azir", 6: "Taliyah"},
        game_start="2026-07-06T06:00:00.000Z",
    )


def test_game_clock():
    ctx = make_ctx()
    assert game_clock(ctx, "2026-07-06T06:25:01.000Z") == "25:01"
    assert game_clock(ctx, "2026-07-06T07:05:09.500Z") == "65:09"


def test_format_kill():
    ev = Event("2026-07-06T06:25:01.000Z", "kill", "blue",
               {"killer": 1, "victim": 6})
    assert format_event(make_ctx(), ev) == \
        "⚔️ [25:01] T1 Faker(Azir) → FUR Tutsz(Taliyah) 킬"


def test_format_dragon_korean_element():
    ev = Event("2026-07-06T06:25:01.000Z", "dragon", "red",
               {"element": "infernal", "stack": 2})
    assert format_event(make_ctx(), ev) == "🐉 [25:01] FUR 화염 드래곤 처치 (2스택)"


def test_format_gold():
    ev = Event("2026-07-06T06:25:01.000Z", "gold", None,
               {"blue": 52000, "red": 48700})
    assert format_event(make_ctx(), ev) == "💰 [25:01] 골드: T1 +3.3k (52.0k : 48.7k)"


def test_format_game_state():
    ev = Event("2026-07-06T06:25:01.000Z", "game_state", None,
               {"from": "in_game", "to": "finished"})
    assert format_event(make_ctx(), ev) == "🏁 [25:01] 게임 종료"
