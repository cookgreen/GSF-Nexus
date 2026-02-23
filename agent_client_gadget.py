import sys
import os
import requests
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

try:
    from gsf.gadget_base import BaseGadget
except ImportError:
    from base_gadget import BaseGadget

class SettingsDialog(QDialog):
    def __init__(self, settings_path, parent=None):
        super().__init__(parent)
        self.settings_path = settings_path
        self.setWindowTitle("Agent Client 配置")
        self.setFixedSize(320, 250)
        
        self.setStyleSheet("""
            QDialog { background-color: #2D2D30; color: #EEE; }
            QLabel { font-weight: bold; color: #CCC; }
            QLineEdit { padding: 5px; border-radius: 4px; border: 1px solid #555; background: #1E1E1E; color: white;}
            QPushButton { background-color: #0078D7; color: white; padding: 6px; border-radius: 4px; font-weight: bold;}
            QPushButton:hover { background-color: #198CE6; }
        """)

        layout = QVBoxLayout(self)

        # 后台大脑的地址 (FastAPI 的地址)
        layout.addWidget(QLabel("Agent Core 地址 (本地或云端):"))
        self.core_url = QLineEdit()
        self.core_url.setPlaceholderText("http://127.0.0.1:8000/chat")
        layout.addWidget(self.core_url)

        # 传递给大脑的 API Key
        layout.addWidget(QLabel("大模型 API Key:"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.api_key)

        # 传递给大脑的模型名称
        layout.addWidget(QLabel("模型名称:"))
        self.model_name = QLineEdit()
        self.model_name.setPlaceholderText("gpt-4o-mini 或 deepseek-chat")
        layout.addWidget(self.model_name)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        self.load_settings()

    def load_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        self.core_url.setText(settings.value("agent/core_url", "http://127.0.0.1:8000/chat"))
        self.api_key.setText(settings.value("agent/api_key", ""))
        self.model_name.setText(settings.value("agent/model_name", "gpt-4o-mini"))

    def save_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        settings.setValue("agent/core_url", self.core_url.text().strip())
        settings.setValue("agent/api_key", self.api_key.text().strip())
        settings.setValue("agent/model_name", self.model_name.text().strip())
        self.accept()


# --- 2. 通信线程 (负责给大脑发消息，不卡顿 UI) ---
class ClientWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, prompt, config):
        super().__init__()
        self.prompt = prompt
        self.config = config

    def run(self):
        core_url = self.config.get("core_url", "http://127.0.0.1:8000/chat")
        
        # 组装发给大脑的数据包
        # 注意：这里我们加入了一个 user_id，后台可以通过这个 ID 区分是桌面端还是手机端
        payload = {
            "user_id": "gsf_desktop_client", 
            "text": self.prompt,
            "api_key": self.config.get("api_key", ""),
            "model": self.config.get("model_name", "gpt-4o-mini"),
            # 如果你后台需要 base_url，也可以在这里传
            "base_url": "https://api.deepseek.com/v1" if "deepseek" in self.config.get("model_name", "") else None
        }

        try:
            # 向 Agent Core 发起 HTTP POST 请求
            res = requests.post(core_url, json=payload, timeout=30)
            res.raise_for_status() # 检查 HTTP 状态码
            
            # 解析大脑返回的回复
            data = res.json()
            self.response_ready.emit(data.get("reply", "无内容返回"))
            
        except requests.exceptions.ConnectionError:
            self.response_ready.emit("⚠️ 无法连接大脑！请确认后台 Agent Core (8000端口) 已启动。")
        except Exception as e:
            self.response_ready.emit(f"通信错误: {str(e)}")


# --- 3. 桌面 UI 本体 (极轻量级) ---
class AgentClientGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        self.gadget_path = gadget_path
        self.settings_file = os.path.join(self.gadget_path, 'config.ini')

        # 桌面宠物标准样式：无边框、置顶、防任务栏显示 (因为改用对话框输入，这里用 Qt.Tool 不会卡焦点了)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.resize(300, 160)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setAlignment(Qt.AlignBottom | Qt.AlignRight)

        # --- 气泡 (Bubble) ---
        self.bubble = QLabel("双击我开始聊天！\n记得先启动 Agent Core 哦。")
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet("""
            QLabel {
                background-color: #FFF9E6; color: #333;
                border: 1px solid #CCC; border-radius: 12px;
                padding: 12px; font-size: 13px; font-family: 'Segoe UI';
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(2, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.bubble.setGraphicsEffect(shadow)
        self.layout.addWidget(self.bubble)

        # 气泡定时器 (5秒后自动隐藏)
        self.bubble_timer = QTimer()
        self.bubble_timer.timeout.connect(lambda: self.bubble.setVisible(False))
        self.bubble_timer.start(5000)

        # --- 形象 (Avatar) ---
        self.avatar = QLabel("🤖")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(65, 65)
        self.avatar.setStyleSheet("font-size: 45px; background: transparent;")
        self.avatar.setCursor(Qt.PointingHandCursor)
        
        img_path = os.path.join(self.gadget_path, "assets", "avatar.png")
        if os.path.exists(img_path):
            self.avatar.setText("")
            self.avatar.setPixmap(QPixmap(img_path).scaled(65, 65, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        self.layout.addWidget(self.avatar, 0, Qt.AlignRight)

    # --- 交互逻辑 ---
    def populate_context_menu(self, menu):
        """右键菜单"""
        menu.addSeparator()
        setting_action = menu.addAction("⚙️ 配置连接 (Settings)...")
        setting_action.triggered.connect(self.open_settings)
        
        poke_action = menu.addAction("👈 状态检查 (Ping)")
        poke_action.triggered.connect(lambda: self.send_to_core("系统自检：请用一句话告诉我你在线。"))

    def open_settings(self):
        dialog = SettingsDialog(self.settings_file, self)
        if dialog.exec():
            self.show_bubble("配置已更新！", 3000)

    def mouseDoubleClickEvent(self, event):
        """双击弹出系统的输入框，完美避开无边框窗口焦点丢失的 Bug"""
        if event.button() == Qt.LeftButton:
            text, ok = QInputDialog.getText(self, "Agent 指令", "输入你的问题或指令：")
            if ok and text.strip():
                self.send_to_core(text.strip())

    def send_to_core(self, text):
        """发送消息给后台大脑"""
        settings = QSettings(self.settings_file, QSettings.IniFormat)
        config = {
            "core_url": settings.value("agent/core_url", "http://127.0.0.1:8000/chat"),
            "api_key": settings.value("agent/api_key", ""),
            "model_name": settings.value("agent/model_name", "gpt-4o-mini")
        }
        
        self.show_bubble("⏳ 正在联系大脑...", 0)
        
        # 启动线程发起网络请求
        self.worker = ClientWorker(text, config)
        self.worker.response_ready.connect(lambda reply: self.show_bubble(reply, 10000))
        self.worker.start()

    def show_bubble(self, text, duration=5000):
        self.bubble.setText(text)
        self.bubble.setVisible(True)
        self.bubble.adjustSize()
        if duration > 0:
            self.bubble_timer.start(duration)
        else:
            self.bubble_timer.stop()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gadget = AgentClientGadget(".")
    gadget.show()
    sys.exit(app.exec())