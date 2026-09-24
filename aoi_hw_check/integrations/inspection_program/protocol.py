"""H/W Self-Check 자동화 프로그램 <-> C++ 검사 프로그램 간 TCP 프로토콜.

카메라·조명·AF는 C++ 검사 프로그램이 소유하고 있어, Python이 카메라 SDK를
직접 잡지 않고 이 프로그램에 Self-Check 전용 요청을 보내는 방식을 전제로
한다. 지금 이런 API가 이미 있는지, 없다면 새 포트를 열어줄 수 있는지는
검사 프로그램 담당자 확인이 필요하다 (TBD) — C# 제어 프로그램과 마찬가지로
운영 중 쓰는 캡처 파이프라인과는 별도 포트를 권장한다.

## 전송
TCP 소켓, 줄바꿈으로 구분된 JSON(NDJSON). 요청 1건 = 응답 1건.

## 공통 필드
- "type": 메시지 종류
- "request_id": 요청·응답을 짝짓는 문자열. 클라이언트가 생성하며,
  서버는 응답에 동일한 값을 그대로 돌려줘야 한다.

## 메시지 종류

### run_reference_scan (C분류 6항목이 공유하는 기준 시료 1회 Scan)
설비 구동 없이 영상을 단독 취득할 수 없다는 제약 때문에, 이 Scan 1회의
결과(AF Z 추종 맵 + 스캔 영상)를 C분류 6항목이 함께 사용한다.

요청: {"type": "run_reference_scan", "request_id": "..."}
응답: {"type": "run_reference_scan_result", "request_id": "...",
       "af_z_map": {
         "pin_heights": [{"pin_id": "PIN1", "z_um": 100.0}, ...],
         "tracks": {
           "Micro": {"samples": [
             {"x_mm": 0.0, "y_mm": 0.0, "z_um": 50.0, "beam_position_error_um": 0.05},
             ...
           ]},
           "Macro": {...},
           "계측": {...}
         }
       },
       "scan_images": {
         "focus_measures": {"Micro": 980.0, "Macro": 875.0, "계측": 910.0},
         "gantry_x_axis_samples": [
           {"stage_position_mm": 0.0, "x_um": 0.0, "y_um": 0.0}, ...
         ],
         "gantry_y_axis_samples": [...]
       }}

### run_optical_comm_test (광학 부품 동작·통신 확인 — 광량 단계별 Gray 응답)
요청: {"type": "run_optical_comm_test", "request_id": "..."}
응답: {"type": "run_optical_comm_test_result", "request_id": "...",
       "channels": {
         "Micro_CH1": {
           "communication_ok": true,
           "samples": [{"light_level": 0.0, "gray_value": 10.0}, ...]
         },
         ...
       }}

### 오류 응답 (모든 요청 공통)
{"type": "error", "request_id": "...", "message": "사람이 읽을 오류 설명"}
"""

from __future__ import annotations

REQUEST_RUN_REFERENCE_SCAN = "run_reference_scan"
RESPONSE_RUN_REFERENCE_SCAN = "run_reference_scan_result"

REQUEST_RUN_OPTICAL_COMM_TEST = "run_optical_comm_test"
RESPONSE_RUN_OPTICAL_COMM_TEST = "run_optical_comm_test_result"

RESPONSE_ERROR = "error"
