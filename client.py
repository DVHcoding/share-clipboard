import socket
import threading
import time
import pyperclip
import json

class ClipboardClient:
    def __init__(self, server_ip, port=9999):
        self.server_ip = server_ip
        self.port = port
        self.socket = None
        self.running = False
        self.last_clipboard = ""
        
    def connect(self):
        """Kết nối đến server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.port))
            self.running = True
            print(f"✅ Đã kết nối đến server {self.server_ip}:{self.port}")
            
            # Bắt đầu các thread
            threading.Thread(target=self.monitor_clipboard, daemon=True).start()
            threading.Thread(target=self.receive_clipboard, daemon=True).start()
            
            # Giữ chương trình chạy
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Đang ngắt kết nối...")
                self.stop()
                
        except Exception as e:
            print(f"❌ Không thể kết nối: {e}")
            print("💡 Hãy kiểm tra:")
            print("   - Server đã chạy chưa?")
            print(f"   - IP {self.server_ip} có đúng không?")
            print("   - Firewall có chặn cổng 9999 không?")
    
    def monitor_clipboard(self):
        """Theo dõi thay đổi clipboard và gửi đến server"""
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
        """Gửi nội dung clipboard đến server"""
        try:
            if self.socket:
                data = json.dumps({"text": text})
                self.socket.sendall(data.encode('utf-8') + b'\n')
                print(f"📤 Đã gửi: {text[:50]}...")
        except Exception as e:
            print(f"❌ Lỗi gửi: {e}")
            self.running = False
    
    def receive_clipboard(self):
        """Nhận nội dung clipboard từ server"""
        print("📥 Sẵn sàng nhận dữ liệu...")
        buffer = ""
        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    print("⚠️  Server đã ngắt kết nối")
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
        
        self.running = False
    
    def stop(self):
        """Ngắt kết nối"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("✅ Đã ngắt kết nối")

if __name__ == "__main__":
    print("=" * 50)
    print("    CLIPBOARD SYNC - CLIENT MODE")
    print("=" * 50)
    
    server_ip = input("Nhập IP của Server: ").strip()
    
    if not server_ip:
        print("❌ IP không được để trống!")
    else:
        client = ClipboardClient(server_ip)
        client.connect()
