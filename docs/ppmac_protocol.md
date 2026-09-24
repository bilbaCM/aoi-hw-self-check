# H/W Self-Check ↔ PPMAC Ethernet ASCII 프로토콜 & 실기 검증 문서

Sep 24, 2026

> 이 문서는 [Claude Docs 버전](https://claude.ai/artifact/0e1a79f2-28f5-4e1e-a7a4-2a34e0a6c9bb)의 스냅샷입니다.
> 질문이나 체크리스트 항목에 대한 확인 결과는 그쪽에 댓글로 남기면 더 빠르게 반영됩니다.

## 개요

모션 H/W Check(전 축 Encoder/PWM/I/O 값 조회)와 모션 Tuning 상태 확인(축 왕복 조그 시험으로 위치편차·오버슈트·정착시간 측정) 2개 항목은 PPMAC(Power PMAC)에서 값을 읽고 조그 명령을 보내야 합니다.

C# 제어 프로그램·C++ 검사 프로그램과 달리, PPMAC은 이미 자체 Ethernet ASCII 명령 서버를 갖춘 기기라서 새로 구현해줄 서버가 없습니다 — Python이 PPMAC의 표준 Ethernet 포트에 LAN으로 직결합니다. 그래서 이 문서는 구현 요청이 아니라 검증 체크리스트입니다. 담는 내용은 두 가지입니다: 첫째, Python 쪽이 실제로 보내는 명령과 기대하는 응답 형식. 둘째, 실기 연결 전에 이 설비의 PPMAC 설정에 맞춰 확인하고 교체해야 하는 항목(TBD).

## 전송 방식

- TCP 소켓으로 PPMAC의 Ethernet ASCII 명령 채널에 직접 연결 (별도 프로그램 경유 없음)
- 기본 포트는 관례상 1025이지만, 실제 이 설비의 PPMAC 설정을 확인해야 합니다 (TBD)
- 명령은 캐리지리턴(`\r`)으로 종료해서 보냄
- 응답은 정상 종료 시 ACK(0x06), 오류 시 BELL(0x07)로 끝나는 것이 PMAC ASCII 프로토콜의 일반적 관례이지만, 실제 펌웨어/설정에 따라 다를 수 있어 실기 연결 전 검증이 필요합니다 (TBD) — Python 쪽(`PmacAsciiConnection`)은 이 두 문자를 생성자 인자로 바꿀 수 있게 만들어 뒀습니다.
- 요청 1건에 응답 1건, 동기 처리 — 응답을 받을 때까지 다음 명령을 보내지 않음
- 연결은 Python 쪽에서 최초 요청 시 맺고 계속 재사용

## 명령 1: 변수 조회 (query) — 모션 H/W Check가 사용

PMAC 전역 변수명을 명령으로 그대로 보내면, 그 값이 응답 본문(ACK/BELL 제외)으로 돌아옵니다.

**예시**

```
-> Motor[1].ActPos\r
<- 123.456<ACK>
```

Python은 응답 본문을 `float`로 파싱합니다. 숫자로 해석할 수 없으면 오류로 처리합니다.

모션 H/W Check는 축(X/Y/Z 등)마다 여러 필드(예: 인코더 카운트, PWM Duty, 원점 센서)를 조회해 기준 범위와 비교합니다. 어떤 PMAC 변수를 어떤 축/필드에 매핑할지는 `config/ppmac_axis_map.example.json`에서 사람이 정의합니다 — 아래 표는 그 예시일 뿐, 실제 이 설비의 Motor 번호·Gate 채널에 맞춰 교체해야 합니다 (TBD).

| 축 | field | 예시 PMAC 변수 | 비고 |
| --- | --- | --- | --- |
| X | `encoder_count` | `Motor[1].ActPos` | 실제 인코더 카운트 변수인지 확인 필요 |
| X | `pwm_duty_percent` | `Motor[1].Pwm` | 단위(% 여부) 확인 필요 |
| X | `io_home_sensor` | `Motor[1].HomeComplete` | 원점 센서 상태를 나타내는 실제 변수인지 확인 필요 |
| Y, Z | ... | `Motor[2]`, `Motor[3]` ... | 동일 패턴 |

field 이름 자체(`encoder_count` 등)는 Python 코드가 강제하는 고정값이 아니라 설정 파일에서 자유롭게 정할 수 있는 이름입니다 — CriteriaStore에 그 이름으로 기준(min/max)을 등록해야 그 필드가 실제로 판정에 쓰입니다.

## 명령 2: 조그 이동 (jog_to_position) — 모션 Tuning 상태 확인이 사용

축을 절대 위치로 조그 이동시키는 표준 PMAC 명령입니다.

**예시**

```
-> #1J=250.0\r
<- <ACK>
```

`#<motor번호>J=<목표위치>` 형식이며, 모터 번호는 1부터 시작합니다. 응답 본문은 쓰지 않고 ACK/BELL 여부만 확인합니다.

**확인 필요(TBD)**:
- **좌표 단위** — `target_position` 등에 넣는 값이 카운트(count) 단위인지, 엔지니어링 단위(mm 등)인지는 PPMAC의 스케일링 설정에 따라 다릅니다.
- **속도/가속도** — 이 명령 자체는 속도·가속도를 지정하지 않습니다. 현재 PPMAC에 설정된 값으로 움직이는지, 아니면 별도 파라미터(`Motor[n].JogSpeed` 등)를 먼저 설정해야 하는지 확인이 필요합니다.

모션 Tuning은 이 명령으로 시작 위치 → 목표 위치로 왕복 조그하면서 `query`로 위치를 폴링해, 위치편차·오버슈트·정착시간을 계산합니다. 축별 시험 스펙(모터 번호, 위치 변수, 시작/목표 위치, 허용오차, 정착 유지시간, 폴링 주기, 타임아웃)은 `config/ppmac_tuning_moves.example.json`에서 정의합니다.

## 실기 검증 체크리스트

실제 PPMAC에 연결하기 전에, 아래 항목을 이 설비의 PPMAC 설정과 대조해 확인해 주세요.

| 항목 | 확인할 것 | Python 쪽 기본값/가정 |
| --- | --- | --- |
| 포트 | Ethernet ASCII 명령 채널의 실제 포트 번호 | 1025 (관례) |
| 응답 종료 문자 | 정상/오류 응답을 구분하는 실제 바이트 | ACK 0x06 / BELL 0x07 (관례) |
| 축-Motor 매핑 | 어느 물리 축(X/Y/Z 등)이 몇 번 Motor인지 | 예시는 X=1, Y=2, Z=3 |
| 변수명 | 인코더 카운트/PWM/원점 센서 등을 나타내는 실제 PMAC 전역 변수명 | 예시는 `Motor[n].ActPos` / `.Pwm` / `.HomeComplete` |
| 좌표 단위 | 조그 위치·허용오차 값이 카운트인지 엔지니어링 단위인지 | 확인 필요 |
| 조그 속도/가속도 | 별도 설정이 필요한지, 현재 설정값으로 충분한지 | 확인 필요 |
| 이동 범위 | 조그 시험이 설비 물리 한계(리밋 스위치 등) 내에 있는지 | 설정 파일 작성자가 보장 |

이 항목들이 실제 값과 맞지 않으면 조회는 엉뚱한 값을 돌려주거나, 조그 명령이 의도와 다른 거리를 움직일 수 있습니다 — 최초 실기 연결은 소량 이동으로 시작해 단계적으로 검증하시길 권장합니다.

## 설정 파일 채우기

**`config/ppmac_axis_map.example.json`** — 축별 `{field명: PMAC 변수명}` 매핑. 모션 H/W Check가 조회할 대상입니다.

```json
{
  "X": {
    "encoder_count": "Motor[1].ActPos",
    "pwm_duty_percent": "Motor[1].Pwm",
    "io_home_sensor": "Motor[1].HomeComplete"
  }
}
```

**`config/ppmac_tuning_moves.example.json`** — 축별 왕복 조그 시험 스펙. 모션 Tuning 상태 확인이 사용합니다.

| 필드 | 설명 |
| --- | --- |
| `motor` | 조그 명령에 쓸 Motor 번호 |
| `position_variable` | 이동 중 위치를 폴링할 PMAC 변수명 |
| `start_position` | 시작 위치 |
| `target_position` | 목표 위치 |
| `settle_tolerance` | 정착으로 볼 위치편차 허용치 |
| `settle_hold_ms` | 허용치 이내를 유지해야 정착으로 인정하는 시간(ms) |
| `poll_interval_ms` | 위치 폴링 주기(ms) |
| `timeout_ms` | 정착을 못 하면 포기하는 타임아웃(ms) |

두 파일 모두 `_comment` 키를 제외한 나머지가 실제 값으로 채워져야 합니다 — 지금은 형식만 보여주는 TBD 예시입니다.

## 안전 참고사항

- 조그 이동(`jog_to_position`)은 실제로 축을 구동합니다. 최초 실기 연결·검증은 반드시 작업자 감독 하에, 비상정지를 준비한 상태로 진행해 주세요.
- 시험 스펙(`start_position`/`target_position`)이 설비의 물리적 이동 한계(리밋 스위치, 간섭 구간) 안에 있는지 사전에 확인해 주세요 — 이 문서의 범위 밖이며, 설정 파일을 작성하는 사람이 보장해야 합니다.
- 모션 Tuning 상태 확인은 반복 조그를 수행하므로, 시험용 이동 범위는 실제 공정 동작 범위보다 보수적으로 잡는 것을 권장합니다.

## 구현 참고사항

- **연결 수명주기**: Python 쪽은 연결을 맺은 뒤 계속 재사용합니다.
- **동시 처리**: 항상 명령 1건 → 응답 1건 순서로만 보냅니다.
- **타임아웃**: Python 쪽 기본 타임아웃은 5초입니다. 조그 이동 후 정착까지 걸리는 시간이 길면 `config/ppmac_tuning_moves.example.json`의 `timeout_ms`로 축별로 조정합니다(연결 자체의 타임아웃과는 별개).
- **Python 쪽 구현 위치** (참고용, 저장소: `bilbaCM/aoi-hw-self-check`):
  1. 연결 처리: `aoi_hw_check/integrations/ppmac/connection.py`
  2. 모션 H/W Check 연동: `aoi_hw_check/integrations/ppmac/motion_hw_collector.py`, `axis_map.py`
  3. 모션 Tuning 연동: `aoi_hw_check/integrations/ppmac/motion_tuning_runner.py`
  4. 이 프로토콜을 쓰는 판정 로직: `aoi_hw_check/checks/motion_hw_check/`, `motion_tuning_check/`
- 궁금한 점이나 체크리스트 항목에 대한 확인 결과는 이 문서에 댓글로 남겨주세요.
