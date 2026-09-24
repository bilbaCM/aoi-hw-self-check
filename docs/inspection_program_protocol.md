# H/W Self-Check ↔ C++ 검사 프로그램 TCP 프로토콜 스펙

Sep 24, 2026

> 이 문서는 [Claude Docs 버전](https://claude.ai/artifact/944d27ad-8a73-401c-affa-932a5769719a)의 스냅샷입니다.
> 질문이나 제안은 그쪽에 댓글로 남기면 더 빠르게 반영됩니다.

## 개요

H/W Self-Check 자동화 프로그램(Python)이 판정하는 13개 항목 중 **광학 부품 동작·통신 확인**과 **C분류 6항목**(Stage PIN·PAD·Sensor 평탄도, Micro/Macro/계측 광학계 상태 확인, AFM Setting 상태 확인, 계측 Y축 Gantry 직각도)은 카메라·조명·AF 측정값이 필요합니다. 카메라·조명·AF는 C++ 검사 프로그램이 소유하고 있어 Python이 카메라 SDK를 직접 잡지 않고, 이 프로그램에 Self-Check 전용 요청을 보내는 방식을 전제로 설계했습니다.

영상은 설비를 구동해야만 취득되고 단독 취득이 불가능하다는 제약 때문에, **기준 시료 1회 Scan의 결과(AF Z 추종 맵 + 스캔 영상)를 C분류 6항목이 함께 사용**합니다 — `run_reference_scan` 한 번 호출로 6개 항목의 판정에 필요한 데이터를 전부 받아옵니다.

**확인 필요(TBD)**: 지금 이런 Self-Check 전용 API가 이미 있는지, 없다면 새 포트를 열어줄 수 있는지 검사 프로그램 담당자 확인이 필요합니다. C# 제어 프로그램과 마찬가지로, 운영 중 쓰는 캡처 파이프라인과는 **별도 포트**를 권장합니다 — 생산 중 쓰는 채널과 진단/테스트 채널이 섞이지 않도록 하기 위함입니다.

## 전송 방식

- TCP 소켓, 줄바꿈으로 구분된 JSON(NDJSON) — 메시지 1건 = JSON 객체 1개 + 줄바꿈(`\n`)
- 요청 1건에 응답 1건, 동기(synchronous) 처리 — 한 연결에서 다음 요청을 보내기 전에 이전 응답을 반드시 받아야 함 (동시에 여러 요청을 보내지 않음)
- 연결은 Python 쪽에서 최초 요청 시 맺고 계속 재사용 (요청마다 새로 연결하지 않음)

C# 제어 프로그램 프로토콜과 동일한 전송 방식입니다 — Python 쪽 저수준 연결 로직(`NDJSONConnection`)을 두 프로토콜이 공유합니다.

## 공통 필드

모든 요청/응답 JSON 객체는 아래 필드를 포함합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `type` | string | 메시지 종류. 아래 2개 요청 타입과 그에 대응하는 `_result` 응답 타입, 그리고 공통 `error` 타입 중 하나 |
| `request_id` | string | 요청·응답을 짝짓는 문자열(UUID). **클라이언트(Python)가 요청 시 생성**하며, 서버(C++)는 응답에 요청에서 받은 값을 **그대로 동일하게** 돌려줘야 합니다. 값이 다르면 Python 쪽에서 프로토콜 동기화 오류로 처리합니다. |

## 메시지 1: run_reference_scan — 기준 시료 1회 Scan (C분류 6항목 공유)

설비를 구동해 기준 시료를 1회 Scan하고, AF가 기록한 Z 추종 맵과 스캔 영상에서 산출한 값을 함께 돌려받습니다. 이 응답 하나로 아래 6개 항목을 전부 판정합니다.

- Stage PIN·PAD·Sensor 평탄도 (`pin_heights`)
- Micro / Macro / 계측 광학계 상태 확인 — Focus + Tilt, 계통별 1항목 (`tracks`, `focus_measures`)
- AFM Setting 상태 확인 (`tracks`의 `beam_position_error_um`)
- 계측 Y축 Gantry 직각도 (`gantry_x_axis_samples`, `gantry_y_axis_samples`)

**요청**

```json
{"type": "run_reference_scan", "request_id": "..."}
```

파라미터 없음.

**응답**

```json
{"type": "run_reference_scan_result", "request_id": "...",
 "af_z_map": {
   "pin_heights": [
     {"pin_id": "PIN1", "z_um": 100.0},
     {"pin_id": "PIN2", "z_um": 100.3}
   ],
   "tracks": {
     "Micro": {"samples": [
       {"x_mm": 0.0, "y_mm": 0.0, "z_um": 50.0, "beam_position_error_um": 0.05},
       {"x_mm": 10.0, "y_mm": 0.0, "z_um": 50.1, "beam_position_error_um": 0.04}
     ]},
     "Macro": {"samples": [ ... ]},
     "계측": {"samples": [ ... ]}
   }
 },
 "scan_images": {
   "focus_measures": {"Micro": 980.0, "Macro": 875.0, "계측": 910.0},
   "gantry_x_axis_samples": [
     {"stage_position_mm": 0.0, "x_um": 0.0, "y_um": 0.0},
     {"stage_position_mm": 50.0, "x_um": 50.0, "y_um": 0.1}
   ],
   "gantry_y_axis_samples": [ ... ]
 }}
```

### `af_z_map` — Stage PIN 높이, Tilt/AFM Setting 판정의 공통 입력

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `pin_heights` | array | Stage PIN/PAD/Sensor 지점별 AF 측정 높이. **평탄도 판정에 최소 2개 이상 필요** — 이보다 적으면 NA 처리됩니다. |
| `pin_heights[].pin_id` | string | PIN/PAD/Sensor 지점 식별자 |
| `pin_heights[].z_um` | number | 그 지점의 AF 측정 높이(µm) |
| `tracks` | object | 광학계 계통별(키: `"Micro"`, `"Macro"`, `"계측"`) AF Z 추종 샘플 목록 |
| `tracks[계통].samples` | array | 그 계통의 AF Z 추종 샘플. **Tilt 판정(평면 피팅)에 최소 3개 이상, x/y가 한 직선 위에 있지 않도록 2차원으로 분포해야 함** — 한 방향으로만 찍으면 평면 방정식이 특이(singular)해져 계산할 수 없습니다. |
| `tracks[계통].samples[].x_mm`, `y_mm` | number | 측정 위치 좌표(mm) |
| `tracks[계통].samples[].z_um` | number | 그 위치의 AF 측정 높이(µm) — 계통별 Tilt(기울기) 판정에 사용 |
| `tracks[계통].samples[].beam_position_error_um` | number | 그 위치의 AF Beam Position 추종 오차(µm) — AFM Setting 상태 확인(DOF의 1/3 이내)에 사용 |

### `scan_images` — Focus 판정, Gantry 직각도 판정의 입력

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `focus_measures` | object | 광학계 계통별(키: `"Micro"`, `"Macro"`, `"계측"`) Focus 측정값 1개(숫자, 단위 무관 — 이 설비의 최초 실행값을 기준 시료 값(baseline)으로 저장하고 이후 실행은 그 비율로 판정합니다) |
| `gantry_x_axis_samples` | array | 계측 Gantry X축 구동 중 다점 취득한 Cell 패턴 좌표. **직각도 판정에 축당 최소 3점 이상 필요**(2점 측정 금지 — 구간 직진도 오차를 직각도로 오인할 수 있어서입니다) |
| `gantry_y_axis_samples` | array | 계측 Gantry Y축 구동 중 다점 취득한 Cell 패턴 좌표. 위와 동일한 최소 점수 |
| `*_axis_samples[].stage_position_mm` | number | 그 샘플을 찍은 Stage 위치(mm) |
| `*_axis_samples[].x_um`, `y_um` | number | 그 위치에서 취득한 Cell 패턴 좌표(µm) — X/Y 각 축에 최소자승 직선을 피팅해 두 직선의 사잇각을 90도와 비교합니다 |

`tracks`와 `focus_measures`의 계통 키는 반드시 `"Micro"`, `"Macro"`, `"계측"` 3개를 그대로 써야 합니다(한글 "계측" 포함) — Python 쪽이 이 문자열을 그대로 키로 사용합니다.

## 메시지 2: run_optical_comm_test — 광학 부품 동작·통신 확인

카메라/조명 채널마다 광량을 단계적으로 올리며 통신 응답 여부와 Gray 값을 취득합니다. 통신 응답이 있는지, 광량이 늘어날 때 Gray 값이 단조 증가하는지를 판정합니다(절대 기준 수치는 필요 없습니다).

**요청**

```json
{"type": "run_optical_comm_test", "request_id": "..."}
```

파라미터 없음.

**응답**

```json
{"type": "run_optical_comm_test_result", "request_id": "...",
 "channels": {
   "Micro_CH1": {
     "communication_ok": true,
     "samples": [
       {"light_level": 0.0, "gray_value": 10.0},
       {"light_level": 25.0, "gray_value": 70.0},
       {"light_level": 50.0, "gray_value": 130.0}
     ]
   },
   "Macro_CH1": {"communication_ok": true, "samples": [ ... ]}
 }}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `channels` | object | 채널 식별자를 키로 하는 객체 — 채널 이름은 자유(예: `"Micro_CH1"`), 검사 프로그램이 관리하는 실제 채널 목록을 그대로 쓰면 됩니다 |
| `channels[id].communication_ok` | bool | 그 채널과의 통신 응답 여부. `false`면 그 채널은 바로 FAIL 처리됩니다 |
| `channels[id].samples` | array | 광량 단계별 응답 샘플. **단조 증가 판정에 최소 2개 이상 필요**(서로 다른 `light_level`) — 광량 순서로 정렬해 이웃한 두 샘플씩 비교합니다 |
| `channels[id].samples[].light_level` | number | 그 샘플을 찍은 광량 설정값(단위 무관, 상대 비교만 함) |
| `channels[id].samples[].gray_value` | number | 그 광량에서 취득한 평균 Gray 값 |

카메라 Gray 값이 상한(예: 8bit=255)에서 포화되는 구간은 현재 비단조로 간주되어 FAIL 처리됩니다 — 실제 센서 포화 거동을 보고 허용 범위를 추가할지 추후 결정할 예정입니다.

## 오류 응답 (모든 요청 공통)

요청 처리 중 오류가 발생하면, 위 `_result` 응답 대신 아래 형식으로 응답합니다.

```json
{"type": "error", "request_id": "...", "message": "사람이 읽을 수 있는 오류 설명"}
```

`request_id`는 원래 요청의 값을 그대로 담아야 합니다. Python 쪽은 이 응답을 받으면 예외를 발생시켜 해당 판정 항목을 실패 처리합니다.

## 구현 참고사항

- **연결 수명주기**: Python 쪽은 연결을 맺은 뒤 계속 재사용합니다. 서버는 하나의 연결에서 여러 요청을 순차적으로 계속 받을 수 있어야 합니다 (요청마다 연결을 끊지 말 것).
- **동시 처리**: 한 연결 안에서는 항상 요청 1건 → 응답 1건 순서로만 옵니다. 서버가 여러 연결을 동시에 받을 필요는 없습니다(Self-Check는 한 번에 하나씩 실행).
- **타임아웃**: Python 쪽 기본 타임아웃은 5초입니다. `run_reference_scan`은 실제 설비 구동(Stage 이동 + AF + 영상 취득)을 포함해 다른 요청보다 오래 걸릴 수 있으니, 예상 소요 시간을 알려주시면 그에 맞춰 타임아웃을 늘리겠습니다.
- **재Scan 시 처리**: NG가 나오면 Python 쪽이 상한(기본 3회)까지 `run_reference_scan`을 다시 호출할 수 있습니다. 매번 **완전히 새로운 요청**이며, 서버가 이전 요청과의 연관성(재시도 횟수 등)을 신경 쓸 필요는 없습니다 — 재시도 상한 관리는 Python 쪽에서 합니다.
- **포트를 분리하는 이유**: 운영 중 쓰는 캡처 파이프라인과 이 진단/테스트 채널이 섞이지 않도록 별도 포트를 권장합니다.
- **Python 쪽 구현 위치** (참고용, 저장소: `bilbaCM/aoi-hw-self-check`):
  1. 프로토콜 스펙 원본: `aoi_hw_check/integrations/inspection_program/protocol.py`
  2. 연결 처리: `aoi_hw_check/integrations/inspection_program/connection.py`
  3. 이 프로토콜을 쓰는 판정 로직: `aoi_hw_check/checks/optical_comm_check/`, `c_class_scan/`, `pin_pad_flatness_check/`, `optical_subsystem_check/`, `afm_setting_check/`, `gantry_squareness_check/`
- 궁금한 점이나 메시지 포맷 제안은 이 문서에 댓글로 남겨주세요.
