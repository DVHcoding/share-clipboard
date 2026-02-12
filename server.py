import socket
import threading
import time
import pyperclip
import json
import sys

class ClipboardServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.last_clipboard = ""
        self.connection_lock = threading.Lock()
        self.reconnect_event = threading.Event()
        
    def start(self):
        """Khởi động server với khả năng reconnect"""
        self.running = True
        
        print(f"🚀 Server đang chạy trên {self.host}:{self.port}")
        
        # Thread quản lý kết nối
        threading.Thread(target=self.manage_connections, daemon=True).start()
        
        # Bắt đầu các thread
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        threading.Thread(target=self.receive_clipboard, daemon=True).start()
        
        # Giữ chương trình chạy
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Đang dừng server...")
            self.stop()
    
    def manage_connections(self):
        """Quản lý kết nối - tự động reconnect khi mất kết nối"""
        while self.running:
            try:
                # Tạo socket mới
                if self.server_socket:
                    try:
                        self.server_socket.close()
                    except:
                        pass
                
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Thêm timeout để tránh block vĩnh viễn
                self.server_socket.settimeout(5.0)
                
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(1)
                
                print(f"⏳ Đợi client kết nối...")
                
                try:
                    client_socket, addr = self.server_socket.accept()
                    # Bỏ timeout sau khi accept
                    client_socket.settimeout(None)
                    
                    with self.connection_lock:
                        self.client_socket = client_socket
                    
                    print(f"✅ Client đã kết nối từ {addr}")
                    self.reconnect_event.set()
                    
                    # Chờ cho đến khi kết nối bị ngắt
                    while self.running:
                        try:
                            # Gửi heartbeat để kiểm tra kết nối
                            self.client_socket.sendall(b'')
                            time.sleep(5)
                        except:
                            print("⚠️  Mất kết nối - chuẩn bị reconnect...")
                            break
                            
                except socket.timeout:
                    # Timeout khi chờ client - tiếp tục loop
                    continue
                    
            except Exception as e:
                if self.running:
                    print(f"❌ Lỗi kết nối: {e}")
                    print("🔄 Thử kết nối lại sau 3 giây...")
                    time.sleep(3)
            
            # Reset client socket
            with self.connection_lock:
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except:
                        pass
                    self.client_socket = None
                self.reconnect_event.clear()
    
    def monitor_clipboard(self):
        """Theo dõi thay đổi clipboard và gửi đến client"""
        print("🔍️ Bắt đầu theo dõi clipboard...")
        while self.running:
            try:
                # Đợi có kết nối
                if not self.reconnect_event.is_set():
                    self.reconnect_event.wait(timeout=1)
                    continue
                
                current = pyperclip.paste()
                if current != self.last_clipboard and current:
                    self.last_clipboard = current
                    self.send_clipboard(current)
                time.sleep(0.5)
            except Exception as e:
                if self.running:
                    print(f"❌ Lỗi monitor: {e}")
                time.sleep(1)
    
    def send_clipboard(self, text):
        """Gửi nội dung clipboard đến client"""
        try:
            with self.connection_lock:
                if self.client_socket:
                    data = json.dumps({"text": text})
                    self.client_socket.sendall(data.encode('utf-8') + b'\n')
                    print(f"📤 Đã gửi: {text[:50]}...")
        except Exception as e:
            if self.running:
                print(f"❌ Lỗi gửi: {e}")
    
    def receive_clipboard(self):
        """Nhận nội dung clipboard từ client"""
        print("📥 Sẵn sàng nhận dữ liệu...")
        buffer = ""
        
        while self.running:
            try:
                # Đợi có kết nối
                if not self.reconnect_event.is_set():
                    self.reconnect_event.wait(timeout=1)
                    buffer = ""  # Reset buffer khi reconnect
                    continue
                
                with self.connection_lock:
                    client_socket = self.client_socket
                
                if not client_socket:
                    time.sleep(1)
                    continue
                
                # Set timeout ngắn để tránh block
                client_socket.settimeout(1.0)
                
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                except socket.timeout:
                    continue
                
                if not data:
                    print("⚠️  Client đã ngắt kết nối")
                    time.sleep(1)
                    continue
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            text = msg.get('text', '')
                            if text and text != self.last_clipboard:
                                self.last_clipboard = text
                                pyperclip.copy(text)
                                print(f"📨 Đã nhận: {text[:50]}...")
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                if self.running:
                    print(f"❌ Lỗi nhận: {e}")
                time.sleep(1)
    
    def stop(self):
        """Dừng server"""
        self.running = False
        self.reconnect_event.set()  # Đánh thức các thread đang chờ
        
        with self.connection_lock:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        print("✅ Server đã dừng")

if __name__ == "__main__":
    print("=" * 50)
    print("    CLIPBOARD SYNC - SERVER MODE")
    print("=" * 50)
    
    server = ClipboardServer()
    server.start()
