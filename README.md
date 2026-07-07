# lolcast 🎙️

LoL 이스포츠 국제대회(First Stand / MSI / Worlds) 경기를 CLI에서
스포츠 텍스트 중계처럼 받아보는 도구.

lolesports.com이 실제로 쓰는 비공식 API(persisted API + livestats 피드)를
폴링해서, 킬/드래곤/바론/타워/골드 이벤트를 이모지 한 줄 중계로 변환한다.

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

```
╭──────────────────────── T1 vs FUR — Game 1 (replay) ────────────────────────╮
│ 🔵 T1   ⚔️15  💰67.8k  🏰10  👹0  🐉🐉🐉                            ⏱ 33:53 │
│ 🔴 FUR  ⚔️ 8  💰54.2k  🏰1  👹0  🐉🐉                                       │
│ ─────────────────────────────────────────────────────────────────────────── │
│ ⚔️ [30:31] T1 Peyz(Syndra) → FUR JoJo(Rell) 킬                              │
│ 🐉 [30:32] T1 바다 드래곤 처치 (3스택)                                       │
│ 💰 [32:05] 골드: T1 +9.3k (61.3k : 52.0k)                                   │
│ 💥 [32:33] T1 억제기 파괴 (1번째)                                            │
│ 🏰 [33:42] T1 타워 파괴 (10번째)                                             │
│ ⚔️ [33:48] T1 Faker(Orianna) → FUR Tatu(LeeSin) 킬                          │
│ 🏁 [33:53] 게임 종료                                                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

## 이벤트 종류

| 이모지 | 이벤트 |
|---|---|
| ⚔️ | 킬 (킬러→희생자, 챔피언 표시) |
| 💀 | 처형/킬러 불명 사망 |
| 🐉 | 드래곤 (속성 한글, 스택 수) |
| 👹 | 바론 |
| 🏰 / 💥 | 타워 / 억제기 파괴 |
| 💰 | 골드 현황 (게임시간 60초마다) |
| 🏁 ⏸️ ▶️ | 게임 종료 / 일시정지 / 재개 |

## 주의

- 비공식 API라 Riot이 언제든 바꿀 수 있음 (공개 x-api-key 사용)
- livestats 프레임에는 게임 시계가 없어서 첫 in_game 프레임 기준으로 계산
  (라이브 중간 참전 시 이진 탐색으로 게임 시작 시각을 찾음)
- 테스트: `uv run pytest` — diff 엔진은 실경기 캡처 픽스처로 검증

## 구조

```
src/lolcast/
├── api.py     # lolesports API 클라이언트 (백오프 재시도, 204 처리)
├── events.py  # 프레임 diff 엔진 (순수 함수)
├── render.py  # 이벤트 → 이모지 한 줄, 스코어보드
├── app.py     # Broadcaster TUI (rich.Live) + 리플레이/라이브 루프
└── cli.py     # schedule / watch / replay 서브커맨드
```
