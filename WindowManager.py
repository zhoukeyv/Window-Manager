# WindowManager.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import ctypes
from ctypes import wintypes
import json
import os
import sys

import win32gui
import win32con
import win32api
import win32process
import psutil


# ==========================================================
# 资源路径 & AppUserModelID
# ==========================================================
def resource_path(rel):
    """兼容 PyInstaller 打包后的资源路径"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


ICON_PATH = resource_path("icon.ico")
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hotkeys.json")

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "win.tool.window.manager"
    )
except Exception:
    pass


# ==========================================================
# 全局快捷键
# ==========================================================
MOD_ALT      = 0x0001
MOD_CONTROL  = 0x0002
MOD_SHIFT    = 0x0004
MOD_WIN      = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

MOD_NAMES = {
    "ctrl":  MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt":   MOD_ALT,
    "win":   MOD_WIN,
}

VK_MAP = {
    **{chr(c): c for c in range(ord('A'), ord('Z') + 1)},
    **{chr(c): c for c in range(ord('0'), ord('9') + 1)},
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
    "SPACE": 0x20, "ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09,
    "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, "`": 0xC0,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
    "INSERT": 0x2D, "DELETE": 0x2E,
}


def parse_hotkey(text: str):
    if not text:
        return None
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    key = None
    for p in parts:
        low = p.lower()
        if low in MOD_NAMES:
            mods |= MOD_NAMES[low]
        else:
            key = p.upper()
    if not key:
        return None
    vk = VK_MAP.get(key)
    if vk is None:
        return None
    return mods, vk


class HotkeyManager:
    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._tid = None
        self._handlers = {}
        self._pending = {}
        self._registered = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def set_binding(self, name, hotkey_str, callback):
        with self._lock:
            self._pending[name] = (hotkey_str, callback)

    def apply(self):
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._stop.set()
            if self._tid:
                ctypes.windll.user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)
            self._thread.join(timeout=1)
        self._thread = None
        self._tid = None
        self._handlers.clear()
        self._registered.clear()
        self._next_id = 1

    def _run(self):
        user32 = ctypes.windll.user32
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()

        with self._lock:
            for name, (hotkey_str, cb) in self._pending.items():
                parsed = parse_hotkey(hotkey_str)
                if not parsed:
                    continue
                mods, vk = parsed
                hid = self._next_id
                self._next_id += 1
                if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                    self._handlers[hid] = cb
                    self._registered[name] = (hid, hotkey_str)

        msg = wintypes.MSG()
        while not self._stop.is_set():
            r = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
            if r:
                if msg.message == WM_HOTKEY:
                    cb = self._handlers.get(msg.wParam)
                    if cb:
                        try:
                            cb()
                        except Exception:
                            pass
                elif msg.message == 0x0012:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.02)

        for hid in list(self._handlers.keys()):
            user32.UnregisterHotKey(None, hid)


# ==========================================================
# 数据 & 枚举
# ==========================================================
class WindowInfo:
    __slots__ = ("hwnd", "title", "exe", "last_seen")

    def __init__(self, hwnd, title, exe):
        self.hwnd = hwnd
        self.title = title
        self.exe = exe
        self.last_seen = time.time()


class WindowEnumerator:
    def __init__(self):
        self.windows = {}

    def scan(self):
        current = set()

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                exe = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                return
            current.add(hwnd)
            if hwnd in self.windows:
                self.windows[hwnd].title = title
                self.windows[hwnd].last_seen = time.time()
            else:
                self.windows[hwnd] = WindowInfo(hwnd, title, exe)

        win32gui.EnumWindows(callback, None)
        for hwnd in list(self.windows.keys()):
            if hwnd not in current:
                self.windows.pop(hwnd, None)


# ==========================================================
# 透明度
# ==========================================================
class OpacityController:
    def __init__(self):
        self.alpha_map = {}

    def read(self, hwnd):
        if not hwnd:
            return 255
        try:
            alpha = ctypes.c_ubyte()
            flags = ctypes.c_uint()
            if ctypes.windll.user32.GetLayeredWindowAttributes(
                    hwnd, None, ctypes.byref(alpha), ctypes.byref(flags)):
                return alpha.value
        except Exception:
            pass
        return self.alpha_map.get(hwnd, 255)

    def set(self, hwnd, alpha):
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        try:
            alpha = max(1, min(255, int(alpha)))
            self.alpha_map[hwnd] = alpha
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                   style | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha,
                                                win32con.LWA_ALPHA)
            return True
        except Exception:
            return False


# ==========================================================
# 点击
# ==========================================================
class ClickerController:
    def __init__(self, log_cb, status_cb, done_cb):
        self.log_cb = log_cb
        self.status_cb = status_cb
        self.done_cb = done_cb
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.thread = None
        self.count = 0

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def _click_once(self, hwnd, x, y, use_child):
        if not win32gui.IsWindow(hwnd):
            return False, None, (x, y), "窗口无效"
        target, cx, cy = hwnd, x, y
        if use_child:
            try:
                left, top, _, _ = win32gui.GetWindowRect(hwnd)
                sx, sy = left + x, top + y
                child = win32gui.WindowFromPoint((sx, sy))
                if child and win32gui.IsWindow(child):
                    cx, cy = win32gui.ScreenToClient(child, (sx, sy))
                    target = child
            except Exception:
                pass
        lparam = win32api.MAKELONG(cx, cy)
        try:
            win32gui.PostMessage(target, win32con.WM_MOUSEMOVE, 0, lparam)
            win32gui.PostMessage(target, win32con.WM_LBUTTONDOWN,
                                 win32con.MK_LBUTTON, lparam)
            win32gui.PostMessage(target, win32con.WM_LBUTTONUP, 0, lparam)
            return True, target, (cx, cy), None
        except Exception as e:
            return False, target, (cx, cy), str(e)

    def _loop(self, hwnd, x, y, interval, use_child):
        self.count = 0
        self.log_cb(f"▶ 启动点击 hwnd={hwnd} 坐标=({x},{y}) 间隔={interval}s "
                    f"子控件={'是' if use_child else '否'}")
        while not self.stop_event.is_set():
            if not win32gui.IsWindow(hwnd):
                self.log_cb("⚠ 目标窗口已失效")
                break
            ok, target, (cx, cy), err = self._click_once(hwnd, x, y, use_child)
            if ok:
                self.count += 1
                if target and target != hwnd:
                    self.log_cb(f"✔ #{self.count} 点击 父({x},{y}) → "
                                f"子hwnd={target} ({cx},{cy})")
                else:
                    self.log_cb(f"✔ #{self.count} 点击 hwnd={hwnd} ({cx},{cy})")
                self.status_cb(f"已点击 {self.count} 次")
            else:
                self.log_cb(f"✘ 点击失败: {err}")
            if self.stop_event.wait(interval):
                break
        self.log_cb(f"■ 结束 共点击 {self.count} 次")
        self.done_cb()

    def start(self, hwnd, x, y, interval, use_child):
        if self.running:
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop, args=(hwnd, x, y, interval, use_child),
            daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()

    def shutdown(self):
        self.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)


# ==========================================================
# 快捷键设置弹窗
# ==========================================================
ACTION_LABELS = {
    "record_pos":    "记录鼠标坐标 (立即)",
    "toggle_click":  "开始/停止点击",
    "alpha_down":    "透明度 -10",
    "alpha_up":      "透明度 +10",
    "alpha_reset":   "恢复不透明",
    "refresh":       "刷新窗口列表",
    "clear_log":     "清空日志",
}

DEFAULT_HOTKEYS = {
    "record_pos":   "Ctrl+Shift+R",
    "toggle_click": "Ctrl+Shift+S",
    "alpha_down":   "Ctrl+Shift+-",
    "alpha_up":     "Ctrl+Shift+=",
    "alpha_reset":  "Ctrl+Shift+0",
    "refresh":      "F5",
    "clear_log":    "Ctrl+L",
}


class HotkeyDialog(tk.Toplevel):
    def __init__(self, master, current: dict, on_save):
        super().__init__(master)
        self.title("快捷键设置")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        try:
            if os.path.exists(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.on_save = on_save
        self.entries = {}

        ttk.Label(self, text="点击输入框，然后按下组合键进行设置",
                  foreground="#666").grid(row=0, column=0, columnspan=2,
                                          padx=12, pady=(12, 8), sticky="w")

        for i, (name, label) in enumerate(ACTION_LABELS.items()):
            ttk.Label(self, text=label + ":").grid(
                row=i + 1, column=0, sticky="e", padx=(12, 6), pady=4)
            e = ttk.Entry(self, width=24, justify="center")
            e.insert(0, current.get(name, ""))
            e.grid(row=i + 1, column=1, padx=(0, 12), pady=4, sticky="w")
            e.bind("<KeyPress>", self._on_key)
            self.entries[name] = e

        btn_row = ttk.Frame(self)
        btn_row.grid(row=len(ACTION_LABELS) + 1, column=0, columnspan=2,
                     pady=(8, 12))
        ttk.Button(btn_row, text="保存", command=self._save)\
            .pack(side="left", padx=6)
        ttk.Button(btn_row, text="取消", command=self.destroy)\
            .pack(side="left", padx=6)
        ttk.Button(btn_row, text="清空当前项",
                   command=self._clear_focused).pack(side="left", padx=6)

    def _on_key(self, event):
        keysym = event.keysym
        if keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R",
                      "Alt_L", "Alt_R", "Super_L", "Super_R"):
            return "break"
        mods = []
        if event.state & 0x4:     mods.append("Ctrl")
        if event.state & 0x1:     mods.append("Shift")
        if event.state & 0x20000: mods.append("Alt")

        k = keysym
        special = {
            "minus": "-", "equal": "=", "plus": "=",
            "bracketleft": "[", "bracketright": "]",
            "comma": ",", "period": ".", "slash": "/",
            "backslash": "\\", "semicolon": ";",
            "apostrophe": "'", "grave": "`",
            "Return": "Enter", "Escape": "Esc",
            "Prior": "PgUp", "Next": "PgDn",
        }
        if k in special:
            k = special[k]
        elif len(k) == 1:
            k = k.upper()
        else:
            k = k.upper() if not (k.startswith("F") and k[1:].isdigit()) else k

        combo = "+".join(mods + [k])
        event.widget.delete(0, tk.END)
        event.widget.insert(0, combo)
        return "break"

    def _clear_focused(self):
        w = self.focus_get()
        if isinstance(w, ttk.Entry):
            w.delete(0, tk.END)

    def _save(self):
        result = {name: e.get().strip() for name, e in self.entries.items()}
        self.on_save(result)
        self.destroy()


# ==========================================================
# 主程序
# ==========================================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Window Manager")
        self.root.geometry("1040x680")
        self.root.minsize(960, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 图标
        try:
            if os.path.exists(ICON_PATH):
                self.root.iconbitmap(default=ICON_PATH)
        except Exception as e:
            print("图标加载失败:", e)

        self.enumerator = WindowEnumerator()
        self.opacity = OpacityController()
        self.clicker = ClickerController(
            log_cb=self.log_msg,
            status_cb=self.set_status,
            done_cb=lambda: self.root.after(0, self._on_click_done)
        )
        self.hotkey_mgr = HotkeyManager()
        self.hotkeys = self._load_hotkeys()

        self._record_countdown = False  # 防止倒计时重复

        self._setup_style()
        self._build_ui()
        self._bind_local_hotkeys()
        self._register_global_hotkeys()
        self.refresh()

    # ---------------- 配置 ----------------
    def _load_hotkeys(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                    return {**DEFAULT_HOTKEYS, **data}
            except Exception:
                pass
        return dict(DEFAULT_HOTKEYS)

    def _save_hotkeys(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.hotkeys, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_msg(f"✘ 保存快捷键失败: {e}")

    # ---------------- 样式 ----------------
    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 9))
        style.configure("TLabelframe", padding=8)
        style.configure("TLabelframe.Label",
                        font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("TButton", padding=4)
        style.configure("Accent.TButton",
                        foreground="#fff", background="#0078d4")
        style.map("Accent.TButton",
                  background=[("active", "#106ebe"),
                              ("disabled", "#a0a0a0")])
        style.configure("Danger.TButton",
                        foreground="#fff", background="#c42b1c")
        style.map("Danger.TButton",
                  background=[("active", "#a4262c"),
                              ("disabled", "#a0a0a0")])
        style.configure("Treeview", rowheight=22)
        style.configure("Treeview.Heading",
                        font=("Microsoft YaHei UI", 9, "bold"))

    # ---------------- UI ----------------
    def _build_ui(self):
        # 顶部工具栏
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="🔍").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._fill_tree())
        ttk.Entry(toolbar, textvariable=self.search_var, width=32)\
            .pack(side="left", padx=(4, 12))

        ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side="left")

        ttk.Separator(toolbar, orient="vertical")\
            .pack(side="left", fill="y", padx=10)

        self.auto_refresh = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="自动刷新 (5s)",
                        variable=self.auto_refresh,
                        command=self._toggle_auto_refresh).pack(side="left")

        ttk.Button(toolbar, text="⌨ 快捷键设置",
                   command=self.open_hotkey_dialog).pack(side="right")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        # 主体
        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # 左：列表
        left = ttk.LabelFrame(body, text=" 窗口列表 ")
        body.add(left, weight=3)

        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            tree_wrap, columns=("title", "exe", "hwnd", "alpha"),
            show="headings")
        for col, name, w, anchor in [
            ("title", "窗口标题", 340, "w"),
            ("exe", "进程", 140, "w"),
            ("hwnd", "HWND", 80, "center"),
            ("alpha", "透明度", 70, "center"),
        ]:
            self.tree.heading(col, text=name)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        sb = ttk.Scrollbar(tree_wrap, orient="vertical",
                           command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.config(yscrollcommand=sb.set)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        # 右：控制
        right = ttk.Frame(body)
        body.add(right, weight=2)

        # 选中信息
        info_box = ttk.LabelFrame(right, text=" 当前选中 ")
        info_box.pack(fill="x", pady=(0, 8))
        self.sel_label = ttk.Label(info_box, text="（未选择窗口）",
                                   justify="left", wraplength=360,
                                   foreground="#888")
        self.sel_label.pack(fill="x", anchor="w")

        # 透明度
        opa_box = ttk.LabelFrame(right, text=" 透明度控制 ")
        opa_box.pack(fill="x", pady=(0, 8))

        self.slider = ttk.Scale(opa_box, from_=1, to=255, orient="horizontal",
                                command=self.on_slider)
        self.slider.set(255)
        self.slider.pack(fill="x", pady=(0, 6))

        r1 = ttk.Frame(opa_box)
        r1.pack(fill="x")
        ttk.Label(r1, text="数值:").pack(side="left")
        self.alpha_entry = ttk.Entry(r1, width=6, justify="center")
        self.alpha_entry.insert(0, "255")
        self.alpha_entry.pack(side="left", padx=(4, 6))
        ttk.Button(r1, text="应用", width=6,
                   command=self.apply_alpha_entry).pack(side="left", padx=2)
        ttk.Button(r1, text="恢复不透明",
                   command=self.restore_alpha).pack(side="left", padx=2)

        r2 = ttk.Frame(opa_box)
        r2.pack(fill="x", pady=(6, 0))
        ttk.Label(r2, text="预设:").pack(side="left")
        for v in (255, 220, 180, 140, 100, 60):
            ttk.Button(r2, text=str(v), width=4,
                       command=lambda val=v: self._apply_alpha(val))\
                .pack(side="left", padx=1)

        # 后台点击
        clk_box = ttk.LabelFrame(right, text=" 后台点击 ")
        clk_box.pack(fill="x", pady=(0, 8))

        grid = ttk.Frame(clk_box)
        grid.pack(fill="x")
        ttk.Label(grid, text="X 坐标:").grid(row=0, column=0,
                                            sticky="e", padx=(0, 4), pady=2)
        self.x_entry = ttk.Entry(grid, width=8)
        self.x_entry.insert(0, "100")
        self.x_entry.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(grid, text="Y 坐标:").grid(row=0, column=2,
                                            sticky="e", padx=(12, 4), pady=2)
        self.y_entry = ttk.Entry(grid, width=8)
        self.y_entry.insert(0, "100")
        self.y_entry.grid(row=0, column=3, sticky="w", pady=2)

        ttk.Label(grid, text="间隔(秒):").grid(row=1, column=0,
                                              sticky="e", padx=(0, 4), pady=2)
        self.interval_entry = ttk.Entry(grid, width=8)
        self.interval_entry.insert(0, "1.0")
        self.interval_entry.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(grid, text="倒计时(秒):").grid(row=1, column=2,
                                                sticky="e", padx=(12, 4), pady=2)
        self.delay_entry = ttk.Entry(grid, width=8)
        self.delay_entry.insert(0, "3")
        self.delay_entry.grid(row=1, column=3, sticky="w", pady=2)

        self.use_child = tk.BooleanVar(value=True)
        ttk.Checkbutton(grid, text="自动定位子控件",
                        variable=self.use_child)\
            .grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        r3 = ttk.Frame(clk_box)
        r3.pack(fill="x", pady=(8, 0))
        self.btn_record = ttk.Button(r3, text="记录鼠标坐标",
                                     command=self.record_position_delayed)
        self.btn_record.pack(side="left")
        self.btn_start = ttk.Button(r3, text="▶ 开始", style="Accent.TButton",
                                    width=10, command=self.start_click)
        self.btn_start.pack(side="right", padx=(4, 0))
        self.btn_stop = ttk.Button(r3, text="■ 停止", style="Danger.TButton",
                                   width=10, command=self.stop_click,
                                   state="disabled")
        self.btn_stop.pack(side="right")

        ttk.Label(clk_box,
                  text="提示：按钮使用倒计时；快捷键立即记录",
                  foreground="#888",
                  font=("Microsoft YaHei UI", 8))\
            .pack(anchor="w", pady=(6, 0))

        # 快捷键提示
        self.hint_label = ttk.Label(right, text="",
                                    foreground="#888",
                                    justify="left", wraplength=360,
                                    font=("Microsoft YaHei UI", 8))
        self.hint_label.pack(fill="x", pady=(4, 0))

        # 日志
        log_box = ttk.LabelFrame(self.root, text=" 日志 ")
        log_box.pack(fill="both", expand=False, padx=8, pady=(0, 4))

        log_wrap = ttk.Frame(log_box)
        log_wrap.pack(fill="both", expand=True)

        self.log = tk.Text(log_wrap, height=9, state="disabled",
                           bg="#1e1e1e", fg="#dcdcdc",
                           insertbackground="#dcdcdc",
                           font=("Consolas", 9), bd=0, wrap="none")
        self.log.grid(row=0, column=0, sticky="nsew")
        log_sb = ttk.Scrollbar(log_wrap, orient="vertical",
                               command=self.log.yview)
        log_sb.grid(row=0, column=1, sticky="ns")
        self.log.config(yscrollcommand=log_sb.set)
        log_wrap.rowconfigure(0, weight=1)
        log_wrap.columnconfigure(0, weight=1)

        self.log.tag_config("ok",   foreground="#73c991")
        self.log.tag_config("err",  foreground="#f48771")
        self.log.tag_config("warn", foreground="#dcdcaa")
        self.log.tag_config("info", foreground="#9cdcfe")
        self.log.tag_config("time", foreground="#808080")

        btn_row = ttk.Frame(log_box)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="清空日志", command=self.clear_log)\
            .pack(side="right")

        # 状态栏
        status_bar = ttk.Frame(self.root, relief="sunken")
        status_bar.pack(fill="x", side="bottom")
        self.status = ttk.Label(status_bar, text="就绪",
                                anchor="w", padding=(8, 2))
        self.status.pack(side="left", fill="x", expand=True)
        self.status_count = ttk.Label(status_bar, text="窗口: 0",
                                      anchor="e", padding=(8, 2))
        self.status_count.pack(side="right")
        self.status_running = ttk.Label(status_bar, text="● 空闲",
                                        foreground="gray",
                                        anchor="e", padding=(8, 2))
        self.status_running.pack(side="right")

        self._refresh_hotkey_hint()

    # ---------------- 快捷键 ----------------
    def _action_map(self):
        return {
            "record_pos":   self.record_position_now,
            "toggle_click": self.toggle_click,
            "alpha_down":   lambda: self._step_alpha(-10),
            "alpha_up":     lambda: self._step_alpha(+10),
            "alpha_reset":  self.restore_alpha,
            "refresh":      self.refresh,
            "clear_log":    self.clear_log,
        }

    def _bind_local_hotkeys(self):
        for seq in list(getattr(self, "_local_bindings", [])):
            try:
                self.root.unbind_all(seq)
            except Exception:
                pass
        self._local_bindings = []

        actions = self._action_map()
        for name, hk in self.hotkeys.items():
            seq = self._to_tk_sequence(hk)
            if not seq or name not in actions:
                continue
            cb = actions[name]
            self.root.bind_all(seq, lambda e, c=cb: (c(), "break")[1])
            self._local_bindings.append(seq)

    def _to_tk_sequence(self, hotkey_str):
        if not hotkey_str:
            return None
        parts = [p.strip() for p in hotkey_str.split("+") if p.strip()]
        if not parts:
            return None
        mod_map = {"ctrl": "Control", "shift": "Shift",
                   "alt": "Alt", "win": "Super"}
        mods, key = [], None
        for p in parts:
            low = p.lower()
            if low in mod_map:
                mods.append(mod_map[low])
            else:
                key = p
        if not key:
            return None
        special = {
            "-": "minus", "=": "equal", "[": "bracketleft",
            "]": "bracketright", ",": "comma", ".": "period",
            "/": "slash", "\\": "backslash", ";": "semicolon",
            "'": "apostrophe", "`": "grave",
            "Enter": "Return", "Esc": "Escape",
            "PgUp": "Prior", "PgDn": "Next",
            "SPACE": "space",
        }
        if key in special:
            tkkey = special[key]
        elif len(key) == 1:
            tkkey = key.lower() if "Shift" not in mods else key.upper()
        else:
            tkkey = key
        return "<" + "-".join(mods + [tkkey]) + ">"

    def _register_global_hotkeys(self):
        actions = self._action_map()
        self.hotkey_mgr.stop()
        for name, hk in self.hotkeys.items():
            if name not in actions:
                continue
            cb = actions[name]
            self.hotkey_mgr.set_binding(
                name, hk,
                lambda c=cb: self.root.after(0, c)
            )
        self.hotkey_mgr.apply()

    def _refresh_hotkey_hint(self):
        lines = ["快捷键："]
        for name, label in ACTION_LABELS.items():
            hk = self.hotkeys.get(name, "")
            if hk:
                lines.append(f"  · {label}: {hk}")
        self.hint_label.config(text="\n".join(lines))

    def open_hotkey_dialog(self):
        HotkeyDialog(self.root, self.hotkeys, self._on_hotkey_saved)

    def _on_hotkey_saved(self, new_map):
        self.hotkeys = {**self.hotkeys, **new_map}
        self._save_hotkeys()
        self._bind_local_hotkeys()
        self._register_global_hotkeys()
        self._refresh_hotkey_hint()
        self.log_msg("✔ 快捷键已更新")

    # ---------------- 通用 ----------------
    def set_status(self, msg):
        self.root.after(0, lambda: self.status.config(text=msg))

    def log_msg(self, msg):
        def _do():
            tag = "info"
            if msg.startswith("✔"):
                tag = "ok"
            elif msg.startswith("✘"):
                tag = "err"
            elif msg.startswith("⚠"):
                tag = "warn"
            self.log.config(state="normal")
            self.log.insert("end", time.strftime("[%H:%M:%S] "), "time")
            self.log.insert("end", msg + "\n", tag)
            self.log.see("end")
            self.log.config(state="disabled")
        self.root.after(0, _do)

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.set_status("日志已清空")

    # ---------------- 列表 ----------------
    def refresh(self):
        self.enumerator.scan()
        self._fill_tree()
        n = len(self.enumerator.windows)
        self.status_count.config(text=f"窗口: {n}")
        self.set_status(f"已刷新 ({n} 个窗口)")

    def _fill_tree(self):
        keyword = self.search_var.get().lower().strip()
        selected = self.get_selected_hwnd()
        self.tree.delete(*self.tree.get_children())
        for hwnd, info in self.enumerator.windows.items():
            text = f"{info.title} {info.exe}".lower()
            if keyword and keyword not in text:
                continue
            alpha = self.opacity.read(hwnd)
            self.tree.insert("", "end", iid=str(hwnd),
                             values=(info.title, info.exe, hwnd, alpha))
        if selected and str(selected) in self.tree.get_children():
            self.tree.selection_set(str(selected))

    def _toggle_auto_refresh(self):
        if self.auto_refresh.get():
            self._auto_refresh_tick()

    def _auto_refresh_tick(self):
        if not self.auto_refresh.get():
            return
        self.refresh()
        self.root.after(5000, self._auto_refresh_tick)

    def get_selected_hwnd(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def on_select(self, _e=None):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.sel_label.config(text="（未选择窗口）", foreground="#888")
            return
        info = self.enumerator.windows.get(hwnd)
        if not info:
            return
        alpha = self.opacity.read(hwnd)
        self.slider.set(alpha)
        self.alpha_entry.delete(0, tk.END)
        self.alpha_entry.insert(0, str(alpha))
        self.sel_label.config(
            text=f"标题: {info.title}\n进程: {info.exe}    HWND: {hwnd}",
            foreground="black")
        self.set_status(f"已选中 HWND={hwnd}, alpha={alpha}")

    # ---------------- 透明度 ----------------
    def _apply_alpha(self, v):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.set_status("请先选择窗口")
            return
        v = max(1, min(255, int(v)))
        self.slider.set(v)
        self.alpha_entry.delete(0, tk.END)
        self.alpha_entry.insert(0, str(v))
        if self.opacity.set(hwnd, v):
            self._update_tree_alpha(hwnd, v)
            self.set_status(f"已设置 alpha={v}")

    def _step_alpha(self, delta):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.set_status("请先选择窗口")
            return
        cur = self.opacity.read(hwnd)
        self._apply_alpha(cur + delta)

    def on_slider(self, value):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return
        v = int(float(value))
        self.alpha_entry.delete(0, tk.END)
        self.alpha_entry.insert(0, str(v))
        self.opacity.set(hwnd, v)
        self._update_tree_alpha(hwnd, v)

    def apply_alpha_entry(self):
        try:
            v = int(self.alpha_entry.get())
        except ValueError:
            self.set_status("请输入 1~255 整数")
            return
        self._apply_alpha(v)

    def restore_alpha(self):
        self._apply_alpha(255)

    def _update_tree_alpha(self, hwnd, v):
        iid = str(hwnd)
        if iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            if len(vals) >= 4:
                vals[3] = v
                self.tree.item(iid, values=vals)

    # ---------------- 点击器 ----------------
    def record_position_now(self):
        """ 快捷键调用：立即记录鼠标位置 """
        self._do_record_position(source="快捷键")

    def record_position_delayed(self):
        """ 按钮调用：倒计时后记录 """
        if self._record_countdown:
            return
        try:
            delay = int(self.delay_entry.get())
            if delay < 0:
                delay = 0
        except ValueError:
            delay = 3

        if delay == 0:
            self._do_record_position(source="按钮")
            return

        self._record_countdown = True
        self.btn_record.config(state="disabled")

        def tick(remain):
            if remain <= 0:
                self.btn_record.config(state="normal", text="记录鼠标坐标")
                self._record_countdown = False
                self._do_record_position(source="按钮")
                return
            self.btn_record.config(text=f"记录中… {remain}s")
            self.set_status(f"{remain} 秒后记录鼠标位置…")
            self.root.after(1000, lambda: tick(remain - 1))

        tick(delay)

    def _do_record_position(self, source="快捷键"):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.log_msg("⚠ 记录坐标失败：未选择窗口")
            self.set_status("请先在列表中选择窗口")
            return
        try:
            mx, my = win32api.GetCursorPos()
            left, top, _, _ = win32gui.GetWindowRect(hwnd)
            x, y = mx - left, my - top
        except Exception as e:
            self.log_msg(f"✘ 记录失败: {e}")
            return
        self.x_entry.delete(0, tk.END); self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END); self.y_entry.insert(0, str(y))
        self.set_status(f"已记录坐标 ({x}, {y})")
        self.log_msg(f"✔ [{source}] 记录坐标 ({x},{y}) hwnd={hwnd}")

    def toggle_click(self):
        if self.clicker.running:
            self.stop_click()
        else:
            self.start_click()

    def start_click(self):
        if self.clicker.running:
            return
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.log_msg("⚠ 开始失败：未选择窗口")
            self.set_status("请先选择窗口")
            return
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            interval = float(self.interval_entry.get())
            if interval <= 0:
                raise ValueError("间隔必须 > 0")
        except ValueError as e:
            messagebox.showerror("参数错误", str(e))
            return
        if self.clicker.start(hwnd, x, y, interval, self.use_child.get()):
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.status_running.config(text="● 运行中", foreground="#2a7")
            self.set_status("点击器运行中…")

    def stop_click(self):
        if self.clicker.running:
            self.clicker.stop()
            self.set_status("正在停止…")

    def _on_click_done(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_running.config(text="● 空闲", foreground="gray")

    # ---------------- 关闭 ----------------
    def on_close(self):
        try:
            self.clicker.shutdown()
            self.hotkey_mgr.stop()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()