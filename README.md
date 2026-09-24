# AOI H/W Self-Check 자동화 프로그램

A2 GVR AOI 검사기(Micro / Macro / Review / 계측 4계통 복합기)의 셋업 시
반복되는 설비 상태 점검 13개 항목을 자동화하는 프로그램입니다.

자동화 4개 모듈(① H/W Self-Check ② Auto Setup ③ 자동 영역 할당 ④ Setup
자동 평가) 중 **① H/W Self-Check만**을 대상으로 하며, 판정까지가 범위이고
조정·리페어 액추에이터 제어는 범위 밖입니다 — 설비가 측정·판정하고
작업자는 NG(FAIL) 항목만 조치합니다.

## 13개 항목

**A분류 — 읽어서 비교** (설비 미구동)
- PC 동작 Check
- 모션 H/W Check
- 광학 부품 동작·통신 확인

**B분류 — 돌려보고 측정** (설비 구동)
- I/O Check
- 설비 단동 동작 확인
- 모션 Tuning 상태 확인
- 설비 연동 동작 Test

**C분류 — 찍어서 판정** (기준 시료 1회 Scan 공유, 6항목)

영상은 설비를 구동해야만 취득되고 단독 취득이 불가능하다는 제약 때문에,
Scan 1회의 결과(AF Z 추종 맵 + 스캔 영상)를 아래 6항목이 함께 사용합니다.

- Stage PIN·PAD·Sensor 평탄도
- Micro / Macro / 계측 광학계 상태 확인 (Focus + Tilt, 계통별 1항목)
- AFM Setting 상태 확인
- 계측 Y축 Gantry 직각도

## 설계 원칙

- **인터페이스 추상화 + Mock 우선**: 모든 실제 설비 인터페이스는 추상
  클래스(`checks/*/collector.py`, `runner.py`, `client.py`)로 정의하고,
  각 판정 로직(`judge.py`)은 이 인터페이스에만 의존합니다. Mock 구현체로
  전 항목을 실행·검증할 수 있고, 실제 연동은 같은 인터페이스를 구현하는
  클래스를 `aoi_hw_check/integrations/`에 추가하는 방식으로 교체합니다.
- **판정 임계값 하드코딩 금지**: 모든 기준값은 `core/thresholds.py`의
  `CriteriaStore`(JSON 파일, 버전 관리)에서 로드합니다. 실측 데이터가
  없는 값은 `example_criteria.py`에 TBD로 표시된 예시값만 제공합니다.
- **Gate 기반 검증 절차**: 각 기준(Criteria)은
  `GENERATED → TRIAL → OPTIMIZED → VALIDATED → APPLIED` 단계를 밟습니다
  (`core/gate.py`). 새로 산출된 값을 곧바로 실사용에 반영하지 않습니다.
- **재Scan 횟수 상한**: C분류는 Scan 1회 = 셋업 시간이라는 제약 때문에,
  NG가 나도 무한정 재Scan하지 않고 상한(기본 3회) 초과 시 작업자 개입으로
  전환합니다 (`checks/c_class_scan/pipeline.py`).

## 프로젝트 구조

```
aoi_hw_check/
  core/                     # 항목 간 공유 인프라
    models.py                 # CheckResult, Verdict, GateStatus
    storage.py                  # SQLite 기반 결과/baseline 저장소
    thresholds.py                 # CriteriaStore (판정 기준, 버전+Gate 관리)
    gate.py                        # Gate 상태 전이 검증
    report.py                       # 조치 대상 목록 생성

  checks/                   # 13개 항목의 판정 로직 (전부 Mock 기반, 인터페이스 추상화)
    pc_check/                       # A: PC 동작 Check
    motion_hw_check/                 # A: 모션 H/W Check
    optical_comm_check/               # A: 광학 부품 동작·통신 확인
    io_check/                          # B: I/O Check
    single_unit_check/                  # B: 설비 단동 동작 확인
    motion_tuning_check/                 # B: 모션 Tuning 상태 확인 (동종 설비 비교)
    interlock_check/                      # B: 설비 연동 동작 Test
    c_class_scan/                          # C: 공유 Scan 파이프라인 (모델/기하 연산/오케스트레이터)
    pin_pad_flatness_check/                 # C: Stage PIN·PAD 평탄도
    optical_subsystem_check/                 # C: 계통별 Focus+Tilt
    afm_setting_check/                        # C: AFM Setting 상태 확인
    gantry_squareness_check/                   # C: Gantry 직각도

  integrations/             # 실제 설비 인터페이스 구현체 (Mock을 대체)
    control_program/          # C# 제어 프로그램 (CC-Link) — TCP/NDJSON
    ppmac/                      # PPMAC(Power PMAC) — LAN 직결, ASCII 프로토콜
    inspection_program/           # C++ 검사 프로그램 (카메라/AF/조명) — TCP/NDJSON
    windows_pc/                     # PC 동작 Check — WMI + Get-WinEvent
    ndjson_connection.py               # TCP/NDJSON 공통 연결 로직 (재사용)

  cli.py                    # 전 항목 실행 진입점

config/                    # 사람이 정의하는 설정 파일 (전부 *.example.json, 값은 TBD)
tests/                     # 항목당 최소 1개 테스트 파일, 전 항목 Mock/대역 객체로 검증
```

## 실행 방법

```bash
# 항목 하나 실행 (Mock)
python3 -m aoi_hw_check.cli pc-check --equipment-id EQ01
python3 -m aoi_hw_check.cli io-check --equipment-id EQ01
python3 -m aoi_hw_check.cli c-class-scan --equipment-id EQ01 --seed-example-criteria

# 셋업 착수 전 조치 대상 목록 (FAIL/NA만 모아서 출력)
python3 -m aoi_hw_check.cli action-items --equipment-id EQ01

# 기준(Criteria)의 Gate 상태를 한 단계 전진
python3 -m aoi_hw_check.cli criteria-gate \
  --store motion_hw_check_criteria.json \
  --check-item "모션 H/W Check" --key "X.encoder_count" --target TRIAL
```

각 서브커맨드의 전체 옵션은 `--help`로 확인합니다:

```bash
python3 -m aoi_hw_check.cli <command> --help
```

### 실제 설비 연동으로 전환

기본은 전부 Mock입니다. 아래 옵션을 주면 실제 구현체를 사용합니다.

| 대상 | 옵션 | 비고 |
|---|---|---|
| I/O Check, 단동 동작, 연동 동작 | `--control-program-host/-port` | C# 제어 프로그램(CC-Link) — 프로토콜은 `integrations/control_program/protocol.py` 참고, 서버 구현 필요 |
| 모션 H/W Check, 모션 Tuning | `--ppmac-host/-port` | PPMAC LAN 직결 — 실기 프로토콜 세부(ACK/BELL 바이트, 축 매핑) 검증 필요 |
| 광학 부품 확인, C분류 Scan | `--inspection-program-host/-port` | C++ 검사 프로그램 — 프로토콜은 `integrations/inspection_program/protocol.py` 참고, 서버 구현 필요 |
| PC 동작 Check | `--use-wmi` | Windows 전용(`pip install wmi pywin32`), 실기 스모크 테스트 필요 |

## 설정 파일

`config/*.example.json`은 전부 형식을 보여주는 예시이며, 실제 값(TBD)은
설비/PLC I/O Map/PPMAC 설정에 맞춰 채워야 합니다.

- `io_check_danger_list.example.json`: I/O Check에서 작업자 승인 없이는
  자동 시험하지 않는 위험 출력 목록
- `ppmac_axis_map.example.json`: 모션 H/W Check가 조회할 축별 PMAC 변수명
- `ppmac_tuning_moves.example.json`: 모션 Tuning이 수행할 축별 왕복 이동 스펙
- `windows_pc_check.example.json`: PC 동작 Check가 조회할 서비스명/드라이브/장치명

판정 임계값(`*_criteria.json`)은 각 명령에 `--seed-example-criteria`를 주면
개발/테스트용 예시값으로 자동 생성됩니다. 실측치가 아니므로 실사용 전
교체가 필요합니다.

## 테스트

```bash
python3 -m unittest discover -s tests
```

전부 Mock/대역 객체 기반이라 외부 설비 없이 실행됩니다. TCP 연동
(`integrations/control_program`, `integrations/inspection_program`)은
로컬 소켓 서버를, PPMAC ASCII 프로토콜은 같은 방식의 대역 서버를 띄워
프로토콜 왕복까지 검증합니다.

## 비범위 (Out of Scope)

- NG 항목의 실제 조정 로직 (Tilt·Focus·PIN/PAD Setting 액추에이터 제어)
- H/W Self-Check를 제외한 나머지 자동화 모듈(② Auto Setup, ③ 자동 영역
  할당, ④ Setup 자동 평가)
- 반입 후 크리닝, Level 셋팅/앙카, 공압 CDA/PV LEAK 확인, Lift Pin Level
  Setting 등 물리 작업
