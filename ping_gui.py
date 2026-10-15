"""Windows Ping monitor. Run: python ping_gui.py"""

import csv
import json
import locale
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


# 中文名、英文名、实际 Ping 的地址
PRESETS = [
    ("本机", "Localhost", "127.0.0.1"),
    ("Google", "Google", "google.com"),
    ("Bing", "Bing", "bing.com"),
    ("百度", "Baidu", "baidu.com"),
    ("GitHub", "GitHub", "github.com"),
    ("Cloudflare", "Cloudflare", "cloudflare.com"),
    ("自定义", "Custom", ""),
]

# 一个键对应一组（中文，英文）。新增界面文字只需在这里加一行。
WORDS = {
    "title": ("Ping 网络监测", "Ping Monitor"),
    "language": ("语言", "Language"),
    "settings": ("监测设置", "Settings"),
    "preset": ("常用目标", "Common targets"),
    "host": ("目标地址", "Target address"),
    "count": ("次数（1–100）", "Count (1–100)"),
    "interval": ("间隔（1000–60000 ms）", "Interval (1000–60000 ms)"),
    "timeout": ("超时（100–60000 ms）", "Timeout (100–60000 ms)"),
    "duration": ("持续时间（1–300 秒）", "Duration (1–300 s)"),
    "start": ("开始监测", "Start"),
    "stop": ("停止", "Stop"),
    "export": ("导出 CSV", "Export CSV"),
    "last": ("上次监测：{}", "Last target: {}"),
    "none": ("暂无", "None"),
    "elapsed": ("已运行：{:.1f} 秒 / 设定：{} 秒", "Elapsed: {:.1f} s / limit: {} s"),
    "summary": ("发送 {}  |  收到 {}  |  丢包 {:.1f}%  |  {}",
                "Sent {}  |  Received {}  |  Loss {:.1f}%  |  {}"),
    "latency": ("最小 {:g} / 平均 {:.1f} / 最大 {:g} ms",
                "Min {:g} / Avg {:.1f} / Max {:g} ms"),
    "no_latency": ("暂无延迟数据", "No latency data"),
    "ready": ("就绪", "Ready"),
    "running": ("监测中…", "Monitoring…"),
    "stopping": ("正在停止…", "Stopping…"),
    "done_count": ("已达到次数上限", "Count limit reached"),
    "done_time": ("已达到时间上限", "Time limit reached"),
    "stopped": ("已停止", "Stopped"),
    "memory_error": ("上次目标无法保存", "Could not save the last target"),
    "success": ("成功", "Success"),
    "failure": ("失败", "Failed"),
    "reply": ("收到回复", "Reply received"),
    "no_reply": ("未收到回复或系统失败", "No reply or a system error"),
    "column_time": ("时间", "Time"),
    "column_host": ("目标", "Target"),
    "column_status": ("状态", "Status"),
    "column_latency": ("延迟 ms", "Latency ms"),
    "column_detail": ("说明", "Details"),
    "choose": ("请先选择常用目标或自定义。", "Select a target or Custom first."),
    "bad_host": ("请输入主机名或 IP，不要输入 https://。",
                 "Enter a hostname or IP address without https://."),
    "numbers": ("数字设置只能填写数字。", "Number fields accept digits only."),
    "count_range": ("次数必须在 1–100 之间。", "Count must be 1–100."),
    "interval_range": ("间隔必须在 1000–60000 毫秒之间。",
                       "Interval must be 1000–60000 ms."),
    "timeout_range": ("超时必须在 100–60000 毫秒之间。",
                      "Timeout must be 100–60000 ms."),
    "duration_range": ("持续时间必须在 1–300 秒之间。",
                       "Duration must be 1–300 seconds."),
    "input_error": ("输入有误", "Invalid input"),
    "no_data": ("请先运行一次监测。", "Run a monitoring session first."),
    "saved": ("已保存到：\n{}", "Saved to:\n{}"),
    "save_error": ("导出失败", "Export failed"),
    "footer": ("使用系统 ICMP ping；有些网络会屏蔽 ICMP。",
               "Uses ICMP ping; some networks block ICMP."),
}


def digits_only(value):
    """输入过程中允许暂时留空，但不能输入字母或超过 5 位。"""
    return len(value) <= 5 and all("0" <= char <= "9" for char in value)


def valid_host(host):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", host)) and ".." not in host


def parse_latency(output):
    """从 Windows Ping 输出中读取 time=12ms 或 时间<1ms。"""
    match = re.search(r"(?:\btime|时间)\s*([=<])\s*(\d+(?:[.,]\d+)?)", output, re.I)
    if not match:
        return None
    value = float(match.group(2).replace(",", "."))
    return 0.5 if match.group(1) == "<" and value == 1 else value


def settings_file():
    program = sys.executable if getattr(sys, "frozen", False) else __file__
    return Path(program).resolve().parent / "ping-monitor-settings.json"


def load_last_host():
    try:
        host = json.loads(settings_file().read_text(encoding="utf-8"))["last_target"]
        return host if isinstance(host, str) and valid_host(host) else ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def save_last_host(host):
    settings_file().write_text(
        json.dumps({"last_target": host}, ensure_ascii=False), encoding="utf-8"
    )


class PingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("850x600")
        self.minsize(720, 500)

        self.lang = 0  # 0=中文，1=英文
        self.preset_index = -1
        self.last_host = load_last_host()
        self.memory_error = False
        self.status = "ready"
        self.running = False
        self.started = None
        self.elapsed = 0.0
        self.duration_limit = 60
        self.process = None
        self.stop_event = threading.Event()
        self.events = queue.Queue()
        self.results = []  # 每项：(时间、地址、成功与否、延迟)

        self.language_var = tk.StringVar(value="中文")
        self.preset_var = tk.StringVar()
        self.values = {
            "host": tk.StringVar(),
            "count": tk.StringVar(value="10"),
            "interval": tk.StringVar(value="1000"),
            "timeout": tk.StringVar(value="1000"),
            "duration": tk.StringVar(value="60"),
        }

        self.build_window()
        self.translate_window()
        self.after(100, self.check_events)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def t(self, key):
        return WORDS[key][self.lang]

    def build_window(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 10))
        self.language_label = ttk.Label(top)
        self.language_label.pack(side="right", padx=(8, 0))
        language_box = ttk.Combobox(
            top, textvariable=self.language_var, values=("中文", "English"),
            state="readonly", width=9
        )
        language_box.pack(side="right")
        language_box.bind("<<ComboboxSelected>>", self.change_language)

        self.settings_box = ttk.LabelFrame(outer, padding=12)
        self.settings_box.pack(fill="x")
        self.labels = {}
        self.labels["preset"] = ttk.Label(self.settings_box)
        self.labels["preset"].grid(row=0, column=0, sticky="w")
        self.preset_box = ttk.Combobox(
            self.settings_box, textvariable=self.preset_var,
            state="readonly", width=14
        )
        self.preset_box.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.preset_box.bind("<<ComboboxSelected>>", self.choose_preset)

        self.labels["host"] = ttk.Label(self.settings_box)
        self.labels["host"].grid(row=0, column=1, columnspan=3, sticky="w")
        self.host_entry = ttk.Entry(
            self.settings_box, textvariable=self.values["host"], state="readonly"
        )
        self.host_entry.grid(row=1, column=1, columnspan=3, sticky="ew")
        for col, weight in enumerate((1, 2, 1, 1)):
            self.settings_box.columnconfigure(col, weight=weight)

        check_digits = (self.register(digits_only), "%P")
        self.number_entries = []
        for col, name in enumerate(("count", "interval", "timeout", "duration")):
            self.labels[name] = ttk.Label(self.settings_box)
            self.labels[name].grid(row=2, column=col, sticky="w", pady=(12, 0))
            entry = ttk.Entry(
                self.settings_box, textvariable=self.values[name],
                validate="key", validatecommand=check_digits
            )
            entry.grid(row=3, column=col, sticky="ew", padx=(0, 10))
            self.number_entries.append(entry)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=12)
        self.start_button = ttk.Button(actions, command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.export_button = ttk.Button(actions, command=self.export_csv)
        self.export_button.pack(side="left")
        self.status_label = ttk.Label(actions)
        self.status_label.pack(side="right")

        self.last_label = ttk.Label(outer)
        self.last_label.pack(fill="x", pady=(0, 8))
        self.elapsed_label = ttk.Label(outer)
        self.elapsed_label.pack(fill="x", pady=(0, 8))
        self.summary_label = ttk.Label(outer, font=("Segoe UI", 11, "bold"))
        self.summary_label.pack(fill="x", pady=(0, 10))

        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(
            table_frame, columns=("time", "host", "status", "latency", "detail"),
            show="headings"
        )
        for name, width in zip(
            ("time", "host", "status", "latency", "detail"),
            (160, 180, 80, 100, 280)
        ):
            self.table.column(name, width=width, minwidth=60)
        self.table.tag_configure("failed", foreground="#b3261e")
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.footer_label = ttk.Label(outer, foreground="#555555")
        self.footer_label.pack(anchor="w", pady=(10, 0))

    def change_language(self, _event=None):
        self.lang = 1 if self.language_var.get() == "English" else 0
        self.translate_window()

    def translate_window(self):
        """切换语言时重新填写文字，不清空用户设置和结果。"""
        self.title(self.t("title"))
        self.language_label.config(text=self.t("language"))
        self.settings_box.config(text=self.t("settings"))
        for key, label in self.labels.items():
            label.config(text=self.t(key))
        self.preset_box.config(values=[item[self.lang] for item in PRESETS])
        if self.preset_index >= 0:
            self.preset_box.current(self.preset_index)
        self.start_button.config(text=self.t("start"))
        self.stop_button.config(text=self.t("stop"))
        self.export_button.config(text=self.t("export"))
        self.footer_label.config(text=self.t("footer"))
        for name in ("time", "host", "status", "latency", "detail"):
            self.table.heading(name, text=self.t("column_" + name))
        self.show_info()
        self.redraw_results()

    def choose_preset(self, _event=None):
        self.preset_index = self.preset_box.current()
        if self.preset_index < 0:
            return
        host = PRESETS[self.preset_index][2]
        self.values["host"].set(host)
        self.host_entry.config(
            state="normal" if self.preset_index == len(PRESETS) - 1 else "readonly"
        )
        if self.preset_index == len(PRESETS) - 1:
            self.host_entry.focus_set()

    def show_info(self):
        self.last_label.config(
            text=self.t("last").format(self.last_host or self.t("none"))
        )
        elapsed = time.monotonic() - self.started if self.running else self.elapsed
        self.elapsed_label.config(
            text=self.t("elapsed").format(elapsed, self.duration_limit)
        )
        sent = len(self.results)
        received = sum(row[2] for row in self.results)
        times = [row[3] for row in self.results if row[3] is not None]
        loss = 100 * (sent - received) / sent if sent else 0
        latency = (
            self.t("latency").format(min(times), sum(times) / len(times), max(times))
            if times else self.t("no_latency")
        )
        self.summary_label.config(
            text=self.t("summary").format(sent, received, loss, latency)
        )
        status = self.t(self.status)
        if self.memory_error:
            status += " · " + self.t("memory_error")
        self.status_label.config(text=status)

    def add_result(self, row):
        timestamp, host, success, latency = row
        self.table.insert(
            "", "end",
            values=(
                timestamp, host,
                self.t("success") if success else self.t("failure"),
                f"{latency:g}" if latency is not None else "—",
                self.t("reply") if success else self.t("no_reply")
            ),
            tags=() if success else ("failed",)
        )

    def redraw_results(self):
        for item in self.table.get_children():
            self.table.delete(item)
        for row in self.results:
            self.add_result(row)
        self.table.yview_moveto(1)

    def read_inputs(self):
        if self.preset_index < 0:
            raise ValueError(self.t("choose"))
        host = self.values["host"].get().strip()
        if not valid_host(host):
            raise ValueError(self.t("bad_host"))
        names = ("count", "interval", "timeout", "duration")
        raw = [self.values[name].get() for name in names]
        if any(not value or not digits_only(value) for value in raw):
            raise ValueError(self.t("numbers"))
        count, interval, timeout, duration = map(int, raw)
        for valid, error in (
            (1 <= count <= 100, "count_range"),
            (1000 <= interval <= 60000, "interval_range"),
            (100 <= timeout <= 60000, "timeout_range"),
            (1 <= duration <= 300, "duration_range"),
        ):
            if not valid:
                raise ValueError(self.t(error))
        return host, count, interval, timeout, duration

    def start(self):
        try:
            host, count, interval, timeout, duration = self.read_inputs()
        except ValueError as error:
            messagebox.showerror(self.t("input_error"), str(error))
            return
        self.results.clear()
        self.redraw_results()
        self.last_host = host
        try:
            save_last_host(host)
            self.memory_error = False
        except OSError:
            self.memory_error = True
        self.stop_event.clear()
        self.running = True
        self.started = time.monotonic()
        self.elapsed = 0.0
        self.duration_limit = duration
        self.status = "running"
        self.show_info()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.preset_box.config(state="disabled")
        self.host_entry.config(state="disabled")
        for entry in self.number_entries:
            entry.config(state="disabled")
        threading.Thread(
            target=self.monitor, args=(host, count, interval, timeout, duration),
            daemon=True
        ).start()

    def ping_once(self, host, timeout_ms):
        """后台线程调用 Windows 自带的 ping 命令，只发一个包。"""
        if sys.platform != "win32":
            return False, None
        try:
            process = subprocess.Popen(
                ["ping", "-n", "1", "-w", str(timeout_ms), host],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except OSError:
            return False, None
        self.process = process
        if self.stop_event.is_set() and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            output, _ = process.communicate(timeout=timeout_ms / 1000 + 2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return False, None
        finally:
            self.process = None
        if process.returncode != 0:
            return False, None
        text = output.decode(locale.getpreferredencoding(False), errors="replace")
        return True, parse_latency(text)

    def monitor(self, host, count, interval, timeout, duration):
        """后台循环：次数和持续时间，哪个先到就结束。"""
        deadline = self.started + duration
        reason = "done_count"
        try:
            for index in range(count):
                if self.stop_event.is_set():
                    reason = "stopped"
                    break
                remaining_ms = int((deadline - time.monotonic()) * 1000)
                if remaining_ms < 100:
                    reason = "done_time"
                    break
                success, latency = self.ping_once(host, min(timeout, remaining_ms))
                if self.stop_event.is_set():
                    reason = "stopped"
                    break
                self.events.put((
                    "result",
                    (time.strftime("%Y-%m-%d %H:%M:%S"), host, success, latency)
                ))
                if time.monotonic() >= deadline:
                    reason = "done_time"
                    break
                if index < count - 1:
                    wait = min(interval / 1000, deadline - time.monotonic())
                    if self.stop_event.wait(wait):
                        reason = "stopped"
                        break
        finally:
            self.events.put(("done", reason))

    def stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.status = "stopping"
        self.show_info()
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def check_events(self):
        """Tkinter 只能在主线程更新；后台线程通过队列交给这里。"""
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "result":
                    self.results.append(data)
                    self.add_result(data)
                    self.table.yview_moveto(1)
                else:
                    self.elapsed = time.monotonic() - self.started
                    self.running = False
                    self.status = data
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.preset_box.config(state="readonly")
                    self.host_entry.config(
                        state="normal" if self.preset_index == len(PRESETS) - 1
                        else "readonly"
                    )
                    for entry in self.number_entries:
                        entry.config(state="normal")
        except queue.Empty:
            pass
        self.show_info()
        self.after(100, self.check_events)

    def export_csv(self):
        if not self.results:
            messagebox.showinfo(self.t("export"), self.t("no_data"))
            return
        path = filedialog.asksaveasfilename(
            title=self.t("export"), defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="ping-results.csv"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["time", "host", "success", "latency_ms"])
                writer.writerows(self.results)
        except OSError as error:
            messagebox.showerror(self.t("save_error"), str(error))
        else:
            messagebox.showinfo(self.t("export"), self.t("saved").format(path))

    def close(self):
        self.stop()
        self.destroy()


if __name__ == "__main__":
    PingApp().mainloop()
