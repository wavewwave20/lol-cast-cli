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

설치하면 `lolcast` 명령어가 생긴다. 업그레이드는
`uv tool upgrade lol-cast-cli` / `pipx upgrade lol-cast-cli`.

## 사용법

```bash
lolcast schedule     # 국제대회 일정 (KST, 최근 결과 + 예정 경기)
lolcast watch        # 라이브 경기 중계 (없으면 다음 예정 경기 안내)
lolcast replay T1    # 지난 경기 리플레이 중계 (기본 8배속, 마지막 세트)
```

옵션:

```bash
lolcast replay T1 --speed 20 --game 2     # 배속·세트 지정
lolcast replay 115570934355614564         # gameId 직접 지정
lolcast watch --league msi                # 리그 필터 (first_stand,msi,worlds)
```

- `watch`는 세트가 끝나면 다음 게임으로 자동 전환하고, 매치가 끝나면 종료
- `replay`는 완료된 경기를 처음부터 배속 재생 — 라이브가 없을 때 테스트 겸 시청용
- 종료는 `Ctrl+C`

## 피드 태그

킬 · 처형 · 용 · 바론 · 타워 · 억제기 · 골드(게임시간 60초마다) · 종료/중지/재개

- 킬 라인은 킬러/희생자를 팀 색으로 표시, 챔피언명은 Data Dragon에서 한글로 변환
- 스코어보드의 골드 바는 양 팀 총 골드 비율

## 동작 방식

- `esports-api.lolesports.com` (persisted API, 공개 x-api-key)로 일정/매치 조회
- `feed.lolesports.com/livestats/v1/window/{gameId}` 를 10초 간격 폴링
  (윈도우당 초당 ~4프레임: 팀/참가자별 골드·KDA·오브젝트)
- 순수 함수 diff 엔진이 프레임 쌍을 비교해 이벤트 추출 → rich Live TUI 렌더링
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
├── app.py     # Broadcaster TUI (rich.Live) + 리플레이/라이브 루프
└── cli.py     # schedule / watch / replay 서브커맨드
```

## 주의

비공식 API를 사용하므로 Riot이 예고 없이 스키마를 바꾸면 동작이 깨질 수 있다.
이 프로젝트는 Riot Games와 무관한 팬 프로젝트다.

## License

MIT
