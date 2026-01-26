import socket
import threading
import time
import pyperclip
import json

class ClipboardServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.last_clipboard = ""
        
    def start(self):
        """Khởi động server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.running = True
        
        print(f"🟢 Server đang chạy trên {self.host}:{self.port}")
        print(f"📋 Đợi client kết nối...")
        
        # Chờ client kết nối
        self.client_socket, addr = self.server_socket.accept()
        print(f"✅ Client đã kết nối từ {addr}")
        
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
    
    def monitor_clipboard(self):
        """Theo dõi thay đổi clipboard và gửi đến client"""
        print("👁️  Bắt đầu theo dõi clipboard...")
        while self.running:
            try:
                current = pyperclip.paste()
                if current != self.last_clipboard and current:
                    self.last_clipboard = current
                    self.send_clipboard(current)
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ Lỗi monitor: {e}")
    
    def send_clipboard(self, text):
        """Gửi nội dung clipboard đến client"""
        try:
            if self.client_socket:
                data = json.dumps({"text": text})
                self.client_socket.sendall(data.encode('utf-8') + b'\n')
                print(f"📤 Đã gửi: {text[:50]}...")
        except Exception as e:
            print(f"❌ Lỗi gửi: {e}")
    
    def receive_clipboard(self):
        """Nhận nội dung clipboard từ client"""
        print("📥 Sẵn sàng nhận dữ liệu...")
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    print("⚠️  Client đã ngắt kết nối")
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        msg = json.loads(line)
                        text = msg.get('text', '')
                        if text and text != self.last_clipboard:
                            self.last_clipboard = text
                            pyperclip.copy(text)
                            print(f"📥 Đã nhận: {text[:50]}...")
            except Exception as e:
                print(f"❌ Lỗi nhận: {e}")
                break
    
    def stop(self):
        """Dừng server"""
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        print("✅ Server đã dừng")

if __name__ == "__main__":
    print("=" * 50)
    print("    CLIPBOARD SYNC - SERVER MODE")
    print("=" * 50)
    
    server = ClipboardServer()
    server.start()
