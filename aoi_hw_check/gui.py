"""AOI H/W Self-Check 자동화 프로그램의 GUI (Tkinter, 표준 라이브러리만 사용).

설비 PC는 인터넷이 안 될 수 있어 추가 패키지 설치가 필요 없는 Tkinter로
만든다. 체크박스로 13개 항목(C분류는 6항목이 기준 시료 1회 Scan을 공유해
한 단위) 중 원하는 것만 골라 실행할 수 있고, 기본값은 전체 선택이라 아무것도
바꾸지 않으면 run.bat과 같은 전체 실행이 된다. 실제 판정 로직은 CLI와 동일하게
`aoi_hw_check.cli.execute_selected`를 그대로 재사용한다 — GUI는 표시 방식만
다를 뿐 판정 로직을 따로 구현하지 않는다.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from aoi_hw_check import __version__
from aoi_hw_check.cli import RunAllOutcome, execute_selected
from aoi_hw_check.cli_output import PROGRAM_NAME
from aoi_hw_check.gui_support import (
    DEFAULT_EQUIPMENT_ID,
    GATE_COLUMNS,
    SELECTABLE_ITEMS,
    VERDICT_COLOR,
    VERDICT_LABEL,
    ConnectionInputs,
    advance_criteria_gate,
    build_connected_run_all_args,
    describe_connection_inputs,
    format_action_items,
    format_criteria_row,
    format_detail_cell,
    list_criteria_rows,
    next_status,
    parse_min_max,
    save_criteria_value,
)


class HWSelfCheckApp(tk.Tk):
    """13개 항목 run-all을 버튼 클릭으로 실행하고 결과를 표로 보여주는 메인 창."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{PROGRAM_NAME} (v{__version__})")
        self.geometry("900x620")
        self.minsize(760, 480)

        self._result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._connection_inputs = ConnectionInputs()
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

        self._status_var = tk.StringVar(value="대기 중")
        ttk.Label(top, textvariable=self._status_var).pack(side="left", padx=12)

        ttk.Button(top, text="기준값 Gate 관리...", command=self._open_gate_window).pack(
            side="right"
        )
        ttk.Button(top, text="연동 설정...", command=self._open_connection_settings).pack(
            side="right", padx=(0, 6)
        )

        conn_bar = ttk.Frame(self, padding=(10, 0, 10, 6))
        conn_bar.pack(fill="x")
        self._connection_summary_var = tk.StringVar(
            value=describe_connection_inputs(self._connection_inputs)
        )
        ttk.Label(conn_bar, textvariable=self._connection_summary_var, foreground="#555555").pack(
            anchor="w"
        )

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        selection_frame = ttk.LabelFrame(body, text="실행할 항목", padding=8)
        selection_frame.pack(side="left", fill="y", padx=(0, 10))

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

        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)

        columns = ("verdict", "check_item", "detail")
        self._tree = ttk.Treeview(content, columns=columns, show="headings", height=15)
        self._tree.heading("verdict", text="판정")
        self._tree.heading("check_item", text="항목")
        self._tree.heading("detail", text="상세")
        self._tree.column("verdict", width=70, anchor="center", stretch=False)
        self._tree.column("check_item", width=220, anchor="w", stretch=False)
        self._tree.column("detail", width=560, anchor="w")
        self._tree.pack(fill="both", expand=True, pady=(0, 10))

        for verdict, color in VERDICT_COLOR.items():
            self._tree.tag_configure(verdict.value, foreground=color)

        action_frame = ttk.LabelFrame(content, text="조치 대상 목록", padding=8)
        action_frame.pack(fill="both", expand=False, pady=(0, 10))
        self._action_text = tk.Text(action_frame, height=6, wrap="word", state="disabled")
        self._action_text.pack(fill="both", expand=True)

        self._report_var = tk.StringVar(value="")
        ttk.Label(content, textvariable=self._report_var, foreground="#555555").pack(anchor="w")

    def _set_all_items(self, checked: bool) -> None:
        for var in self._item_vars.values():
            var.set(checked)

    def _selected_item_keys(self) -> set[str]:
        return {key for key, var in self._item_vars.items() if var.get()}

    def _on_run_clicked(self) -> None:
        equipment_id = self._equipment_id_var.get().strip()
        if not equipment_id:
            messagebox.showwarning(PROGRAM_NAME, "설비 ID를 입력하세요.")
            return

        selected_keys = self._selected_item_keys()
        if not selected_keys:
            messagebox.showwarning(PROGRAM_NAME, "실행할 항목을 하나 이상 선택하세요.")
            return

        # 연동 설정(호스트/포트) 검증은 메인 스레드에서 미리 해서, 잘못된 입력이면
        # 스레드를 띄우지도 않고 바로 알려준다 — "연동 설정..." 창에서 저장할 때도
        # 같은 검증을 거치므로 보통은 여기서 실패하지 않는다.
        try:
            args = build_connected_run_all_args(equipment_id, self._connection_inputs)
        except ValueError as exc:
            messagebox.showwarning(PROGRAM_NAME, str(exc))
            return

        self._run_button.state(["disabled"])
        self._status_var.set(
            f"실행 중 ({len(selected_keys)}개 항목, "
            f"{describe_connection_inputs(self._connection_inputs)})..."
        )
        self._tree.delete(*self._tree.get_children())
        self._set_action_text("")
        self._report_var.set("")

        thread = threading.Thread(
            target=self._run_in_background, args=(equipment_id, args, selected_keys), daemon=True
        )
        thread.start()
        self.after(100, self._poll_result_queue)

    def _run_in_background(self, equipment_id: str, args, selected_keys: set[str]) -> None:
        # UI 스레드를 막지 않도록 별도 스레드에서 실행하고, 결과/예외는 큐로 전달한다.
        try:
            outcome = execute_selected(args, selected_keys)
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

        self._run_button.state(["!disabled"])
        if kind == "error":
            self._status_var.set("오류 발생")
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

        status = "완료 (" + datetime.now().strftime("%H:%M:%S") + ")"
        if outcome.escalated:
            status += " — C분류 재Scan 상한 초과, 작업자 개입 필요"
        self._status_var.set(status)
        self._report_var.set(f"결과 저장 위치: {outcome.report_path}")

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
        self.geometry("900x480")
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
            foreground="#555555",
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
            foreground="#555555",
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
        self.grab_set()

    def _build_widgets(self, current: ConnectionInputs) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="호스트를 비워두면 그 항목은 Mock으로 실행됩니다.",
            foreground="#555555",
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


def main() -> int:
    app = HWSelfCheckApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
