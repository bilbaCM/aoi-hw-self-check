"""H/W Self-Check 자동화 프로그램 <-> C# 제어 프로그램(CC-Link 마스터 보유) 간 TCP 프로토콜.

기존에 C# 제어 프로그램이 레시피 파라미터 수신용으로 쓰는 TCP 소켓 서버와는
별개로, Self-Check 전용 포트를 새로 여는 것을 전제로 한다 (생산 중 레시피
채널과 진단/테스트 채널을 분리 — 안전상 권장).

## 전송
TCP 소켓, 줄바꿈으로 구분된 JSON(NDJSON). 요청 1건 = 응답 1건, 동시에 여러
요청을 보내지 않는다(한 연결에서 요청-응답을 순차적으로 주고받음).

## 공통 필드
- "type": 메시지 종류 (아래 REQUEST_*/RESPONSE_* 상수)
- "request_id": 요청·응답을 짝짓는 문자열. 클라이언트가 요청 시 생성하며,
  서버는 응답에 동일한 값을 그대로 돌려줘야 한다.

## 메시지 종류

### force_io (I/O Check — I/O Map의 한 포인트를 강제 구동)
요청: {"type": "force_io", "request_id": "...",
       "io_id": "cylinder_1_advance", "forced_input_value": true}
응답: {"type": "force_io_result", "request_id": "...",
       "observed_output_value": true}

### run_test_sequence (설비 단동 동작 확인 — 안전 인터락 시험 시퀀스 실행)
요청: {"type": "run_test_sequence", "request_id": "..."}
응답: {"type": "run_test_sequence_result", "request_id": "...",
       "steps": [
         {"step_id": "원점 복귀", "completed": true, "abnormal_stop": false, "detail": ""},
         ...
       ]}

### get_interlock_status (설비 연동 동작 Test — 연동 신호 수신·순서·지연 조회)
요청: {"type": "get_interlock_status", "request_id": "..."}
응답: {"type": "get_interlock_status_result", "request_id": "...",
       "events": [
         {"signal_id": "upstream_ready", "sequence_order": 1,
          "response_delay_ms": 120.0, "received": true},
         ...
       ]}

### 오류 응답 (모든 요청 공통)
{"type": "error", "request_id": "...", "message": "사람이 읽을 오류 설명"}
"""

from __future__ import annotations

REQUEST_FORCE_IO = "force_io"
RESPONSE_FORCE_IO = "force_io_result"

REQUEST_RUN_TEST_SEQUENCE = "run_test_sequence"
RESPONSE_RUN_TEST_SEQUENCE = "run_test_sequence_result"

REQUEST_GET_INTERLOCK_STATUS = "get_interlock_status"
RESPONSE_GET_INTERLOCK_STATUS = "get_interlock_status_result"

RESPONSE_ERROR = "error"
