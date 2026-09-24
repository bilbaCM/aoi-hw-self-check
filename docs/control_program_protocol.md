# H/W Self-Check ↔ C# 제어 프로그램 TCP 프로토콜 스펙

Sep 24, 2026

> 이 문서는 [Claude Docs 버전](https://claude.ai/artifact/4keXHRHh4XByvY3Dh87S3u)의 스냅샷입니다.
> 질문이나 제안은 그쪽에 댓글로 남기면 더 빠르게 반영됩니다.

## 개요

H/W Self-Check 자동화 프로그램(Python)이 I/O Check, 설비 단동 동작 확인, 설비 연동 동작 Test 3개 항목을 판정하려면 CC-Link I/O를 제어해야 합니다. CC-Link 마스터 카드는 C# 제어 프로그램이 독점하고 있어 Python이 CC-Link를 직접 제어할 수 없습니다. 따라서 이 3개 항목은 C# 제어 프로그램에 요청을 보내고 응답을 받는 방식으로 동작합니다.

기존에 C# 제어 프로그램이 C++ 검사 프로그램으로부터 레시피 파라미터를 받는 TCP 소켓 서버가 있는 것으로 파악했습니다. 이 프로토콜은 그 소켓과는 **별개의 포트**를 새로 여는 것을 전제로 설계했습니다 — 생산 중 쓰는 레시피 채널과 진단/테스트 채널이 섞이지 않도록 분리하기 위함입니다.

## 전송 방식

- TCP 소켓, 줄바꿈으로 구분된 JSON(NDJSON) — 메시지 1건 = JSON 객체 1개 + 줄바꿈(`\n`)
- 요청 1건에 응답 1건, 동기(synchronous) 처리 — 한 연결에서 다음 요청을 보내기 전에 이전 응답을 반드시 받아야 함 (동시에 여러 요청을 보내지 않음)
- 연결은 Python 쪽에서 최초 요청 시 맺고 계속 재사용 (요청마다 새로 연결하지 않음)

## 공통 필드

모든 요청/응답 JSON 객체는 아래 필드를 포함합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `type` | string | 메시지 종류. 아래 3개 요청 타입과 그에 대응하는 `_result` 응답 타입, 그리고 공통 `error` 타입 중 하나 |
| `request_id` | string | 요청·응답을 짝짓는 문자열(UUID). **클라이언트(Python)가 요청 시 생성**하며, 서버(C#)는 응답에 요청에서 받은 값을 **그대로 동일하게** 돌려줘야 합니다. 값이 다르면 Python 쪽에서 프로토콜 동기화 오류로 처리합니다. |

## 메시지 1: force_io — I/O Check

I/O Map의 한 포인트에 입력을 강제로 구동하고, 그 결과 관측된 출력 값을 돌려받습니다.

**요청**

```json
{"type": "force_io", "request_id": "...", "io_id": "cylinder_1_advance", "forced_input_value": true}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `io_id` | string | 구동할 I/O 포인트 식별자 |
| `forced_input_value` | bool 또는 숫자 | 강제로 구동할 입력 값 |

**응답**

```json
{"type": "force_io_result", "request_id": "...", "observed_output_value": true}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `observed_output_value` | bool 또는 숫자 | 구동 후 실제 관측된 출력 값 (Python이 기대값과 비교해 PASS/FAIL 판정) |

## 메시지 2: run_test_sequence — 설비 단동 동작 확인

안전 인터락이 걸린 시험 시퀀스를 실행하고, 스텝별 완주 여부·이상 정지 여부를 돌려받습니다.

**요청**

```json
{"type": "run_test_sequence", "request_id": "..."}
```

파라미터 없음.

**응답**

```json
{"type": "run_test_sequence_result", "request_id": "...",
 "steps": [
   {"step_id": "원점 복귀", "completed": true, "abnormal_stop": false, "detail": ""},
   {"step_id": "Stage 이동", "completed": true, "abnormal_stop": false, "detail": ""}
 ]}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `steps` | array | 시퀀스를 구성하는 스텝 목록, 실행 순서대로 |
| `steps[].step_id` | string | 스텝 이름 |
| `steps[].completed` | bool | 정상 완료 여부 |
| `steps[].abnormal_stop` | bool | 이상 정지 발생 여부 |
| `steps[].detail` | string | 부가 설명 (선택, 없으면 빈 문자열) |

## 메시지 3: get_interlock_status — 설비 연동 동작 Test

전후 공정 장비와 주고받은 연동 신호의 수신 여부·순서·응답 지연을 조회합니다.

**요청**

```json
{"type": "get_interlock_status", "request_id": "..."}
```

파라미터 없음.

**응답**

```json
{"type": "get_interlock_status_result", "request_id": "...",
 "events": [
   {"signal_id": "upstream_ready", "sequence_order": 1, "response_delay_ms": 120.0, "received": true},
   {"signal_id": "load_request", "sequence_order": 2, "response_delay_ms": 80.0, "received": true}
 ]}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `events` | array | 관측된 연동 신호 목록 |
| `events[].signal_id` | string | 신호 식별자 |
| `events[].sequence_order` | int | 실제 수신된 순서 (1부터) |
| `events[].response_delay_ms` | number | 응답까지 걸린 시간(ms) |
| `events[].received` | bool | 신호 수신 여부 |

## 오류 응답 (모든 요청 공통)

요청 처리 중 오류가 발생하면, 위 `_result` 응답 대신 아래 형식으로 응답합니다.

```json
{"type": "error", "request_id": "...", "message": "사람이 읽을 수 있는 오류 설명"}
```

`request_id`는 원래 요청의 값을 그대로 담아야 합니다. Python 쪽은 이 응답을 받으면 예외를 발생시켜 해당 판정 항목을 실패 처리합니다.

## 구현 참고사항

- **연결 수명주기**: Python 쪽은 연결을 맺은 뒤 계속 재사용합니다. 서버는 하나의 연결에서 여러 요청을 순차적으로 계속 받을 수 있어야 합니다 (요청마다 연결을 끊지 말 것).
- **동시 처리**: 한 연결 안에서는 항상 요청 1건 → 응답 1건 순서로만 옵니다. 서버가 여러 연결을 동시에 받을 필요는 없지만(Self-Check는 한 번에 하나씩 실행), 받는다면 연결별로 독립적으로 처리하면 됩니다.
- **타임아웃**: Python 쪽 기본 타임아웃은 5초입니다. 시퀀스 실행처럼 오래 걸릴 수 있는 요청은 필요시 타임아웃 값을 조정할 수 있으니, 예상 소요 시간을 알려주시면 맞추겠습니다.
- **포트를 분리하는 이유**: 기존 레시피 파라미터 소켓과 이 프로토콜을 같은 포트에서 메시지 타입으로만 구분하는 방법도 있지만, 생산 중 쓰는 채널과 진단/테스트 채널이 섞이지 않도록 별도 포트를 권장합니다.
- **Python 쪽 구현 위치** (참고용, 저장소: `bilbaCM/aoi-hw-self-check`):
  1. 프로토콜 스펙 원본: `aoi_hw_check/integrations/control_program/protocol.py`
  2. 연결 처리: `aoi_hw_check/integrations/control_program/connection.py`
  3. 이 프로토콜을 쓰는 판정 로직: `aoi_hw_check/checks/io_check/`, `single_unit_check/`, `interlock_check/`
- 궁금한 점이나 메시지 포맷 제안은 이 문서에 댓글로 남겨주세요.
