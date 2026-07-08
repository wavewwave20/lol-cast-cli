from lolcast.events import Event
from lolcast.render import GameContext, feed_line, game_clock, gold_bar


def make_ctx():
    return GameContext(
        blue_code="T1", red_code="FUR",
        names={1: "Faker", 6: "Tutsz"},
        champions={1: "아지르", 6: "탈리야"},
        game_start="2026-07-06T06:00:00.000Z",
    )


def test_game_clock():
    ctx = make_ctx()
    assert game_clock(ctx, "2026-07-06T06:25:01.000Z") == "25:01"
    assert game_clock(ctx, "2026-07-06T07:05:09.500Z") == "65:09"


def test_kill_line():
    ev = Event("2026-07-06T06:25:01.000Z", "kill", "blue",
               {"killer": 1, "victim": 6})
    line = feed_line(make_ctx(), ev)
    assert line.clock == "25:01"
    assert line.tag == "킬"
    assert line.body.plain == "Faker(아지르) → Tutsz(탈리야)"


def test_dragon_line_korean_element():
    ev = Event("2026-07-06T06:25:01.000Z", "dragon", "red",
               {"element": "infernal", "stack": 2})
    line = feed_line(make_ctx(), ev)
    assert line.tag == "용"
    assert line.body.plain == "FUR 화염 드래곤 (2스택)"


def test_gold_line():
    ev = Event("2026-07-06T06:25:01.000Z", "gold", None,
               {"blue": 52000, "red": 48700})
    line = feed_line(make_ctx(), ev)
    assert line.tag == "골드"
    assert line.body.plain == "T1 +3.3k (52.0 : 48.7)"


def test_game_end_line():
    ev = Event("2026-07-06T06:25:01.000Z", "game_state", None,
               {"from": "in_game", "to": "finished"})
    line = feed_line(make_ctx(), ev)
    assert line.tag == "종료"
    assert line.body.plain == "게임 종료"


def test_gold_bar_leans_toward_leader():
    bar = gold_bar(make_ctx(), blue=60000, red=40000, width=20)
    assert bar.plain.count("▓") == 12  # 60% of 20
    assert bar.plain.count("░") == 8


def test_first_blood_line():
    ev = Event("2026-07-06T06:25:01.000Z", "kill", "blue",
               {"killer": 1, "victim": 6, "first_blood": True})
    line = feed_line(make_ctx(), ev)
    assert line.tag == "퍼블"


def test_detail_board():
    from lolcast.render import detail_board
    ctx = make_ctx()
    ctx.roles = {1: "mid", 6: "mid"}
    detail = {"participants": [
        {"participantId": 1, "kills": 3, "deaths": 1, "assists": 5, "level": 14,
         "creepScore": 210, "totalGoldEarned": 10200,
         "championDamageShare": 0.23, "killParticipation": 0.5,
         "wardsPlaced": 8, "wardsDestroyed": 2},
        {"participantId": 6, "kills": 1, "deaths": 3, "assists": 2, "level": 12,
         "creepScore": 180, "totalGoldEarned": 8100,
         "championDamageShare": 0.18, "killParticipation": 0.4,
         "wardsPlaced": 5, "wardsDestroyed": 1},
    ]}
    table = detail_board(ctx, detail)
    assert table.row_count == 3  # 헤더 + 선수 2명


def test_detail_board_wide_pairs_lanes():
    from lolcast.render import detail_board
    ctx = make_ctx()
    ctx.roles = {1: "mid", 6: "mid"}
    detail = {"participants": [
        {"participantId": 1, "kills": 3, "deaths": 1, "assists": 5, "level": 14,
         "creepScore": 210, "totalGoldEarned": 10200,
         "championDamageShare": 0.23, "killParticipation": 0.5,
         "wardsPlaced": 8, "wardsDestroyed": 2},
        {"participantId": 6, "kills": 1, "deaths": 3, "assists": 2, "level": 12,
         "creepScore": 180, "totalGoldEarned": 8100,
         "championDamageShare": 0.18, "killParticipation": 0.4,
         "wardsPlaced": 5, "wardsDestroyed": 1},
    ]}
    table = detail_board(ctx, detail, width=120)  # wide: 헤더 + 라인 5줄
    assert table.row_count == 6
    table2 = detail_board(ctx, detail, width=80)  # narrow: 헤더 + 선수 2줄
    assert table2.row_count == 3


def test_dragons_str_one_emoji_per_take():
    from lolcast.render import _dragons_str
    assert _dragons_str(["hextech", "hextech", "hextech"]) == "⚡⚡⚡"
    assert _dragons_str(["ocean", "infernal"]) == "🌊🔥"
    assert _dragons_str([]) == "-"


def test_kill_line_with_assists():
    ctx = make_ctx()
    ctx.champions[2] = "트런들"
    ev = Event("2026-07-06T06:25:01.000Z", "kill", "blue",
               {"killer": 1, "victim": 6, "assists": [2]})
    line = feed_line(ctx, ev)
    assert line.body.plain == "Faker(아지르) → Tutsz(탈리야)  (어시 트런들)"
