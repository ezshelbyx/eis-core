"""Capture a PNG screenshot of the running E.I.S. Core dashboard.

Zero-dependency approach:
- tkinter opens the real app window
- Win32 PrintWindow renders it into a DIB (ctypes)
- the DIB is repacked as PPM and written to PNG via Tk 8.6's PhotoImage

Usage:  python tools/screenshot.py [output.png]
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GDI32 = ctypes.windll.gdi32
USER32 = ctypes.windll.user32

BI_RGB = 0
DIB_RGB_COLORS = 0
PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
GA_ROOT = 2


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def capture_hwnd(hwnd: int) -> tuple[int, int, bytes]:
    """Return (width, height, top-down BGRX bytes) for the window."""
    rect = wt.RECT()
    if not USER32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("GetWindowRect failed")
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError("window has no size")

    hdc_window = USER32.GetWindowDC(hwnd)
    hdc_mem = GDI32.CreateCompatibleDC(hdc_window)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    bits = ctypes.c_void_p()
    hbm = GDI32.CreateDIBSection(hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS,
                                 ctypes.byref(bits), None, 0)
    if not hbm or not bits:
        raise RuntimeError("CreateDIBSection failed")
    GDI32.SelectObject(hdc_mem, hbm)
    GDI32.BitBlt(hdc_mem, 0, 0, w, h, hdc_window, 0, 0, SRCCOPY)
    ok = USER32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    if not ok:
        raise RuntimeError("PrintWindow failed")

    raw = ctypes.string_at(bits, w * h * 4)
    GDI32.DeleteObject(hbm)
    GDI32.DeleteDC(hdc_mem)
    USER32.ReleaseDC(hwnd, hdc_window)
    return w, h, raw


def save_png_via_tk(root, width: int, height: int, raw: bytes, dest: Path) -> None:
    """Wrap raw BGRX pixel data in a PPM and let Tk write a PNG."""
    ppm = bytearray()
    ppm += b"P6\n%d %d\n255\n" % (width, height)
    for i in range(0, len(raw), 4):
        b, g, r = raw[i], raw[i + 1], raw[i + 2]
        ppm += bytes((r, g, b))
    from tkinter import PhotoImage

    img = PhotoImage(data=bytes(ppm), format="ppm", master=root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.write(str(dest), format="png")


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "screenshots" / "dashboard.png"

    from eis.ui.app import EISApp

    app = EISApp()
    captures: list[tuple[int, int, bytes]] = []

    def grab() -> None:
        try:
            hwnd = USER32.GetAncestor(app.winfo_id(), GA_ROOT) or app.winfo_id()
            captures.append(capture_hwnd(hwnd))
        except Exception as exc:
            print(f"capture failed: {exc}", file=sys.stderr)
        finally:
            app.destroy()

    app.after(3500, grab)  # let the dashboard finish first paint
    app.mainloop()

    if not captures:
        print("no capture produced", file=sys.stderr)
        return 1
    w, h, raw = captures[0]
    # PhotoImage needs a live Tk interpreter; the app is gone, so use a hidden one.
    from tkinter import Tk

    tmp = Tk()
    tmp.withdraw()
    save_png_via_tk(tmp, w, h, raw, dest)
    tmp.destroy()
    print(f"saved {dest} ({w}x{h}, {dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
