import socket
import threading
import time
import pyperclip
import json
import logging
import os
import sys

# --- Logging ra file (vì chạy ngầm không có terminal) ---
LOG_FILE = os.path.expanduser("~/clipboard_sync_client.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        # Bỏ comment dòng dưới nếu muốn in ra terminal khi test
        # logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


class ClipboardClient:
    def __init__(self, server_ip, port=9999, retry_interval=5):
        self.server_ip = server_ip
        self.port = port
        self.retry_interval = retry_interval
        self.socket = None
        self.running = True
        self.connected = False
        self.last_clipboard = ""
        self.lock = threading.Lock()
        self.connected_event = threading.Event()

    def start(self):
        """Vòng lặp chính: kết nối + tự reconnect khi mất"""
        log.info("=== Clipboard Sync Client khởi động ===")
        log.info(f"Server: {self.server_ip}:{self.port}")

        # Thread theo dõi clipboard (luôn chạy)
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        # Thread nhận dữ liệu từ server (luôn chạy, tự reset khi mất kết nối)
        threading.Thread(target=self.receive_loop, daemon=True).start()

        # Vòng lặp kết nối chính
        while self.running:
            if not self.connected:
                self._try_connect()
            time.sleep(1)

    def _try_connect(self):
        """Thử kết nối, trả về True nếu thành công"""
        try:
            log.info(f"🔄 Đang kết nối đến {self.server_ip}:{self.port}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.server_ip, self.port))
            s.settimeout(None)

            with self.lock:
                self.socket = s
                self.connected = True

            self.connected_event.set()
            log.info(f"✅ Đã kết nối đến server!")
            return True

        except Exception as e:
            log.warning(f"❌ Kết nối thất bại: {e}. Thử lại sau {self.retry_interval}s...")
            time.sleep(self.retry_interval)
            return False

    def _disconnect(self):
        """Đánh dấu mất kết nối, đóng socket cũ"""
        with self.lock:
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
        self.connected_event.clear()
        log.warning("⚠️  Mất kết nối — sẽ tự reconnect...")

    # ------------------------------------------------------------------
    # Thread 1: Theo dõi clipboard local và gửi lên server
    # ------------------------------------------------------------------
    def monitor_clipboard(self):
        log.info("👁️  Bắt đầu theo dõi clipboard local...")
        while self.running:
            # Đợi có kết nối trước khi gửi
            self.connected_event.wait(timeout=2)

            try:
                current = pyperclip.paste()
                if current and current != self.last_clipboard:
                    self.last_clipboard = current
                    self._send(current)
            except Exception as e:
                log.error(f"Lỗi đọc clipboard: {e}")

            time.sleep(0.5)

    def _send(self, text):
        try:
            with self.lock:
                sock = self.socket
            if sock and self.connected:
                payload = json.dumps({"text": text}) + "\n"
                sock.sendall(payload.encode("utf-8"))
                log.info(f"📤 Gửi: {text[:60]}{'...' if len(text) > 60 else ''}")
        except Exception as e:
            log.error(f"Lỗi gửi: {e}")
            self._disconnect()

    # ------------------------------------------------------------------
    # Thread 2: Nhận dữ liệu từ server
    # ------------------------------------------------------------------
    def receive_loop(self):
        log.info("📥 Sẵn sàng nhận dữ liệu từ server...")
        while self.running:
            # Đợi có kết nối
            if not self.connected_event.wait(timeout=2):
                continue

            buffer = ""
            try:
                with self.lock:
                    sock = self.socket

                if not sock:
                    continue

                sock.settimeout(1.0)  # timeout để không block mãi

                while self.running and self.connected:
                    try:
                        chunk = sock.recv(4096).decode("utf-8")
                    except socket.timeout:
                        continue

                    if not chunk:
                        # Server đóng kết nối
                        raise ConnectionError("Server đã đóng kết nối")

                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                msg = json.loads(line)
                                text = msg.get("text", "")
                                if text and text != self.last_clipboard:
                                    self.last_clipboard = text
                                    pyperclip.copy(text)
                                    log.info(f"📨 Nhận: {text[:60]}{'...' if len(text) > 60 else ''}")
                            except json.JSONDecodeError:
                                pass

            except Exception as e:
                if self.running:
                    log.error(f"Lỗi nhận: {e}")
                self._disconnect()

    def stop(self):
        log.info("🛑 Đang dừng client...")
        self.running = False
        self.connected_event.set()
        self._disconnect()
        log.info("✅ Client đã dừng")


if __name__ == "__main__":
    SERVER_IP = "192.168.43.159"  # IP server Windows của bạn
    PORT = 9999

    client = ClipboardClient(server_ip=SERVER_IP, port=PORT, retry_interval=5)
    try:
        client.start()
    except KeyboardInterrupt:
        client.stop()
