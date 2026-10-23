"""Cover one Windows display or all displays with solid black windows."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys
import tkinter as tk
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class Monitor:
    device: str
    left: int
    top: int
    right: int
    bottom: int
    primary: bool

    @property
    def label(self) -> str:
        name = self.device.removeprefix("\\\\.\\")
        primary = " (primary)" if self.primary else ""
        return f"{name}{primary} — {self.right - self.left} × {self.bottom - self.top}"


def enable_dpi_awareness() -> None:
    """Keep window coordinates in physical pixels on mixed-DPI desktops."""
    try:
        set_context = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = wintypes.BOOL
        if set_context(ctypes.c_void_p(-4)):
            return
    except AttributeError:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()


def get_monitors() -> list[Monitor]:
    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("monitor", wintypes.RECT),
            ("work", wintypes.RECT),
            ("flags", wintypes.DWORD),
            ("device", wintypes.WCHAR * 32),
        ]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
    )
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [
        wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback_type, wintypes.LPARAM,
    ]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    monitors: list[Monitor] = []
    errors: list[int] = []

    @callback_type
    def collect(handle, _dc, _rect, _data):
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            errors.append(ctypes.get_last_error())
            return False
        rect = info.monitor
        monitors.append(Monitor(
            info.device, rect.left, rect.top, rect.right, rect.bottom,
            bool(info.flags & 1),
        ))
        return True

    succeeded = user32.EnumDisplayMonitors(None, None, collect, 0)
    if errors or not succeeded:
        raise ctypes.WinError(errors[0] if errors else ctypes.get_last_error())
    if not monitors:
        raise RuntimeError("Windows did not report any connected displays.")
    return sorted(monitors, key=lambda monitor: (not monitor.primary, monitor.left, monitor.top))


class BlackScreenApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.monitors: list[Monitor] = []
        self.overlays: list[tk.Toplevel] = []
        root.title("Black Screen")
        root.geometry("540x310")
        root.minsize(480, 300)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        style = ttk.Style(root)
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("TButton", padding=(12, 8))

        panel = ttk.Frame(root, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Black Screen", style="Title.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Cover a display with solid black. Your screens stay on.").pack(
            anchor="w", pady=(4, 20),
        )
        ttk.Label(panel, text="Choose a screen").pack(anchor="w", pady=(0, 6))
        self.selection = ttk.Combobox(panel, state="readonly")
        self.selection.pack(fill="x")
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(16, 18))
        self.start_button = ttk.Button(buttons, text="Make black", command=self.show_black)
        self.start_button.pack(side="left")
        ttk.Button(buttons, text="Refresh screens", command=self.refresh).pack(side="left", padx=8)
        ttk.Label(panel, text="Press Esc to restore all screens. Mouse clicks are ignored.").pack(anchor="w")
        self.refresh()

    def refresh(self) -> bool:
        previous = None
        index = self.selection.current()
        if 0 < index <= len(self.monitors):
            previous = self.monitors[index - 1].device
        try:
            self.monitors = get_monitors()
        except (OSError, RuntimeError) as error:
            self.start_button.state(["disabled"])
            messagebox.showerror("Cannot detect screens", str(error), parent=self.root)
            return False
        self.selection["values"] = ["All screens", *(monitor.label for monitor in self.monitors)]
        selected = next(
            (i + 1 for i, monitor in enumerate(self.monitors) if monitor.device == previous), 0,
        )
        self.selection.current(selected)
        self.start_button.state(["!disabled"])
        return True

    def show_black(self) -> None:
        if self.overlays or not self.refresh():
            return
        index = self.selection.current()
        targets = self.monitors if index == 0 else [self.monitors[index - 1]]
        self.root.withdraw()
        try:
            for index, monitor in enumerate(targets):
                overlay = tk.Toplevel(self.root)
                overlay.title("Black Screen — Press Esc to restore")
                self.overlays.append(overlay)
                overlay.withdraw()
                # Keep the main overlay managed normally so Windows can activate
                # it from Alt+Tab. Remove its frame through Win32 below instead.
                overlay.overrideredirect(index != 0)
                overlay.configure(background="black", cursor="none")
                overlay.attributes("-topmost", True)
                overlay.bind("<Escape>", self.restore)
                overlay.bind("<Alt-F4>", lambda _event: "break")
                overlay.protocol("WM_DELETE_WINDOW", lambda: None)
                # Tk interprets negative geometry offsets relative to the desktop's
                # right/bottom edge. Use Win32 for absolute negative coordinates.
                overlay.geometry(f"{monitor.right - monitor.left}x{monitor.bottom - monitor.top}+0+0")
                overlay.deiconify()
                overlay.update_idletasks()
                self.position_overlay(overlay, monitor, show_in_taskbar=index == 0)
            self.overlays[0].focus_force()
        except Exception as error:
            self.restore()
            messagebox.showerror("Cannot cover screens", str(error), parent=self.root)

    @staticmethod
    def position_overlay(
        overlay: tk.Toplevel, monitor: Monitor, show_in_taskbar: bool = False,
    ) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        child = overlay.winfo_id()
        handle = user32.GetParent(child) or child
        if show_in_taskbar:
            user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = wintypes.LONG
            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            user32.SetWindowLongW.restype = wintypes.LONG
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            # Publish one normally managed, borderless app window to the shell.
            style = user32.GetWindowLongW(handle, -20)  # GWL_EXSTYLE
            user32.ShowWindow(handle, 0)  # Shell requires hide/show after this change.
            ctypes.set_last_error(0)
            previous = user32.SetWindowLongW(
                handle, -20, (style | 0x40000) & ~(0x80 | 0x08000000),
            )
            if not previous and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
            window_style = user32.GetWindowLongW(handle, -16)  # GWL_STYLE
            ctypes.set_last_error(0)
            previous = user32.SetWindowLongW(handle, -16, window_style & ~0x00CF0000)
            if not previous and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
        if not user32.SetWindowPos(
            handle, wintypes.HWND(-1), monitor.left, monitor.top,
            monitor.right - monitor.left, monitor.bottom - monitor.top, 0x0040 | 0x0020,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def restore(self, _event=None) -> str:
        for overlay in self.overlays:
            overlay.destroy()
        self.overlays.clear()
        self.root.deiconify()
        self.root.lift()
        return "break"

    def quit(self) -> None:
        self.root.destroy()


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This application currently supports Windows only.")
    enable_dpi_awareness()
    root = tk.Tk()
    BlackScreenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
