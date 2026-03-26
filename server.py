import socket
import threading
import time
import pyperclip
import json
import logging
import os
import ctypes
import ctypes.wintypes

# --- Logging ra file (chạy ngầm không có terminal) ---
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


# ================================================================
#  Wake-up Detector
# ================================================================
class SleepWakeDetector:
    WM_POWERBROADCAST      = 0x0218
    PBT_APMSUSPEND         = 0x0004
    PBT_APMRESUMEAUTOMATIC = 0x0012
    PBT_APMRESUMESUSPEND   = 0x0007

    def __init__(self, on_sleep=None, on_wake=None):
        self.on_sleep = on_sleep
        self.on_wake  = on_wake
        self._thread  = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        try:
            user32   = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            WNDPROCTYPE = ctypes.WINFUNCTYPE(
                ctypes.c_int64, ctypes.c_int64, ctypes.c_uint,
                ctypes.c_int64, ctypes.c_int64,
            )
            user32.DefWindowProcW.restype  = ctypes.c_int64
            user32.DefWindowProcW.argtypes = [
                ctypes.c_int64, ctypes.c_uint, ctypes.c_int64, ctypes.c_int64
            ]

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == self.WM_POWERBROADCAST:
                    if wparam == self.PBT_APMSUSPEND:
                        log.info("💤 Máy đang sleep...")
                        if self.on_sleep:
                            threading.Thread(target=self.on_sleep, daemon=True).start()
                    elif wparam in (self.PBT_APMRESUMEAUTOMATIC, self.PBT_APMRESUMESUSPEND):
                        log.info("☀️  Máy vừa wake up!")
                        if self.on_wake:
                            threading.Thread(target=self.on_wake, daemon=True).start()
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            wnd_proc_ptr = WNDPROCTYPE(wnd_proc)
            hinstance = kernel32.GetModuleHandleW(None)

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style",         ctypes.c_uint),
                    ("lpfnWndProc",   WNDPROCTYPE),
                    ("cbClsExtra",    ctypes.c_int),
                    ("cbWndExtra",    ctypes.c_int),
                    ("hInstance",     ctypes.c_void_p),
                    ("hIcon",         ctypes.c_void_p),
                    ("hCursor",       ctypes.c_void_p),
                    ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName",  ctypes.c_wchar_p),
                    ("lpszClassName", ctypes.c_wchar_p),
                ]

            wc2 = WNDCLASSW()
            wc2.lpfnWndProc   = wnd_proc_ptr
            wc2.hInstance     = hinstance
            wc2.lpszClassName = "ClipboardSyncWatcher"

            user32.RegisterClassW(ctypes.byref(wc2))
            user32.CreateWindowExW(
                0, "ClipboardSyncWatcher", "ClipboardSyncWatcher",
                0, 0, 0, 0, 0, None, None, hinstance, None
            )
            log.info("🔋 Sleep/Wake detector đang chạy...")

            msg_struct = ctypes.wintypes.MSG()
            while True:
                bret = user32.GetMessageW(ctypes.byref(msg_struct), None, 0, 0)
                if bret == 0 or bret == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg_struct))
                user32.DispatchMessageW(ctypes.byref(msg_struct))

        except Exception as e:
            log.error(f"SleepWakeDetector lỗi: {e}")
            log.info("⚠️  Fallback: dùng heartbeat để phát hiện wake up")


# ================================================================
#  Clipboard Server
# ================================================================
class ClipboardServer:
    def __init__(self, host="0.0.0.0", port=9999):
        self.host = host
        self.port = port
        self.server_socket  = None
        self.client_socket  = None
        self.running        = False
        self.last_clipboard = ""
        self.connection_lock = threading.Lock()
        self.connected_event = threading.Event()
        self._force_restart  = threading.Event()

    def start(self):
        self.running = True
        log.info("=" * 50)
        log.info("  CLIPBOARD SYNC — SERVER")
        log.info("=" * 50)
        log.info(f"Listening on {self.host}:{self.port}")

        SleepWakeDetector(on_sleep=self._on_sleep, on_wake=self._on_wake).start()
        threading.Thread(target=self._heartbeat_watchdog, daemon=True).start()
        threading.Thread(target=self._connection_manager, daemon=True).start()
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        threading.Thread(target=self.receive_clipboard, daemon=True).start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Đang dừng server...")
            self.stop()

    # ----------------------------------------------------------
    # Sleep / Wake
    # ----------------------------------------------------------
    def _on_sleep(self):
        log.info("💤 Xử lý sleep: đóng socket...")
        with self.connection_lock:
            self._close_client()
            self._close_server_socket()
        self.connected_event.clear()

    def _on_wake(self):
        log.info("☀️  Wake up — đợi network ổn định (3s)...")
        time.sleep(3)
        log.info("🔄 Khởi động lại server socket...")
        self._force_restart.set()

    def _heartbeat_watchdog(self):
        INTERVAL = 5
        MAX_SKIP = 15
        last_tick = time.time()
        while self.running:
            time.sleep(INTERVAL)
            now = time.time()
            gap = now - last_tick
            last_tick = now
            if gap > MAX_SKIP:
                log.info(f"⏰ Watchdog phát hiện gap {gap:.1f}s → máy vừa wake!")
                self._on_wake()

    # ----------------------------------------------------------
    # Connection manager
    # ----------------------------------------------------------
    def _connection_manager(self):
        while self.running:
            self._force_restart.clear()

            if not self._bind_server():
                time.sleep(3)
                continue

            log.info("⏳ Đợi client kết nối...")
            client_socket, addr = self._accept_client()

            if client_socket is None:
                self._close_server_socket()
                if self._force_restart.is_set():
                    log.info("🔄 Force restart do wake up...")
                continue

            with self.connection_lock:
                self.client_socket = client_socket

            log.info(f"✅ Client kết nối từ {addr}")
            self.connected_event.set()

            # Chờ đến khi client disconnect
            self._wait_for_disconnect()

            log.info("⚠️  Client đã ngắt kết nối — chuẩn bị nhận client mới...")
            with self.connection_lock:
                self._close_client()
            self.connected_event.clear()
            self._close_server_socket()

    def _bind_server(self):
        for attempt in range(1, 6):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(5.0)
                s.bind((self.host, self.port))
                s.listen(1)
                self.server_socket = s
                return True
            except OSError as e:
                log.warning(f"Bind thất bại lần {attempt}: {e} — thử lại sau 2s...")
                time.sleep(2)
        log.error(f"Không thể bind cổng {self.port} sau 5 lần thử!")
        return False

    def _accept_client(self):
        while self.running and not self._force_restart.is_set():
            try:
                client_socket, addr = self.server_socket.accept()
                client_socket.settimeout(None)
                return client_socket, addr
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log.error(f"Accept lỗi: {e}")
                return None, None
        return None, None

    def _wait_for_disconnect(self):
        """
        Dùng MSG_PEEK để phát hiện client đóng kết nối mà không
        lấy mất data (receive_clipboard sẽ xử lý data thật).
        recv() trả về b"" = client đã đóng kết nối.
        """
        with self.connection_lock:
            sock = self.client_socket
        if not sock:
            return

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass

        sock.settimeout(2.0)

        while self.running and not self._force_restart.is_set():
            try:
                data = sock.recv(1, socket.MSG_PEEK)
                if data == b"":
                    log.info("⚠️  Detect disconnect (MSG_PEEK)")
                    break
                time.sleep(0.5)
            except socket.timeout:
                continue
            except Exception:
                break

    # ----------------------------------------------------------
    # Monitor clipboard
    # ----------------------------------------------------------
    def monitor_clipboard(self):
        log.info("👁️  Theo dõi clipboard...")
        while self.running:
            if not self.connected_event.wait(timeout=1):
                continue
            try:
                current = pyperclip.paste()
                if current and current != self.last_clipboard:
                    self.last_clipboard = current
                    self._send(current)
            except Exception as e:
                log.error(f"Monitor lỗi: {e}")
            time.sleep(0.5)

    def _send(self, text):
        try:
            with self.connection_lock:
                sock = self.client_socket
            if sock and self.connected_event.is_set():
                payload = json.dumps({"text": text}) + "\n"
                sock.sendall(payload.encode("utf-8"))
                log.info(f"📤 Gửi: {text[:60]}{'...' if len(text) > 60 else ''}")
        except Exception as e:
            log.error(f"Gửi lỗi: {e}")
            self.connected_event.clear()

    # ----------------------------------------------------------
    # Receive clipboard
    # ----------------------------------------------------------
    def receive_clipboard(self):
        log.info("📥 Sẵn sàng nhận dữ liệu...")
        while self.running:
            if not self.connected_event.wait(timeout=1):
                continue

            with self.connection_lock:
                sock = self.client_socket

            if not sock:
                time.sleep(1)
                continue

            buffer = ""
            try:
                sock.settimeout(1.0)
                while self.running and self.connected_event.is_set():
                    try:
                        chunk = sock.recv(4096).decode("utf-8")
                    except socket.timeout:
                        continue

                    if not chunk:
                        log.info("⚠️  receive_clipboard: client ngắt kết nối")
                        self.connected_event.clear()
                        break

                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                msg  = json.loads(line)
                                text = msg.get("text", "")
                                if text and text != self.last_clipboard:
                                    self.last_clipboard = text
                                    pyperclip.copy(text)
                                    log.info(f"📨 Nhận: {text[:60]}{'...' if len(text) > 60 else ''}")
                            except json.JSONDecodeError:
                                pass

            except Exception as e:
                # WinError 10053/10054 = OS hủy socket khi tắt/restart máy → bình thường
                err_str = str(e)
                expected = ("10053", "10054", "10061", "forcibly closed", "aborted")
                if self.running and not any(code in err_str for code in expected):
                    log.error(f"Nhận lỗi: {e}")
                else:
                    log.info(f"🔌 Kết nối đóng do shutdown/restart — sẽ reconnect...")
                self.connected_event.clear()

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _close_client(self):
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None

    def _close_server_socket(self):
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

    def stop(self):
        self.running = False
        self.connected_event.set()
        self._force_restart.set()
        with self.connection_lock:
            self._close_client()
        self._close_server_socket()
        log.info("✅ Server đã dừng")


if __name__ == "__main__":
    server = ClipboardServer()
    server.start()
