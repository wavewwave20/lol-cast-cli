# lol-cast-cli

LoL 이스포츠 국제대회(First Stand / MSI / Worlds)를 터미널에서
스포츠 텍스트 중계처럼 받아보는 CLI.

lolesports.com이 실제로 쓰는 비공식 API(persisted API + livestats 피드)를
폴링해서 킬 / 드래곤 / 바론 / 타워 / 골드 이벤트를 실시간 텍스트 피드로 중계한다.

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
```

터미널에서는 팀이 파랑/빨강으로, 타임스탬프·태그는 회색으로 표시된다.

## 설치

Linux / macOS, Python 3.10+.

[uv](https://docs.astral.sh/uv/) (권장):

```bash
uv tool install git+https://github.com/wavewwave20/lol-cast-cli.git
```

pipx:

```bash
pipx install git+https://github.com/wavewwave20/lol-cast-cli.git
```

설치하면 `lolcast` 명령어가 생긴다. 업데이트는 `lolcast update` 한 방이면 된다
(uv/pipx 설치 방식을 감지해서 최신 버전으로 재설치).

## 사용법

```bash
lolcast
```

이거 하나면 끝. 인터랙티브 TUI가 뜨고 나머지는 전부 화면에서 단일키로:

| 화면 | 키 |
|---|---|
| 홈 (경기 목록) | `↑↓` 이동 · `Enter` 중계/리플레이 · `r` 새로고침 · `q` 종료 |
| 세트 선택 | `↑↓` 또는 숫자키 · `Enter` 재생 · `q` 뒤로 |
| 중계 | 휠/`↑↓`/`PgUp` 스크롤 · `f` 자동스크롤 · `+`/`-` 배속(리플레이) · `q` 뒤로 |

- 라이브 경기는 목록에 `LIVE`로 표시, 선택하면 바로 중계 (세트 간 자동 전환)
- 완료 경기는 세트를 골라 처음부터 배속 재생

바로가기 서브커맨드도 있다:

```bash
lolcast schedule                          # 일정만 출력하고 종료
lolcast watch                             # 라이브 경기로 바로 진입
lolcast replay T1 --speed 20 --game 2     # 리플레이로 바로 진입
lolcast update                            # 최신 버전으로 자가 업데이트
```

## 피드 태그

킬 · 처형 · 용 · 바론 · 타워 · 억제기 · 골드(게임시간 60초마다) · 종료/중지/재개

- 킬 라인은 킬러/희생자를 팀 색으로 표시, 챔피언명은 Data Dragon에서 한글로 변환
- 스코어보드의 골드 바는 양 팀 총 골드 비율

## 동작 방식

- `esports-api.lolesports.com` (persisted API, 공개 x-api-key)로 일정/매치 조회
- `feed.lolesports.com/livestats/v1/window/{gameId}` 를 10초 간격 폴링
  (윈도우당 초당 ~4프레임: 팀/참가자별 골드·KDA·오브젝트)
- 순수 함수 diff 엔진이 프레임 쌍을 비교해 이벤트 추출 → Textual TUI 렌더링
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
