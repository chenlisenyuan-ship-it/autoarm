#!/usr/bin/env python3
"""
UI界面模块
职责：提供深色现代风格的图形界面，实时显示摄像头画面与调试信息。
界面布局：
- 整体风格：深色背景 #1E222A，圆角卡片，白色文字。
- 左侧栏（30%）：调试信息流，显示状态、FPS、距离等。
- 右侧栏（70%）：OpenCV实时视频渲染区。
"""

import sys
import time
from datetime import datetime
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QGroupBox, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QPalette, QTextCursor

import cv2
import numpy as np


class MainWindow(QMainWindow):
    """主窗口类"""

    # 信号定义
    emergency_stop_signal = Signal()  # 急停信号
    connect_arm_signal = Signal()     # 连接机械臂信号
    disconnect_arm_signal = Signal()  # 断开机械臂信号

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化主窗口

        :param config: 配置字典
        """
        super().__init__()

        # 配置
        self.config = config or {}
        self.theme = self.config.get('theme', 'dark')
        self.background_color = self.config.get('background_color', '#1E222A')
        self.update_interval_ms = self.config.get('update_interval_ms', 50)
        self.debug_max_lines = self.config.get('debug_max_lines', 1000)

        # 状态变量
        self.video_frame = None
        self.debug_data = {}
        self.arm_connected = False
        self.camera_connected = False
        self.emergency_stopped = False

        # 初始化UI
        self.init_ui()

        # 设置定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(self.update_interval_ms)

        # 性能统计
        self.frame_count = 0
        self.last_fps_time = time.time()

        print("[MainWindow] 初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("基于视觉伺服的手势控制机械臂系统")
        self.setGeometry(100, 100, 1400, 800)  # 初始大小

        # 设置整体样式
        self._apply_theme()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局（水平分割）
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 左侧栏（30%）：调试信息面板
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, stretch=3)  # 3份宽度

        # 右侧栏（70%）：视频渲染面板
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, stretch=7)  # 7份宽度

        # 状态栏
        self._create_status_bar()

    def _apply_theme(self):
        """应用主题样式"""
        if self.theme == 'dark':
            # 深色主题
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {self.background_color};
                }}
                QGroupBox {{
                    color: #FFFFFF;
                    font-weight: bold;
                    border: 2px solid #3A3F4B;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }}
                QTextEdit {{
                    background-color: #2A2E3A;
                    color: #E0E0E0;
                    border: 1px solid #3A3F4B;
                    border-radius: 4px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                }}
                QLabel {{
                    color: #FFFFFF;
                }}
                QPushButton {{
                    background-color: #3A3F4B;
                    color: #FFFFFF;
                    border: 1px solid #4A4F5B;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #4A4F5B;
                }}
                QPushButton:pressed {{
                    background-color: #2A2E3A;
                }}
                QPushButton#emergencyButton {{
                    background-color: #DC3545;
                    color: #FFFFFF;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 12px 24px;
                }}
                QPushButton#emergencyButton:hover {{
                    background-color: #C82333;
                }}
                QPushButton#connectButton {{
                    background-color: #28A745;
                    color: #FFFFFF;
                }}
                QPushButton#connectButton:hover {{
                    background-color: #218838;
                }}
                QPushButton#disconnectButton {{
                    background-color: #6C757D;
                    color: #FFFFFF;
                }}
                QPushButton#disconnectButton:hover {{
                    background-color: #5A6268;
                }}
            """)
        else:
            # 浅色主题
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: #F8F9FA;
                }}
                QGroupBox {{
                    color: #212529;
                    font-weight: bold;
                    border: 2px solid #DEE2E6;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }}
                QTextEdit {{
                    background-color: #FFFFFF;
                    color: #212529;
                    border: 1px solid #CED4DA;
                    border-radius: 4px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                }}
                QPushButton {{
                    background-color: #E9ECEF;
                    color: #212529;
                    border: 1px solid #CED4DA;
                    border-radius: 4px;
                    padding: 8px 16px;
                }}
                QPushButton#emergencyButton {{
                    background-color: #DC3545;
                    color: #FFFFFF;
                    font-size: 14px;
                    font-weight: bold;
                }}
            """)

    def _create_left_panel(self) -> QWidget:
        """创建左侧调试信息面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(10)

        # 1. 系统状态组
        status_group = QGroupBox("📊 系统状态")
        status_layout = QGridLayout()

        # 状态标签
        self.camera_status_label = QLabel("❌ 摄像头: 未连接")
        self.arm_status_label = QLabel("❌ 机械臂: 未连接")
        self.fps_label = QLabel("FPS: 0.0")
        self.detection_rate_label = QLabel("手势检测率: 0.0%")

        status_layout.addWidget(self.camera_status_label, 0, 0)
        status_layout.addWidget(self.arm_status_label, 1, 0)
        status_layout.addWidget(self.fps_label, 2, 0)
        status_layout.addWidget(self.detection_rate_label, 3, 0)

        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # 2. 手势特征组
        features_group = QGroupBox("👋 手势特征")
        features_layout = QVBoxLayout()

        self.features_text = QTextEdit()
        self.features_text.setReadOnly(True)
        self.features_text.setMaximumHeight(150)
        self.features_text.setPlainText("等待手势检测...")

        features_layout.addWidget(self.features_text)
        features_group.setLayout(features_layout)
        left_layout.addWidget(features_group)

        # 3. 控制参数组
        control_group = QGroupBox("🎛️ 控制参数")
        control_layout = QVBoxLayout()

        # 滤波系数
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("滤波系数 (α):"))
        self.filter_value_label = QLabel("0.40")
        filter_layout.addWidget(self.filter_value_label)
        filter_layout.addStretch()
        control_layout.addLayout(filter_layout)

        # 死区阈值
        deadzone_layout = QHBoxLayout()
        deadzone_layout.addWidget(QLabel("死区阈值:"))
        self.deadzone_value_label = QLabel("15")
        deadzone_layout.addWidget(self.deadzone_value_label)
        deadzone_layout.addStretch()
        control_layout.addLayout(deadzone_layout)

        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)

        # 4. 关节PWM值组
        pwm_group = QGroupBox("⚙️ 关节PWM值")
        pwm_layout = QVBoxLayout()

        self.pwm_text = QTextEdit()
        self.pwm_text.setReadOnly(True)
        self.pwm_text.setMaximumHeight(150)
        self.pwm_text.setPlainText("等待控制指令...")

        pwm_layout.addWidget(self.pwm_text)
        pwm_group.setLayout(pwm_layout)
        left_layout.addWidget(pwm_group)

        # 5. 控制按钮组
        button_group = QGroupBox("🔧 控制")
        button_layout = QVBoxLayout()

        # 急停按钮
        self.emergency_button = QPushButton("⛔ 紧急停止")
        self.emergency_button.setObjectName("emergencyButton")
        self.emergency_button.clicked.connect(self._on_emergency_stop)
        button_layout.addWidget(self.emergency_button)

        # 连接/断开按钮
        button_row = QHBoxLayout()
        self.connect_button = QPushButton("🔗 连接机械臂")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.clicked.connect(self._on_connect_arm)
        button_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("🔌 断开机械臂")
        self.disconnect_button.setObjectName("disconnectButton")
        self.disconnect_button.clicked.connect(self._on_disconnect_arm)
        self.disconnect_button.setEnabled(False)
        button_row.addWidget(self.disconnect_button)

        button_layout.addLayout(button_row)
        button_group.setLayout(button_layout)
        left_layout.addWidget(button_group)

        # 6. 调试信息流
        debug_group = QGroupBox("📝 调试信息流")
        debug_layout = QVBoxLayout()

        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setLineWrapMode(QTextEdit.NoWrap)

        debug_layout.addWidget(self.debug_text)
        debug_group.setLayout(debug_layout)
        left_layout.addWidget(debug_group, stretch=1)

        return left_widget

    def _create_right_panel(self) -> QWidget:
        """创建右侧视频渲染面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 2px solid #3A3F4B;
                border-radius: 4px;
            }
        """)

        # 提示文本
        self.video_label.setText("正在初始化摄像头...")

        right_layout.addWidget(self.video_label, stretch=1)

        # 视频控制按钮
        control_layout = QHBoxLayout()

        self.record_button = QPushButton("⏺️ 开始录制")
        self.record_button.clicked.connect(self._on_toggle_record)
        control_layout.addWidget(self.record_button)

        self.snapshot_button = QPushButton("📸 截图")
        self.snapshot_button.clicked.connect(self._on_take_snapshot)
        control_layout.addWidget(self.snapshot_button)

        control_layout.addStretch()

        self.fullscreen_button = QPushButton("🖥️ 全屏")
        self.fullscreen_button.clicked.connect(self._on_toggle_fullscreen)
        control_layout.addWidget(self.fullscreen_button)

        right_layout.addLayout(control_layout)

        return right_widget

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        # 添加时间标签
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)

        # 更新时间
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)
        self._update_time()

    def _update_ui(self):
        """更新UI界面"""
        # 更新视频帧
        if self.video_frame is not None:
            self._update_video_display()

        # 更新调试信息
        if self.debug_data:
            self._update_debug_display()

        # 更新FPS
        self._update_fps()

    def _update_video_display(self):
        """更新视频显示"""
        try:
            # 将OpenCV图像转换为QPixmap
            h, w, ch = self.video_frame.shape
            bytes_per_line = ch * w

            # BGR转RGB，并复制数据避免悬挂引用
            rgb_image = cv2.cvtColor(self.video_frame, cv2.COLOR_BGR2RGB)
            rgb_image = rgb_image.copy()  # 确保数据独立

            # 创建QImage（复制数据）
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            qt_image = qt_image.copy()  # 确保QImage拥有独立数据

            # 缩放图像以适应标签大小
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.video_label.setPixmap(scaled_pixmap)

        except Exception as e:
            print(f"[MainWindow] 更新视频显示时出错: {e}")

    def _update_debug_display(self):
        """更新调试信息显示"""
        try:
            # 更新系统状态
            self.camera_status_label.setText(
                "✅ 摄像头: 已连接" if self.debug_data.get('camera_connected', False)
                else "❌ 摄像头: 未连接"
            )
            self.arm_status_label.setText(
                "✅ 机械臂: 已连接" if self.debug_data.get('arm_connected', False)
                else "❌ 机械臂: 未连接"
            )

            # 更新FPS
            fps = self.debug_data.get('fps', 0.0)
            self.fps_label.setText(f"FPS: {fps:.1f}")

            # 更新检测率
            detection_rate = self.debug_data.get('detection_rate', 0.0) * 100
            self.detection_rate_label.setText(f"手势检测率: {detection_rate:.1f}%")

            # 更新手势特征
            features = self.debug_data.get('features', {})
            if features:
                features_text = ""
                if 'grip_distance' in features:
                    features_text += f"夹爪距离: {features['grip_distance']:.3f}m\n"
                if 'wrist_pitch' in features:
                    features_text += f"手腕俯仰: {features['wrist_pitch']:.2f}rad\n"
                if 'wrist_roll' in features:
                    features_text += f"手腕翻滚: {features['wrist_roll']:.2f}rad\n"
                if 'hand_x' in features:
                    features_text += f"手部位置: X={features['hand_x']:.2f}, "
                    features_text += f"Y={features['hand_y']:.2f}, "
                    features_text += f"Z={features['hand_z']:.2f}"

                self.features_text.setPlainText(features_text)

            # 更新控制参数
            filter_alpha = self.debug_data.get('filter_alpha', 0.4)
            deadzone = self.debug_data.get('deadzone', 15)
            self.filter_value_label.setText(f"{filter_alpha:.2f}")
            self.deadzone_value_label.setText(f"{deadzone}")

            # 更新PWM值
            pwms = self.debug_data.get('pwms', {})
            if pwms:
                pwm_text = ""
                joint_names = {
                    'joint_1': '底座旋转',
                    'joint_2': '近端关节',
                    'joint_3': '大臂',
                    'joint_4': '小臂',
                    'joint_5': '夹爪',
                    'joint_6': '夹爪旋转',
                }

                for joint in ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6']:
                    if joint in pwms:
                        name = joint_names.get(joint, joint)
                        pwm_text += f"{name}: {pwms[joint]}\n"

                self.pwm_text.setPlainText(pwm_text)

            # 添加调试信息到信息流
            log_msg = self.debug_data.get('log_message')
            if log_msg:
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_line = f"[{timestamp}] {log_msg}"

                # 添加到文本区域
                self.debug_text.append(log_line)

                # 限制行数
                lines = self.debug_text.toPlainText().split('\n')
                if len(lines) > self.debug_max_lines:
                    self.debug_text.setPlainText('\n'.join(lines[-self.debug_max_lines:]))

                # 滚动到底部
                self.debug_text.moveCursor(QTextCursor.End)

        except Exception as e:
            print(f"[MainWindow] 更新调试信息时出错: {e}")

    def _update_fps(self):
        """更新FPS统计"""
        self.frame_count += 1
        current_time = time.time()

        if current_time - self.last_fps_time >= 1.0:
            fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time

            # 更新状态栏
            self.status_label.setText(f"运行中 | FPS: {fps:.1f}")

    def _update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(current_time)

    # 公共接口方法
    @Slot(np.ndarray)
    def update_video_frame(self, frame: np.ndarray):
        """
        更新右侧视频区的图像

        :param frame: numpy.ndarray (H, W, 3) BGR格式
        """
        self.video_frame = frame.copy()

    @Slot(dict)
    def update_debug_data(self, data_dict: Dict):
        """
        更新左侧调试信息

        :param data_dict: dict 包含调试信息
        """
        self.debug_data.update(data_dict)

        # 更新连接状态
        if 'arm_connected' in data_dict:
            self.arm_connected = data_dict['arm_connected']
            self.connect_button.setEnabled(not self.arm_connected)
            self.disconnect_button.setEnabled(self.arm_connected)

        if 'camera_connected' in data_dict:
            self.camera_connected = data_dict['camera_connected']

    # 槽函数
    def _on_emergency_stop(self):
        """急停按钮点击事件"""
        self.emergency_stopped = True
        self.emergency_stop_signal.emit()

        # 更新UI
        self.emergency_button.setEnabled(False)
        self.emergency_button.setText("🛑 已急停")
        self.status_label.setText("⚠️ 急停已触发")

        # 记录日志
        self.debug_data['log_message'] = "急停已触发，所有关节回到安全位置"

    def _on_connect_arm(self):
        """连接机械臂按钮点击事件"""
        self.connect_arm_signal.emit()
        self.status_label.setText("正在连接机械臂...")

    def _on_disconnect_arm(self):
        """断开机械臂按钮点击事件"""
        self.disconnect_arm_signal.emit()
        self.status_label.setText("正在断开机械臂连接...")

    def _on_toggle_record(self):
        """切换录制状态"""
        # TODO: 实现录制功能
        self.status_label.setText("录制功能未实现")

    def _on_take_snapshot(self):
        """截图按钮点击事件"""
        if self.video_frame is not None:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"snapshot_{timestamp}.jpg"
                cv2.imwrite(filename, self.video_frame)
                self.status_label.setText(f"截图已保存: {filename}")
                print(f"[MainWindow] 截图已保存: {filename}")
            except Exception as e:
                self.status_label.setText(f"截图失败: {str(e)}")
                print(f"[MainWindow] 截图失败: {e}")
        else:
            self.status_label.setText("无视频帧可截图")

    def _on_toggle_fullscreen(self):
        """切换全屏状态"""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("🖥️ 全屏")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("📺 退出全屏")

    def closeEvent(self, event):
        """窗口关闭事件"""
        print("[MainWindow] 正在关闭...")

        # 停止定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()

        if hasattr(self, 'time_timer'):
            self.time_timer.stop()

        # 发送断开连接信号
        if self.arm_connected:
            self.disconnect_arm_signal.emit()

        event.accept()


# 测试函数
def test_main_window():
    """测试主窗口模块"""
    print("测试主窗口模块...")

    app = QApplication(sys.argv)

    # 创建配置
    config = {
        'theme': 'dark',
        'background_color': '#1E222A',
        'update_interval_ms': 50,
        'debug_max_lines': 1000,
    }

    # 创建主窗口
    window = MainWindow(config)

    # 测试信号连接
    def on_emergency_stop():
        print("急停信号触发")

    def on_connect_arm():
        print("连接机械臂信号触发")

    def on_disconnect_arm():
        print("断开机械臂信号触发")

    window.emergency_stop_signal.connect(on_emergency_stop)
    window.connect_arm_signal.connect(on_connect_arm)
    window.disconnect_arm_signal.connect(on_disconnect_arm)

    # 模拟视频帧更新
    def simulate_video_update():
        # 创建测试图像
        width, height = 640, 480
        test_frame = np.zeros((height, width, 3), dtype=np.uint8)

        # 绘制渐变背景
        for y in range(height):
            color = int(255 * y / height)
            test_frame[y, :] = [color, color // 2, 255 - color]

        # 绘制文本
        cv2.putText(test_frame, "测试视频流", (width//4, height//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(test_frame, "手势控制机械臂系统", (width//6, height//2 + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 100), 2)

        # 更新视频帧
        window.update_video_frame(test_frame)

    # 模拟调试数据更新
    def simulate_debug_update():
        test_data = {
            'camera_connected': True,
            'arm_connected': False,
            'fps': 29.5,
            'detection_rate': 0.85,
            'features': {
                'grip_distance': 0.125,
                'wrist_pitch': 0.34,
                'wrist_roll': -0.21,
                'hand_x': 0.05,
                'hand_y': -0.12,
                'hand_z': 0.45,
            },
            'filter_alpha': 0.4,
            'deadzone': 15,
            'pwms': {
                'joint_1': 1500,
                'joint_2': 1450,
                'joint_3': 1550,
                'joint_4': 1600,
                'joint_5': 1200,
                'joint_6': 1500,
            },
            'log_message': "测试调试信息"
        }

        # 随机修改一些值以模拟实时更新
        import random
        test_data['fps'] = 25 + random.random() * 10
        test_data['features']['grip_distance'] = 0.1 + random.random() * 0.1
        test_data['features']['hand_x'] = random.random() * 0.4 - 0.2

        window.update_debug_data(test_data)

    # 设置定时器模拟更新
    video_timer = QTimer()
    video_timer.timeout.connect(simulate_video_update)
    video_timer.start(100)  # 10 FPS

    debug_timer = QTimer()
    debug_timer.timeout.connect(simulate_debug_update)
    debug_timer.start(500)  # 2 Hz

    # 显示窗口
    window.show()

    print("主窗口已显示，按 Ctrl+C 退出测试...")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\n测试被用户中断")

    print("测试完成")


if __name__ == "__main__":
    test_main_window()