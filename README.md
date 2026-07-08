# lol-cast-cli

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)

LoL 이스포츠 국제대회(**First Stand / MSI / Worlds**)를 터미널에서
스포츠 텍스트 중계처럼 보는 인터랙티브 CLI.

lolesports.com이 실제로 쓰는 비공식 API를 폴링해서 킬 / 드래곤 / 바론 /
타워 / 골드 이벤트를 실시간 텍스트 피드로 중계한다.

- **`lolcast` 하나만 치면 끝** — 경기 선택부터 중계까지 전부 화면 안에서 단일키 조작
- **라이브 중계** — 진행 중 경기 자동 감지, 세트 끝나면 다음 게임 자동 전환
- **리플레이** — 끝난 경기를 처음부터 배속 재생 (`+`/`-`로 1~256배속 실시간 조절)
- **스크롤 가능한 피드** — 마우스 휠/키보드로 지난 장면 되돌아보기, `f`로 자동 따라가기
- **한글 중계** — 챔피언명은 Data Dragon에서 한글 변환, 드래곤 속성도 한글 표기

## 미리보기

홈 화면 — 방향키로 고르고 Enter:

```
lolcast — 국제대회 (KST)  ·  Enter: 중계/리플레이
┌──────┬─────────────┬──────┬─────────────────────┐
│ 상태 │ 시간        │ 리그 │ 매치                │
│ 완료 │ 07/06 17:00 │ msi  │ T1 vs FUR (3-0)     │
│ LIVE │ 07/08 17:00 │ msi  │ G2 vs T1            │
│ 예정 │ 07/09 17:00 │ msi  │ HLE vs BLG          │
└──────┴─────────────┴──────┴─────────────────────┘
 q 종료  r 새로고침
```

중계 화면 — 상단 스코어보드 고정, 아래 피드는 스크롤:

```
T1 vs FUR · Game 1                                             32:43
T1   11킬    62.7k   타워 7   용 3  바론 0
FUR   7킬    52.6k   타워 1   용 2  바론 0
T1 ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░ FUR                                   +10.2k
─────────────────────────────────────────────────────────────────────
 24:21  용      T1 바다 드래곤 (2스택)
 25:04  킬      Keria(카밀) → Tutsz(라이즈)
 28:05  골드    T1 +8.9k (54.7 : 45.9)
 28:14  타워    FUR 1번째 파괴
 30:31  킬      Peyz(신드라) → JoJo(렐)
 32:33  억제기  T1 억제기 파괴 (1번째)
 33:53  종료    게임 종료
 q 뒤로  f 자동스크롤  + 배속+  - 배속-
```

실제 터미널에서는 팀이 파랑/빨강, 타임스탬프·태그는 회색으로 표시된다.

## 설치

Linux / macOS / Windows, Python 3.10+.
(Windows는 [Windows Terminal](https://aka.ms/terminal) 사용 권장 — 구형 cmd 콘솔은 색·마우스 지원이 제한적)

[uv](https://docs.astral.sh/uv/) (권장):

```bash
uv tool install git+https://github.com/wavewwave20/lol-cast-cli.git
```

pipx:

```bash
pipx install git+https://github.com/wavewwave20/lol-cast-cli.git
```

설치하면 `lolcast` 명령어가 생긴다. 이후 업데이트는:

```bash
lolcast update
```

(uv/pipx 설치 방식을 자동 감지해서 최신 버전으로 재설치)

## 사용법

```bash
lolcast
```

이게 전부다. 인터랙티브 TUI가 뜨고 나머지는 화면에서:

| 화면 | 키 |
|---|---|
| 홈 (경기 목록) | `↑↓` 이동 · `Enter` 중계/리플레이 · `r` 새로고침 · `q` 종료 |
| 세트 선택 | `↑↓` 또는 숫자키 · `Enter` 재생 · `q` 뒤로 |
| 중계 | 휠/`↑↓`/`PgUp` 스크롤 · `f` 자동스크롤 · `End` 맨 아래로 · `+`/`-` 배속(리플레이) · `q` 뒤로 · `c` 즉시 종료+화면 클리어 |

바로가기 서브커맨드:

```bash
lolcast schedule                          # 일정만 출력하고 종료
lolcast watch                             # 라이브 경기로 바로 진입
lolcast replay T1 --speed 20 --game 2     # 리플레이로 바로 진입
lolcast replay 115570934355614564         # gameId 직접 지정
lolcast update                            # 최신 버전으로 자가 업데이트
lolcast --version                         # 버전 확인
```

`--league first_stand,msi,worlds` 로 리그 필터 가능 (schedule/watch).

## 피드 태그

`킬` `처형` `용` `바론` `타워` `억제기` `골드` `종료/중지/재개`

- 킬 라인은 킬러/희생자를 각자 팀 색으로 표시
- 골드 현황은 게임시간 60초마다 한 줄, 스코어보드의 골드 바는 양 팀 총 골드 비율

## 동작 방식

- `esports-api.lolesports.com` (persisted API, 공개 x-api-key)로 일정/매치 조회
- `feed.lolesports.com/livestats/v1/window/{gameId}` 를 10초 간격 폴링
  (윈도우당 초당 ~4프레임: 팀/참가자별 골드·KDA·오브젝트)
- 순수 함수 diff 엔진이 프레임 쌍을 비교해 이벤트 추출 → [Textual](https://github.com/Textualize/textual) TUI 렌더링
- livestats 프레임에는 게임 시계가 없어 첫 `in_game` 프레임 기준으로 계산
  (라이브 중간 참전 시 이진 탐색으로 게임 시작 시각 탐색)

## 개발

```bash
git clone https://github.com/wavewwave20/lol-cast-cli.git
cd lol-cast-cli
uv sync
uv run pytest          # diff 엔진은 실경기 캡처 픽스처로 검증
uv run lolcast replay T1 --speed 100
```

```
src/lolcast/
├── api.py     # lolesports API 클라이언트 (백오프 재시도, 204 처리, ddragon 한글명)
├── events.py  # 프레임 diff 엔진 (순수 함수)
├── render.py  # 피드 라인/스코어보드 렌더링 (rich)
├── app.py     # Broadcaster + 리플레이/라이브 공급 루프 (UI 독립)
├── tui.py     # Textual 인터랙티브 TUI (홈/세트선택/중계 화면)
└── cli.py     # 진입점 (기본: 인터랙티브, 서브커맨드: 바로가기)
```

## 주의

비공식 API를 사용하므로 Riot이 예고 없이 스키마를 바꾸면 동작이 깨질 수 있다.
이 프로젝트는 Riot Games와 무관한 팬 프로젝트다.

## License

MIT
