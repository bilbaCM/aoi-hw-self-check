"""AOI H/W Self-Check 자동화 프로그램의 GUI (Tkinter, 표준 라이브러리만 사용).

설비 PC는 인터넷이 안 될 수 있어 추가 패키지 설치가 필요 없는 Tkinter로
만든다. 1차 범위는 run-all(13개 항목 전부 실행) 결과를 표로 보여주는 것으로
한정하고, 실제 판정 로직은 CLI와 동일하게 `aoi_hw_check.cli.execute_run_all`을
그대로 재사용한다 — GUI는 표시 방식만 다를 뿐 판정 로직을 따로 구현하지 않는다.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from aoi_hw_check import __version__
from aoi_hw_check.cli import RunAllOutcome, execute_run_all
from aoi_hw_check.cli_output import PROGRAM_NAME
from aoi_hw_check.gui_support import (
    DEFAULT_EQUIPMENT_ID,
    VERDICT_COLOR,
    VERDICT_LABEL,
    build_run_all_args,
    format_action_items,
    format_detail_cell,
)


class HWSelfCheckApp(tk.Tk):
    """13개 항목 run-all을 버튼 클릭으로 실행하고 결과를 표로 보여주는 메인 창."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{PROGRAM_NAME} (v{__version__})")
        self.geometry("900x620")
        self.minsize(760, 480)

        self._result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_widgets()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="설비 ID:").pack(side="left")
        self._equipment_id_var = tk.StringVar(value=DEFAULT_EQUIPMENT_ID)
        entry = ttk.Entry(top, textvariable=self._equipment_id_var, width=16)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<Return>", lambda _event: self._on_run_clicked())

        self._run_button = ttk.Button(top, text="전체 실행 (13개 항목)", command=self._on_run_clicked)
        self._run_button.pack(side="left")

        self._status_var = tk.StringVar(value="대기 중")
        ttk.Label(top, textvariable=self._status_var).pack(side="left", padx=12)

        columns = ("verdict", "check_item", "detail")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self._tree.heading("verdict", text="판정")
        self._tree.heading("check_item", text="항목")
        self._tree.heading("detail", text="상세")
        self._tree.column("verdict", width=70, anchor="center", stretch=False)
        self._tree.column("check_item", width=220, anchor="w", stretch=False)
        self._tree.column("detail", width=560, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for verdict, color in VERDICT_COLOR.items():
            self._tree.tag_configure(verdict.value, foreground=color)

        action_frame = ttk.LabelFrame(self, text="조치 대상 목록", padding=8)
        action_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self._action_text = tk.Text(action_frame, height=6, wrap="word", state="disabled")
        self._action_text.pack(fill="both", expand=True)

        self._report_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._report_var, foreground="#555555").pack(
            anchor="w", padx=10, pady=(0, 10)
        )

    def _on_run_clicked(self) -> None:
        equipment_id = self._equipment_id_var.get().strip()
        if not equipment_id:
            messagebox.showwarning(PROGRAM_NAME, "설비 ID를 입력하세요.")
            return

        self._run_button.state(["disabled"])
        self._status_var.set("실행 중 (Mock, 13개 항목)...")
        self._tree.delete(*self._tree.get_children())
        self._set_action_text("")
        self._report_var.set("")

        thread = threading.Thread(target=self._run_in_background, args=(equipment_id,), daemon=True)
        thread.start()
        self.after(100, self._poll_result_queue)

    def _run_in_background(self, equipment_id: str) -> None:
        # UI 스레드를 막지 않도록 별도 스레드에서 실행하고, 결과/예외는 큐로 전달한다.
        try:
            outcome = execute_run_all(build_run_all_args(equipment_id))
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


def main() -> int:
    app = HWSelfCheckApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
