"""AOI H/W Self-Check 자동화 프로그램의 GUI (Tkinter, 표준 라이브러리만 사용).

설비 PC는 인터넷이 안 될 수 있어 추가 패키지 설치가 필요 없는 Tkinter로
만든다. 체크박스로 13개 항목(C분류는 6항목이 기준 시료 1회 Scan을 공유해
한 단위) 중 원하는 것만 골라 실행할 수 있고, 기본값은 전체 선택이라 아무것도
바꾸지 않으면 run.bat과 같은 전체 실행이 된다. 실제 판정 로직은 CLI와 동일하게
`aoi_hw_check.cli.execute_selected`를 그대로 재사용한다 — GUI는 표시 방식만
다를 뿐 판정 로직을 따로 구현하지 않는다.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import messagebox, ttk

from aoi_hw_check import __version__
from aoi_hw_check.cli import RunAllOutcome, execute_selected
from aoi_hw_check.cli_output import PROGRAM_NAME
from aoi_hw_check.gui_support import (
    DEFAULT_EQUIPMENT_ID,
    GATE_COLUMNS,
    REPORTS_DIR,
    SELECTABLE_ITEMS,
    VERDICT_COLOR,
    VERDICT_LABEL,
    VERDICT_ROW_BACKGROUND,
    ConnectionInputs,
    advance_criteria_gate,
    build_connected_run_all_args,
    describe_connection_inputs,
    format_action_items,
    format_criteria_row,
    format_detail_cell,
    format_report_row,
    list_criteria_rows,
    list_dangerous_io_points,
    list_report_files,
    next_status,
    parse_min_max,
    read_report_text,
    save_criteria_value,
)

_MUTED_TEXT_COLOR = "#555555"

# 상태 표시줄 색상 — 판정 색(VERDICT_COLOR)과 톤을 맞췄다.
_STATUS_NEUTRAL_COLOR = "#1f2328"
_STATUS_RUNNING_COLOR = "#0969da"
_STATUS_DONE_COLOR = "#1a7f37"
_STATUS_ERROR_COLOR = "#cf222e"
_STATUS_WARNING_COLOR = "#9a6700"


def _apply_theme(root: tk.Tk) -> ttk.Style:
    """가능하면 OS 네이티브에 가까운 ttk 테마를 쓰고, 표/섹션 제목 글꼴과
    판정별 행 배경까지 한 번에 설정한다. Windows에서는 "vista" 테마가 있으면
    그걸 쓰고, 없으면 순서대로 다음 테마로 넘어간다 — 어떤 환경이든 항상
    뭔가는 적용된다.
    """
    style = ttk.Style(root)
    for theme in ("vista", "xpnative", "clam", "alt", "default"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    default_font = tkfont.nametofont("TkDefaultFont")
    header_font = default_font.copy()
    header_font.configure(weight="bold", size=default_font.cget("size") + 1)
    # 폰트 객체가 가비지 컬렉션되지 않도록 root에 붙잡아 둔다.
    root._header_font = header_font  # type: ignore[attr-defined]

    style.configure("TLabelframe.Label", font=header_font)
    style.configure(
        "Danger.TLabelframe.Label", font=header_font, foreground=_STATUS_WARNING_COLOR
    )
    style.configure("Treeview", rowheight=24)
    style.configure(
        "Treeview.Heading",
        font=(default_font.cget("family"), default_font.cget("size"), "bold"),
    )
    return style


def _center_window(win: tk.Tk | tk.Toplevel, width: int, height: int) -> None:
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 3, 0)  # 정중앙보다 살짝 위가 자연스럽다
    win.geometry(f"{width}x{height}+{x}+{y}")


class HWSelfCheckApp(tk.Tk):
    """13개 항목 run-all을 버튼 클릭으로 실행하고 결과를 표로 보여주는 메인 창."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{PROGRAM_NAME} (v{__version__})")
        _apply_theme(self)
        self.minsize(820, 540)
        _center_window(self, 980, 680)

        self._result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._connection_inputs = ConnectionInputs()
        self._cancel_event = threading.Event()
        self._build_widgets()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="설비 ID:").pack(side="left")
        self._equipment_id_var = tk.StringVar(value=DEFAULT_EQUIPMENT_ID)
        entry = ttk.Entry(top, textvariable=self._equipment_id_var, width=16)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<Return>", lambda _event: self._on_run_clicked())

        self._run_button = ttk.Button(top, text="선택 항목 실행", command=self._on_run_clicked)
        self._run_button.pack(side="left")

        self._cancel_button = ttk.Button(
            top, text="취소", command=self._on_cancel_clicked, state="disabled"
        )
        self._cancel_button.pack(side="left", padx=(6, 0))

        self._status_var = tk.StringVar(value="대기 중")
        self._status_label = ttk.Label(
            top, textvariable=self._status_var, foreground=_STATUS_NEUTRAL_COLOR
        )
        self._status_label.pack(side="left", padx=12)

        ttk.Button(top, text="기준값 Gate 관리...", command=self._open_gate_window).pack(
            side="right"
        )
        ttk.Button(top, text="연동 설정...", command=self._open_connection_settings).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(top, text="리포트 열람...", command=self._open_report_history).pack(
            side="right", padx=(0, 6)
        )

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10)

        conn_bar = ttk.Frame(self, padding=(10, 6, 10, 6))
        conn_bar.pack(fill="x")
        self._connection_summary_var = tk.StringVar(
            value=describe_connection_inputs(self._connection_inputs)
        )
        ttk.Label(conn_bar, textvariable=self._connection_summary_var, foreground=_MUTED_TEXT_COLOR).pack(
            anchor="w"
        )

        self._progress = ttk.Progressbar(self, mode="determinate")
        self._progress.pack(fill="x", padx=10, pady=(0, 6))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sidebar = ttk.Frame(body)
        sidebar.pack(side="left", fill="y", padx=(0, 10))

        selection_frame = ttk.LabelFrame(sidebar, text="실행할 항목", padding=8)
        selection_frame.pack(fill="x")

        # ttk::checkbutton은 생성자에 wraplength를 직접 받지 않으므로 스타일로 설정한다
        # (C분류 항목처럼 긴 이름이 사이드바 폭을 넘지 않도록 줄바꿈).
        style = ttk.Style(self)
        style.configure("Selectable.TCheckbutton", wraplength=260)

        select_buttons = ttk.Frame(selection_frame)
        select_buttons.pack(fill="x", pady=(0, 6))
        ttk.Button(select_buttons, text="전체 선택", command=lambda: self._set_all_items(True)).pack(
            side="left"
        )
        ttk.Button(select_buttons, text="전체 해제", command=lambda: self._set_all_items(False)).pack(
            side="left", padx=(6, 0)
        )

        self._item_vars: dict[str, tk.BooleanVar] = {}
        for key, label in SELECTABLE_ITEMS:
            var = tk.BooleanVar(value=True)
            self._item_vars[key] = var
            ttk.Checkbutton(
                selection_frame, text=label, variable=var, style="Selectable.TCheckbutton"
            ).pack(anchor="w", pady=1)

        danger_frame = ttk.LabelFrame(
            sidebar, text="위험 I/O 승인 (I/O Check)", padding=8, style="Danger.TLabelframe"
        )
        danger_frame.pack(fill="x", pady=(10, 0))

        self._danger_points = list_dangerous_io_points()
        self._danger_vars: dict[str, tk.BooleanVar] = {}
        if self._danger_points:
            ttk.Label(
                danger_frame,
                text="체크한 항목만 승인되어 실제로 구동됩니다.\n체크하지 않으면 계속 NA로 남습니다.",
                foreground=_MUTED_TEXT_COLOR,
                justify="left",
                wraplength=240,
            ).pack(anchor="w", pady=(0, 4))
            for point in self._danger_points:
                var = tk.BooleanVar(value=False)  # 안전 기본값: 승인 안 함
                self._danger_vars[point.io_id] = var
                label = f"{point.io_id} — {point.description}" if point.description else point.io_id
                ttk.Checkbutton(
                    danger_frame, text=label, variable=var, style="Selectable.TCheckbutton"
                ).pack(anchor="w", pady=1)
        else:
            ttk.Label(danger_frame, text="등록된 위험 출력 없음", foreground=_MUTED_TEXT_COLOR).pack(
                anchor="w"
            )

        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)

        columns = ("verdict", "check_item", "detail")
        self._tree = ttk.Treeview(content, columns=columns, show="headings", height=15)
        self._tree.heading("verdict", text="판정")
        self._tree.heading("check_item", text="항목")
        self._tree.heading("detail", text="상세")
        self._tree.column("verdict", width=90, anchor="center", stretch=False)
        self._tree.column("check_item", width=220, anchor="w", stretch=False)
        self._tree.column("detail", width=560, anchor="w")
        self._tree.pack(fill="both", expand=True, pady=(0, 10))

        default_font = tkfont.nametofont("TkDefaultFont")
        verdict_font = (default_font.cget("family"), default_font.cget("size"), "bold")
        for verdict, color in VERDICT_COLOR.items():
            self._tree.tag_configure(
                verdict.value,
                foreground=color,
                background=VERDICT_ROW_BACKGROUND[verdict],
                font=verdict_font,
            )

        action_frame = ttk.LabelFrame(content, text="조치 대상 목록", padding=8)
        action_frame.pack(fill="both", expand=False, pady=(0, 10))
        self._action_text = tk.Text(action_frame, height=6, wrap="word", state="disabled")
        self._action_text.pack(fill="both", expand=True)

        self._report_var = tk.StringVar(value="")
        ttk.Label(content, textvariable=self._report_var, foreground=_MUTED_TEXT_COLOR).pack(anchor="w")

    def _set_all_items(self, checked: bool) -> None:
        for var in self._item_vars.values():
            var.set(checked)

    def _selected_item_keys(self) -> set[str]:
        return {key for key, var in self._item_vars.items() if var.get()}

    def _approved_dangerous_ids(self) -> set[str]:
        return {io_id for io_id, var in self._danger_vars.items() if var.get()}

    def _on_run_clicked(self) -> None:
        equipment_id = self._equipment_id_var.get().strip()
        if not equipment_id:
            messagebox.showwarning(PROGRAM_NAME, "설비 ID를 입력하세요.")
            return

        selected_keys = self._selected_item_keys()
        if not selected_keys:
            messagebox.showwarning(PROGRAM_NAME, "실행할 항목을 하나 이상 선택하세요.")
            return

        approved_ids = self._approved_dangerous_ids()
        if approved_ids and not messagebox.askyesno(
            PROGRAM_NAME,
            f"위험 출력 {len(approved_ids)}건을 승인하고 실제로 구동합니다:\n"
            + ", ".join(sorted(approved_ids))
            + "\n\n계속하시겠습니까?",
        ):
            return

        # 연동 설정(호스트/포트) 검증은 메인 스레드에서 미리 해서, 잘못된 입력이면
        # 스레드를 띄우지도 않고 바로 알려준다 — "연동 설정..." 창에서 저장할 때도
        # 같은 검증을 거치므로 보통은 여기서 실패하지 않는다.
        try:
            args = build_connected_run_all_args(equipment_id, self._connection_inputs, approved_ids)
        except ValueError as exc:
            messagebox.showwarning(PROGRAM_NAME, str(exc))
            return

        self._cancel_event.clear()
        self._run_button.state(["disabled"])
        self._cancel_button.state(["!disabled"])
        self._progress.configure(maximum=max(len(selected_keys), 1), value=0)
        self._set_status(
            f"실행 중 (0/{len(selected_keys)}개 항목, "
            f"{describe_connection_inputs(self._connection_inputs)})...",
            _STATUS_RUNNING_COLOR,
        )
        self._tree.delete(*self._tree.get_children())
        self._set_action_text("")
        self._report_var.set("")

        thread = threading.Thread(
            target=self._run_in_background,
            args=(equipment_id, args, selected_keys, len(selected_keys)),
            daemon=True,
        )
        thread.start()
        self.after(100, self._poll_result_queue)

    def _on_cancel_clicked(self) -> None:
        self._cancel_event.set()
        self._cancel_button.state(["disabled"])
        self._set_status(
            "취소 요청됨 — 현재 실행 중인 항목을 마치고 중단합니다...", _STATUS_WARNING_COLOR
        )

    def _run_in_background(
        self, equipment_id: str, args, selected_keys: set[str], total: int
    ) -> None:
        # UI 스레드를 막지 않도록 별도 스레드에서 실행한다. Tkinter 위젯은 이
        # 스레드에서 직접 건드리지 않고, 큐로 메시지만 전달한다(스레드 안전).
        def on_progress(_key: str, label: str) -> None:
            self._result_queue.put(("progress", (label, total)))

        def should_continue() -> bool:
            return not self._cancel_event.is_set()

        try:
            outcome = execute_selected(
                args, selected_keys, on_progress=on_progress, should_continue=should_continue
            )
        except Exception as exc:  # noqa: BLE001 - GUI 스레드로 예외 메시지를 전달하기 위함
            self._result_queue.put(("error", exc))
            return
        self._result_queue.put(("done", (equipment_id, outcome)))

    def _poll_result_queue(self) -> None:
        try:
            kind, payload = self._result_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_result_queue)
            return

        if kind == "progress":
            label, total = payload
            self._progress.configure(value=self._progress["value"] + 1)
            done = int(self._progress["value"])
            self._set_status(f"실행 중 ({done}/{total}개 항목)... 방금 완료: {label}", _STATUS_RUNNING_COLOR)
            self.after(100, self._poll_result_queue)
            return

        self._run_button.state(["!disabled"])
        self._cancel_button.state(["disabled"])
        if kind == "error":
            self._set_status("오류 발생", _STATUS_ERROR_COLOR)
            messagebox.showerror(PROGRAM_NAME, f"실행 중 오류가 발생했습니다:\n{payload}")
            return

        equipment_id, outcome = payload
        self._render_outcome(equipment_id, outcome)

    def _render_outcome(self, equipment_id: str, outcome: RunAllOutcome) -> None:
        for result in outcome.all_results:
            self._tree.insert(
                "",
                "end",
                values=(VERDICT_LABEL[result.verdict], result.check_item, format_detail_cell(result)),
                tags=(result.verdict.value,),
            )

        self._set_action_text(format_action_items(equipment_id, outcome.action_items))

        if outcome.cancelled:
            status = f"취소됨 ({len(outcome.all_results)}개 항목까지 실행)"
            color = _STATUS_WARNING_COLOR
        elif outcome.escalated:
            status = (
                "완료 (" + datetime.now().strftime("%H:%M:%S") + ")"
                " — C분류 재Scan 상한 초과, 작업자 개입 필요"
            )
            color = _STATUS_WARNING_COLOR
        else:
            status = "완료 (" + datetime.now().strftime("%H:%M:%S") + ")"
            color = _STATUS_DONE_COLOR
        self._set_status(status, color)
        self._report_var.set(f"결과 저장 위치: {outcome.report_path}")

    def _set_status(self, text: str, color: str = _STATUS_NEUTRAL_COLOR) -> None:
        self._status_var.set(text)
        self._status_label.configure(foreground=color)

    def _set_action_text(self, content: str) -> None:
        self._action_text.configure(state="normal")
        self._action_text.delete("1.0", "end")
        self._action_text.insert("1.0", content)
        self._action_text.configure(state="disabled")

    def _open_gate_window(self) -> None:
        CriteriaGateWindow(self)

    def _open_connection_settings(self) -> None:
        ConnectionSettingsDialog(self, self._connection_inputs, on_saved=self._apply_connection_inputs)

    def _apply_connection_inputs(self, inputs: ConnectionInputs) -> None:
        self._connection_inputs = inputs
        self._connection_summary_var.set(describe_connection_inputs(inputs))

    def _open_report_history(self) -> None:
        ReportHistoryWindow(self)


class CriteriaGateWindow(tk.Toplevel):
    """기준(Criteria) 목록을 보고, 값(min/max)을 고치거나 Gate 상태를 한
    단계씩 전진시키는 별도 창.

    값을 고치면 core/thresholds.py의 설계대로 새 버전이 GENERATED 상태로
    등록된다 — 기존 Gate 단계는 유지되지 않고 처음부터 다시 검증을 거쳐야
    한다(값이 바뀌었으니 당연하다).
    """

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("기준값 Gate 관리")
        _center_window(self, 900, 480)
        self.transient(master)

        self._rows: list[tuple[str, object]] = []  # (store_path, Criteria) — 선택된 항목 조회용
        self._build_widgets()
        self._reload()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(
            top,
            text="행을 고르고 값을 수정하거나 Gate를 다음 단계로 전진시키세요 (더블클릭으로도 값 수정).",
            foreground=_MUTED_TEXT_COLOR,
        ).pack(side="left")
        ttk.Button(top, text="새로고침", command=self._reload).pack(side="right")

        self._tree = ttk.Treeview(self, columns=GATE_COLUMNS, show="headings", height=15)
        headings = {
            "store": "기준 파일",
            "check_item": "항목",
            "key": "Key",
            "version": "버전",
            "range": "범위",
            "gate_status": "Gate 상태",
            "updated_at": "수정 시각",
        }
        widths = {
            "store": 190,
            "check_item": 150,
            "key": 150,
            "version": 50,
            "range": 140,
            "gate_status": 90,
            "updated_at": 140,
        }
        for column in GATE_COLUMNS:
            self._tree.heading(column, text=headings[column])
            self._tree.column(column, width=widths[column], anchor="w", stretch=False)
        self._tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._tree.bind("<<TreeviewSelect>>", lambda _event: self._update_buttons())
        self._tree.bind("<Double-1>", lambda _event: self._on_edit_clicked())

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")
        self._edit_button = ttk.Button(
            bottom, text="값 수정...", command=self._on_edit_clicked, state="disabled"
        )
        self._edit_button.pack(side="left")
        self._advance_button = ttk.Button(
            bottom, text="다음 단계로 전진", command=self._on_advance_clicked, state="disabled"
        )
        self._advance_button.pack(side="left", padx=(6, 0))

    def _reload(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._rows = list_criteria_rows()
        for store_path, criteria in self._rows:
            self._tree.insert("", "end", values=format_criteria_row(store_path, criteria))
        self._update_buttons()

    def _selected_row(self):
        selection = self._tree.selection()
        if not selection:
            return None
        index = self._tree.index(selection[0])
        return self._rows[index]

    def _update_buttons(self) -> None:
        selected = self._selected_row()
        if selected is None:
            self._edit_button.state(["disabled"])
            self._advance_button.state(["disabled"])
            self._advance_button.configure(text="다음 단계로 전진")
            return

        _store_path, criteria = selected
        self._edit_button.state(["!disabled"])

        target = next_status(criteria.gate_status)
        if target is None:
            self._advance_button.state(["disabled"])
            self._advance_button.configure(text="이미 최종 단계(APPLIED)")
        else:
            self._advance_button.state(["!disabled"])
            self._advance_button.configure(text=f"{target.value}(으)로 전진")

    def _on_edit_clicked(self) -> None:
        selected = self._selected_row()
        if selected is None:
            return
        store_path, criteria = selected
        EditCriteriaDialog(self, store_path, criteria, on_saved=self._reload)

    def _on_advance_clicked(self) -> None:
        selected = self._selected_row()
        if selected is None:
            return
        store_path, criteria = selected
        target = next_status(criteria.gate_status)
        if target is None:
            return

        confirmed = messagebox.askyesno(
            "기준값 Gate 관리",
            f"{criteria.check_item} / {criteria.key}의 Gate를 "
            f"{criteria.gate_status.value} → {target.value}(으)로 전진시키겠습니까?\n"
            "이 동작은 되돌릴 수 없습니다 (역행 불가).",
            parent=self,
        )
        if not confirmed:
            return

        try:
            advance_criteria_gate(store_path, criteria.check_item, criteria.key, target)
        except Exception as exc:  # noqa: BLE001 - 사용자에게 그대로 원인을 보여주기 위함
            messagebox.showerror("기준값 Gate 관리", f"Gate 전진에 실패했습니다:\n{exc}", parent=self)
            return

        self._reload()


class EditCriteriaDialog(tk.Toplevel):
    """선택한 기준의 min/max 값을 고쳐 새 버전으로 등록하는 모달 대화상자.

    저장하면 core/thresholds.py의 설계대로 새 버전이 GENERATED 상태로
    등록된다 — 여기서 Gate 단계까지 같이 정하지는 않는다.
    """

    def __init__(
        self,
        master: tk.Misc,
        store_path: str,
        criteria,
        on_saved,
    ) -> None:
        super().__init__(master)
        self._store_path = store_path
        self._criteria = criteria
        self._on_saved = on_saved

        self.title("기준값 수정")
        self.transient(master)
        self.resizable(False, False)
        self._build_widgets()
        _center_window(self, self.winfo_reqwidth(), self.winfo_reqheight())
        self.grab_set()

    def _build_widgets(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"{self._criteria.check_item} / {self._criteria.key}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        ttk.Label(frame, text="최소값:").grid(row=1, column=0, sticky="w")
        self._min_var = tk.StringVar(value=str(self._criteria.min_value))
        min_entry = ttk.Entry(frame, textvariable=self._min_var, width=16)
        min_entry.grid(row=1, column=1, pady=2)

        ttk.Label(frame, text="최대값:").grid(row=2, column=0, sticky="w")
        self._max_var = tk.StringVar(value=str(self._criteria.max_value))
        ttk.Entry(frame, textvariable=self._max_var, width=16).grid(row=2, column=1, pady=2)

        ttk.Label(
            frame,
            text="저장하면 새 버전(GENERATED)으로 등록되어 Gate 검증을\n처음부터 다시 거쳐야 합니다.",
            foreground=_MUTED_TEXT_COLOR,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 8))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="저장", command=self._on_save_clicked).pack(
            side="right", padx=(0, 6)
        )

        min_entry.focus_set()
        self.bind("<Return>", lambda _event: self._on_save_clicked())
        self.bind("<Escape>", lambda _event: self.destroy())

    def _on_save_clicked(self) -> None:
        try:
            min_value, max_value = parse_min_max(self._min_var.get(), self._max_var.get())
        except ValueError as exc:
            messagebox.showerror("기준값 수정", str(exc), parent=self)
            return

        try:
            save_criteria_value(
                self._store_path, self._criteria.check_item, self._criteria.key, min_value, max_value
            )
        except Exception as exc:  # noqa: BLE001 - 사용자에게 그대로 원인을 보여주기 위함
            messagebox.showerror("기준값 수정", f"저장에 실패했습니다:\n{exc}", parent=self)
            return

        self.destroy()
        self._on_saved()


class ConnectionSettingsDialog(tk.Toplevel):
    """실제 설비 연동(제어 프로그램/PPMAC/검사 프로그램 TCP, PC WMI) 호스트·포트를
    입력하는 대화상자. 호스트를 비워두면 그 항목은 계속 Mock으로 실행된다 —
    CLI의 --control-program-host 등과 동일한 규칙이다.
    """

    def __init__(self, master: tk.Misc, current: ConnectionInputs, on_saved) -> None:
        super().__init__(master)
        self._on_saved = on_saved

        self.title("연동 설정")
        self.transient(master)
        self.resizable(False, False)
        self._build_widgets(current)
        _center_window(self, self.winfo_reqwidth(), self.winfo_reqheight())
        self.grab_set()

    def _build_widgets(self, current: ConnectionInputs) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="호스트를 비워두면 그 항목은 Mock으로 실행됩니다.",
            foreground=_MUTED_TEXT_COLOR,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._control_host_var = tk.StringVar(value=current.control_program_host)
        self._control_port_var = tk.StringVar(value=current.control_program_port)
        self._add_host_port_row(
            frame, 1, "제어 프로그램(C#, CC-Link):", self._control_host_var, self._control_port_var
        )

        self._ppmac_host_var = tk.StringVar(value=current.ppmac_host)
        self._ppmac_port_var = tk.StringVar(value=current.ppmac_port)
        self._add_host_port_row(frame, 2, "PPMAC:", self._ppmac_host_var, self._ppmac_port_var)

        self._inspection_host_var = tk.StringVar(value=current.inspection_program_host)
        self._inspection_port_var = tk.StringVar(value=current.inspection_program_port)
        self._add_host_port_row(
            frame, 3, "검사 프로그램(C++):", self._inspection_host_var, self._inspection_port_var
        )

        self._use_wmi_var = tk.BooleanVar(value=current.use_wmi)
        ttk.Checkbutton(
            frame, text="PC 동작 Check: WMI로 실제 조회 (Windows 전용)", variable=self._use_wmi_var
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="저장", command=self._on_save_clicked).pack(
            side="right", padx=(0, 6)
        )

        self.bind("<Return>", lambda _event: self._on_save_clicked())
        self.bind("<Escape>", lambda _event: self.destroy())

    @staticmethod
    def _add_host_port_row(
        frame: ttk.Frame, row: int, label: str, host_var: tk.StringVar, port_var: tk.StringVar
    ) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(frame, textvariable=host_var, width=18).grid(row=row, column=1, padx=(4, 4))
        ttk.Entry(frame, textvariable=port_var, width=8).grid(row=row, column=2)

    def _current_inputs(self) -> ConnectionInputs:
        return ConnectionInputs(
            control_program_host=self._control_host_var.get(),
            control_program_port=self._control_port_var.get(),
            ppmac_host=self._ppmac_host_var.get(),
            ppmac_port=self._ppmac_port_var.get(),
            inspection_program_host=self._inspection_host_var.get(),
            inspection_program_port=self._inspection_port_var.get(),
            use_wmi=self._use_wmi_var.get(),
        )

    def _on_save_clicked(self) -> None:
        candidate = self._current_inputs()
        try:
            # 실제로 실행하진 않고, 입력값(숫자 여부/host-port 짝)만 검증한다.
            build_connected_run_all_args("_connection_settings_validation", candidate)
        except ValueError as exc:
            messagebox.showerror("연동 설정", str(exc), parent=self)
            return

        self.destroy()
        self._on_saved(candidate)


class ReportHistoryWindow(tk.Toplevel):
    """`reports/` 폴더에 저장된 과거 실행 리포트를 목록에서 골라 내용을 읽어보는 창.

    표시만 하며, 아무것도 고치거나 지우지 않는다.
    """

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("리포트 열람")
        _center_window(self, 900, 560)
        self.transient(master)

        self._reports: list = []  # list_report_files()가 반환한 ReportFileInfo — 선택된 항목 조회용
        self._build_widgets()
        self._reload()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="설비 ID 필터:").pack(side="left")
        self._filter_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(top, textvariable=self._filter_var, width=14)
        filter_entry.pack(side="left", padx=(4, 6))
        filter_entry.bind("<Return>", lambda _event: self._reload())
        ttk.Button(top, text="필터", command=self._reload).pack(side="left")
        ttk.Button(
            top, text="전체 보기", command=lambda: (self._filter_var.set(""), self._reload())
        ).pack(side="left", padx=(4, 0))

        ttk.Button(top, text="새로고침", command=self._reload).pack(side="right")
        ttk.Button(top, text="폴더 열기", command=self._open_reports_folder).pack(
            side="right", padx=(0, 6)
        )

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        list_frame = ttk.Frame(body)
        list_frame.pack(side="left", fill="y")

        columns = ("equipment_id", "measured_at", "filename")
        self._tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=20, selectmode="browse"
        )
        self._tree.heading("equipment_id", text="설비 ID")
        self._tree.heading("measured_at", text="실행 시각")
        self._tree.heading("filename", text="파일명")
        self._tree.column("equipment_id", width=80, anchor="w", stretch=False)
        self._tree.column("measured_at", width=140, anchor="w", stretch=False)
        self._tree.column("filename", width=180, anchor="w", stretch=False)
        self._tree.pack(side="left", fill="y")
        self._tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected())

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        scrollbar.pack(side="left", fill="y")
        self._tree.configure(yscrollcommand=scrollbar.set)

        content_frame = ttk.LabelFrame(body, text="내용", padding=6)
        content_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self._content_text = tk.Text(
            content_frame, wrap="none", state="disabled", font="TkFixedFont"
        )
        self._content_text.pack(fill="both", expand=True)

    def _reload(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._reports = list_report_files(equipment_id_filter=self._filter_var.get().strip())
        for info in self._reports:
            self._tree.insert("", "end", values=format_report_row(info))
        self._set_content("")
        if not self._reports:
            self._set_content("저장된 리포트가 없습니다.")

    def _selected_report(self):
        selection = self._tree.selection()
        if not selection:
            return None
        index = self._tree.index(selection[0])
        return self._reports[index]

    def _show_selected(self) -> None:
        info = self._selected_report()
        if info is None:
            return
        try:
            text = read_report_text(info)
        except OSError as exc:
            self._set_content(f"파일을 읽을 수 없습니다: {exc}")
            return
        self._set_content(text)

    def _set_content(self, text: str) -> None:
        self._content_text.configure(state="normal")
        self._content_text.delete("1.0", "end")
        self._content_text.insert("1.0", text)
        self._content_text.configure(state="disabled")

    def _open_reports_folder(self) -> None:
        # Windows 전용 기능 — 다른 OS(예: 이 저장소의 개발 컨테이너)에서는 조용히
        # 안내만 하고 실패하지 않는다.
        os.makedirs(REPORTS_DIR, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(os.path.abspath(REPORTS_DIR))  # noqa: S606
        else:
            messagebox.showinfo(
                "리포트 열람",
                f"리포트 폴더 위치:\n{os.path.abspath(REPORTS_DIR)}",
                parent=self,
            )


def main() -> int:
    app = HWSelfCheckApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
