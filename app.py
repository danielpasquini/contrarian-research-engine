"""
Root Standalone Entrypoint (`app.py`) for Contrarian Engine (`Contrarian Engine.exe`).
Bundles backend validation, local FastAPI server startup, and a native Windows 11
App Window (with DWM dark Mica titlebar, rounded corners, and custom favicon) into
a single portable Windows executable via PyInstaller:
`pyinstaller --noconsole --onefile --name="Contrarian Engine" --icon="favicon.ico" app.py`
"""

import contextlib
import ctypes
import io
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from src.config import PAPER_ALPACA_URL, EngineSettings

APP_NAME = "Contrarian Engine"
APP_USER_MODEL_ID = "Contrarian.Engine.Win11"


class _SafeStream:
    """Safe fallback stream when running under PyInstaller --noconsole on Windows."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def _ensure_stdio_streams() -> None:
    """Windows GUI / --noconsole compatibility: ensure standard streams are not None."""
    if sys.stdout is None:
        sys.stdout = _SafeStream()  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _SafeStream()  # type: ignore[assignment]
    if sys.stdin is None:
        sys.stdin = io.StringIO()


_ensure_stdio_streams()


def resolve_bundle_path(relative_path: str) -> Path:
    """Resolves resource paths in both PyInstaller `_MEIPASS` and local source mode."""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / relative_path


def build_runtime_metadata() -> dict[str, object]:
    """
    Validates immutable safety settings on startup before exposing Contrarian Engine.
    Raises RuntimeError if live mode or non-paper Alpaca URLs are configured.
    """
    settings = EngineSettings()
    if settings.execution_mode not in ("research", "paper"):
        raise RuntimeError(f"Unsupported execution mode: {settings.execution_mode}")
    if settings.alpaca_paper_api_url != PAPER_ALPACA_URL:
        raise RuntimeError("Non-paper brokerage endpoint detected.")

    return {
        "app_name": APP_NAME,
        "execution_mode": settings.execution_mode,
        "allow_averaging_down": settings.allow_averaging_down,
        "require_bracket_order": settings.require_bracket_order,
        "paper_endpoint_verified": settings.alpaca_paper_api_url == PAPER_ALPACA_URL,
        "dashboard_path": str(resolve_bundle_path("dashboard/app.py")),
    }


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex((host, port)) == 0


def _free_stale_port_on_windows(port: int) -> None:
    """Terminates any previous stale server instance holding the port so the new exe starts."""
    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],  # noqa: S607
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        current_pid = os.getpid()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and f":{port}" in parts[1] and parts[3].upper() == "LISTENING":
                pid = int(parts[4])
                if pid > 0 and pid != current_pid:
                    subprocess.run(  # noqa: S603
                        ["taskkill", "/F", "/PID", str(pid)],  # noqa: S607
                        check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
        time.sleep(0.3)


def _wait_for_server_ready(url: str, timeout: float = 15.0) -> bool:
    """Polls `/health` until the local FastAPI server responds HTTP 200 OK."""
    deadline = time.monotonic() + timeout
    health_url = f"{url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.12)
    return False


def _apply_win11_dwm_styling(window_title: str, icon_path: Path) -> None:
    """
    Applies native Windows 11 DWM attributes (Dark Mode, Rounded Corners,
    Mica Caption Color `#060a12`, and custom `.ico` icon) to the application window.
    """
    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        hwnd = 0
        for _ in range(30):
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                break
            time.sleep(0.15)
        if not hwnd:
            return

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_mode = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
        )
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33 (2 = DWMWCP_ROUND)
        corner_pref = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(corner_pref), ctypes.sizeof(corner_pref)
        )
        # DWMWA_SYSTEMBACKDROP_TYPE = 38 (2 = Mica)
        mica_backdrop = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 38, ctypes.byref(mica_backdrop), ctypes.sizeof(mica_backdrop)
        )
        # DWMWA_CAPTION_COLOR = 35 (COLORREF 0x00BBGGRR for #060a12 -> 0x00120A06)
        caption_color = ctypes.c_int(0x00120A06)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
        )
        # DWMWA_TEXT_COLOR = 36 (COLORREF for #f1f5f9 -> 0x00F9F5F1)
        text_color = ctypes.c_int(0x00F9F5F1)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color)
        )

        if icon_path.exists():
            # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x0010
            hicon_small = user32.LoadImageW(None, str(icon_path), 1, 16, 16, 0x0010)
            hicon_big = user32.LoadImageW(None, str(icon_path), 1, 32, 32, 0x0010)
            # WM_SETICON = 0x0080 (0 = ICON_SMALL, 1 = ICON_BIG)
            if hicon_small:
                user32.SendMessageW(hwnd, 0x0080, 0, hicon_small)
            if hicon_big:
                user32.SendMessageW(hwnd, 0x0080, 1, hicon_big)


def _find_win11_app_host() -> Path | None:
    """Finds Microsoft Edge on Windows 11 to host a native chromeless app window."""
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _launch_win11_native_window(url: str) -> subprocess.Popen[bytes] | None:
    """Opens a dedicated Windows 11 native app window (chromeless, custom DWM dark header)."""
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)

    edge_exe = _find_win11_app_host()
    if edge_exe is None:
        webbrowser.open(url)
        return None

    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    profile_dir = local_app_data / "ContrarianEngine" / "Win11DesktopProfile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    args = [
        str(edge_exe),
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,msEdgeSidebarV2",
    ]
    proc = subprocess.Popen(args)  # noqa: S603
    icon_file = resolve_bundle_path("favicon.ico")
    if not icon_file.exists():
        icon_file = Path("favicon.ico").resolve()
    threading.Thread(
        target=_apply_win11_dwm_styling,
        args=(APP_NAME, icon_file),
        daemon=True,
    ).start()
    return proc


def _open_window_when_ready(url: str) -> None:
    """Waits until FastAPI `/health` returns 200 OK, then opens the Windows 11 window."""
    if _wait_for_server_ready(url, timeout=20.0):
        _launch_win11_native_window(url)


def launch_command_center(
    host: str = "127.0.0.1",
    port: int = 8501,
    open_browser: bool = True,
) -> int:
    """Starts the local FastAPI engine server and opens the Windows 11 native window."""
    try:
        import uvicorn

        from src.api.app import app as fastapi_app

        build_runtime_metadata()

        if _is_port_in_use(host, port):
            _free_stale_port_on_windows(port)
        if _is_port_in_use(host, port):
            for alt_port in range(port + 1, port + 15):
                if not _is_port_in_use(host, alt_port):
                    port = alt_port
                    break

        url = f"http://{host}:{port}"
        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            log_level="info",
            log_config=None,
        )
        server = uvicorn.Server(config)

        if open_browser:
            threading.Thread(
                target=_open_window_when_ready,
                args=(url,),
                daemon=True,
            ).start()

        server.run()
        return 0
    except Exception as exc:
        crash_log = Path("contrarian_startup_crash.log")
        crash_log.write_text(f"Crash: {exc}\n{traceback.format_exc()}", encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(launch_command_center())
