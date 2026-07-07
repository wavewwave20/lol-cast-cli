# lolcast

LoL 이스포츠 국제대회(First Stand / MSI / Worlds) 경기를 CLI에서
스포츠 텍스트 중계처럼 받아보는 도구.

lolesports.com이 실제로 쓰는 비공식 API(persisted API + livestats 피드)를
폴링해서, 킬/드래곤/바론/타워/골드 이벤트를 미니멀 컬럼 피드로 중계한다.

## 설치

```bash
cd dev/lolcast
uv sync
```

## 사용법

```bash
# 국제대회 일정 (KST)
uv run lolcast schedule

# 라이브 경기 중계 (없으면 다음 예정 경기 안내)
uv run lolcast watch

# 지난 경기 리플레이 중계 (기본 8배속, 기본 마지막 세트)
uv run lolcast replay T1 --speed 20 --game 2
uv run lolcast replay 115570934355614564   # gameId 직접 지정
```

`--league first_stand,msi,worlds` 로 리그 필터 가능 (schedule/watch).

## 출력 예시

터미널에서는 팀 파랑/빨강, 타임스탬프·태그 회색, 오래된 라인 딤 처리.

```
T1 vs FUR · Game 1 (replay)                                    32:43
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

## 피드 태그

킬 · 처형 · 용 · 바론 · 타워 · 억제기 · 골드(게임시간 60초마다) · 종료/중지/재개

- 킬 라인은 킬러/희생자를 팀 색으로 표시, 챔피언명은 Data Dragon에서 한글로 변환
- 골드 우위 바는 양 팀 총 골드 비율

## 주의

- 비공식 API라 Riot이 언제든 바꿀 수 있음 (공개 x-api-key 사용)
- livestats 프레임에는 게임 시계가 없어서 첫 in_game 프레임 기준으로 계산
  (라이브 중간 참전 시 이진 탐색으로 게임 시작 시각을 찾음)
- 테스트: `uv run pytest` — diff 엔진은 실경기 캡처 픽스처로 검증

## 구조

```
src/lolcast/
├── api.py     # lolesports API 클라이언트 (백오프 재시도, 204 처리, ddragon 한글명)
├── events.py  # 프레임 diff 엔진 (순수 함수)
├── render.py  # 피드 라인/스코어보드 렌더링 (rich)
├── app.py     # Broadcaster TUI (rich.Live) + 리플레이/라이브 루프
└── cli.py     # schedule / watch / replay 서브커맨드
```
