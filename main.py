#!/usr/bin/env python3
"""
基于视觉伺服的手势控制机械臂系统 - 主程序
集成所有模块，管理线程和数据流。
"""

import sys
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Dict

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, Slot, QTimer

# 导入配置和模块
import config
from modules.vision_capture import VisionCapture
from modules.hand_detector import HandDetector
from modules.gesture_parser import GestureParser
from modules.mapping import MappingEngine
from modules.filter_control import FilterController
from modules.arm_communicator import ArmCommunicator
from modules.main_window import MainWindow


class VisionThread(QObject):
    """视觉处理线程"""

    # 信号定义
    video_frame_signal = Signal(object)  # 视频帧信号（numpy数组）
    features_signal = Signal(object)     # 特征字典信号
    debug_signal = Signal(object)        # 调试信息信号

    def __init__(self, config_dict: Dict):
        super().__init__()

        # 配置
        self.camera_config = config_dict.get('CAMERA_CONFIG', {})
        self.hand_config = config_dict.get('HAND_DETECTOR_CONFIG', {})

        # 模块初始化
        self.capture = None
        self.detector = None
        self.parser = None

        # 状态变量
        self.running = False
        self.paused = False

        # 性能统计
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = time.time()

    def initialize(self) -> bool:
        """初始化视觉模块"""
        try:
            print("[VisionThread] 初始化视觉模块...")

            # 初始化视觉采集
            self.capture = VisionCapture(
                camera_id=self.camera_config.get('id', 0),
                flip_horizontal=self.camera_config.get('flip_horizontal', True),
                width=self.camera_config.get('width', 1280),
                height=self.camera_config.get('height', 720),
                fps=self.camera_config.get('fps', 30)
            )

            if not self.capture.open():
                print("[VisionThread] 无法打开摄像头")
                return False

            # 初始化手势检测器
            self.detector = HandDetector(
                static_image_mode=self.hand_config.get('static_image_mode', False),
                max_num_hands=self.hand_config.get('max_num_hands', 1),
                min_detection_confidence=self.hand_config.get('min_detection_confidence', 0.7),
                min_tracking_confidence=self.hand_config.get('min_tracking_confidence', 0.7)
            )

            # 初始化手势解析器
            self.parser = GestureParser(
                image_width=self.camera_config.get('width', 1280),
                image_height=self.camera_config.get('height', 720)
            )

            print("[VisionThread] 视觉模块初始化完成")
            return True

        except Exception as e:
            print(f"[VisionThread] 初始化失败: {e}")
            return False

    def start_processing(self):
        """开始处理循环"""
        self.running = True
        self.paused = False

        print("[VisionThread] 开始视觉处理...")

        while self.running:
            if self.paused:
                time.sleep(0.01)
                continue

            try:
                # 1. 读取视频帧
                success, frame = self.capture.read_frame()

                if not success:
                    time.sleep(0.1)
                    continue

                # 2. 发送视频帧到UI
                self.video_frame_signal.emit(frame.copy())

                # 3. 转换为RGB用于手势检测
                rgb_frame = frame.copy()
                rgb_frame = rgb_frame[:, :, ::-1]  # BGR转RGB

                # 4. 手势检测
                results = self.detector.process(rgb_frame)

                if results and results.multi_hand_landmarks:
                    hand_landmarks = results.multi_hand_landmarks[0]
                    world_landmarks = results.multi_hand_world_landmarks[0] if results.multi_hand_world_landmarks else None

                    # 5. 手势解析
                    features = self.parser.extract_features(hand_landmarks, world_landmarks)

                    if features:
                        self.detection_count += 1

                        # 6. 发送特征数据
                        self.features_signal.emit(features)

                        # 7. 在图像上绘制地标（用于显示）
                        frame_with_landmarks = self.detector.draw_landmarks(frame, hand_landmarks)

                        # 8. 发送带地标的视频帧
                        self.video_frame_signal.emit(frame_with_landmarks)

                        # 9. 发送调试信息
                        debug_info = {
                            'camera_connected': True,
                            'detection_rate': self.parser.get_parse_count() / max(self.frame_count, 1),
                            'features': features,
                            'log_message': f"检测到手势，夹爪距离: {features['grip_distance']:.3f}m"
                        }
                        self.debug_signal.emit(debug_info)

                else:
                    # 未检测到手势
                    debug_info = {
                        'camera_connected': True,
                        'detection_rate': self.parser.get_parse_count() / max(self.frame_count, 1),
                        'log_message': "未检测到手势"
                    }
                    self.debug_signal.emit(debug_info)

                self.frame_count += 1

                # 控制处理频率
                time.sleep(0.01)  # ~100Hz

            except Exception as e:
                print(f"[VisionThread] 处理错误: {e}")
                time.sleep(0.1)

    def stop(self):
        """停止处理"""
        self.running = False
        print("[VisionThread] 正在停止...")

        # 释放资源
        if self.capture:
            self.capture.release()

        if self.detector:
            self.detector.release()

        print("[VisionThread] 已停止")

    def pause(self):
        """暂停处理"""
        self.paused = True
        print("[VisionThread] 已暂停")

    def resume(self):
        """恢复处理"""
        self.paused = False
        print("[VisionThread] 已恢复")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        elapsed = time.time() - self.start_time
        fps = self.frame_count / max(elapsed, 0.001)
        detection_rate = self.detection_count / max(self.frame_count, 1)

        return {
            'fps': fps,
            'frame_count': self.frame_count,
            'detection_count': self.detection_count,
            'detection_rate': detection_rate,
            'running': self.running,
            'paused': self.paused,
        }


class ControlThread(QObject):
    """控制处理线程"""

    # 信号定义
    command_ready_signal = Signal(object)  # 指令字节信号
    debug_signal = Signal(object)          # 调试信息信号

    def __init__(self, config_dict: Dict):
        super().__init__()

        # 配置
        self.filter_config = config_dict.get('FILTER_CONFIG', {})
        self.mapping_config = config_dict.get('MAPPING_CONFIG', {})
        self.safety_config = config_dict.get('SAFETY_CONFIG', {})

        # 模块初始化
        self.mapper = None
        self.filter = None

        # 状态变量
        self.running = False
        self.features_queue = queue.Queue(maxsize=10)

        # 统计信息
        self.process_count = 0
        self.send_count = 0

    def initialize(self) -> bool:
        """初始化控制模块"""
        try:
            print("[ControlThread] 初始化控制模块...")

            # 初始化映射引擎
            self.mapper = MappingEngine(self.mapping_config)

            # 初始化滤波控制器
            self.filter = FilterController(
                alpha=self.filter_config.get('alpha', 0.4),
                dead_zone=self.filter_config.get('dead_zone', 15),
                min_pwm=self.safety_config.get('min_pwm', 500),
                max_pwm=self.safety_config.get('max_pwm', 2500)
            )

            print("[ControlThread] 控制模块初始化完成")
            return True

        except Exception as e:
            print(f"[ControlThread] 初始化失败: {e}")
            return False

    def start_processing(self):
        """开始处理循环"""
        self.running = True

        print("[ControlThread] 开始控制处理...")

        while self.running:
            try:
                # 从队列获取特征数据（阻塞，最多1秒）
                features = self.features_queue.get(timeout=1.0)

                if features is None:
                    continue

                # 1. 特征映射到PWM
                raw_pwms = self.mapper.map_features(features)

                # 2. 滤波处理
                filtered_pwms = self.filter.apply_filter(raw_pwms)

                # 3. 死区判断
                if self.filter.should_send(filtered_pwms):
                    # 4. 打包指令
                    command_bytes = self.filter.pack_command(filtered_pwms)

                    # 5. 发送指令
                    self.command_ready_signal.emit(command_bytes)

                    # 6. 更新发送状态
                    self.filter.update_last_sent(filtered_pwms)

                    self.send_count += 1

                    # 7. 发送调试信息
                    debug_info = {
                        'filter_alpha': self.filter.alpha,
                        'deadzone': self.filter.dead_zone,
                        'pwms': filtered_pwms,
                        'log_message': f"发送指令 #{self.send_count}"
                    }
                    self.debug_signal.emit(debug_info)

                self.process_count += 1

                # 控制处理频率
                time.sleep(0.01)  # ~100Hz

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"[ControlThread] 处理错误: {e}")
                time.sleep(0.1)

    def stop(self):
        """停止处理"""
        self.running = False
        print("[ControlThread] 正在停止...")

        # 发送安全位置指令
        safe_pwms = self.filter._get_default_pwms()
        command_bytes = self.filter.pack_command(safe_pwms)
        self.command_ready_signal.emit(command_bytes)

        print("[ControlThread] 已停止，发送安全位置指令")

    def add_features(self, features: Dict):
        """添加特征数据到队列"""
        try:
            self.features_queue.put_nowait(features)
        except queue.Full:
            # 队列已满，丢弃最旧的数据
            try:
                self.features_queue.get_nowait()  # 丢弃一个
                self.features_queue.put_nowait(features)  # 添加新的
            except:
                pass

    def get_stats(self) -> Dict:
        """获取统计信息"""
        filter_stats = self.filter.get_stats() if self.filter else {}

        return {
            'process_count': self.process_count,
            'send_count': self.send_count,
            'queue_size': self.features_queue.qsize(),
            **filter_stats
        }


class MainController(QObject):
    """主控制器，协调所有线程和模块"""

    def __init__(self):
        super().__init__()

        # 配置
        self.config_dict = self._load_config()

        # 模块初始化
        self.vision_thread_obj = None
        self.control_thread_obj = None
        self.arm_communicator = None
        self.main_window = None

        # 线程
        self.vision_thread = None
        self.control_thread = None

        # 状态变量
        self.arm_connected = False

    def _load_config(self) -> Dict:
        """加载配置"""
        config_dict = {}

        # 从config.py导入所有大写变量
        import config as cfg
        for key in dir(cfg):
            if key.isupper():
                config_dict[key] = getattr(cfg, key)

        return config_dict

    def initialize(self) -> bool:
        """初始化所有模块"""
        try:
            print("=" * 60)
            print("基于视觉伺服的手势控制机械臂系统")
            print("版本: 1.0")
            print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)

            # 1. 初始化机械臂通信
            print("\n[1/4] 初始化机械臂通信...")
            serial_config = self.config_dict.get('SERIAL_CONFIG', {})
            self.arm_communicator = ArmCommunicator(
                port=serial_config.get('port', 'COM3'),
                baudrate=serial_config.get('baudrate', 115200),
                restart_buffer=serial_config.get('restart_buffer', 4.0)
            )

            # 列出可用串口
            ports = ArmCommunicator.list_available_ports()
            print(f"可用串口: {[p['device'] for p in ports]}")

            # 2. 初始化视觉线程
            print("\n[2/4] 初始化视觉线程...")
            self.vision_thread_obj = VisionThread(self.config_dict)
            if not self.vision_thread_obj.initialize():
                print("视觉线程初始化失败")
                return False

            # 3. 初始化控制线程
            print("\n[3/4] 初始化控制线程...")
            self.control_thread_obj = ControlThread(self.config_dict)
            if not self.control_thread_obj.initialize():
                print("控制线程初始化失败")
                return False

            # 4. 初始化主窗口
            print("\n[4/4] 初始化主窗口...")
            self.main_window = MainWindow(self.config_dict.get('UI_CONFIG', {}))

            # 连接信号和槽
            self._connect_signals()

            print("\n" + "=" * 60)
            print("所有模块初始化完成")
            print("=" * 60)

            return True

        except Exception as e:
            print(f"\n初始化失败: {e}")
            return False

    def _connect_signals(self):
        """连接信号和槽"""
        # 视觉线程信号
        self.vision_thread_obj.video_frame_signal.connect(
            self.main_window.update_video_frame
        )
        self.vision_thread_obj.debug_signal.connect(
            self.main_window.update_debug_data
        )
        self.vision_thread_obj.features_signal.connect(
            self.control_thread_obj.add_features
        )

        # 控制线程信号
        self.control_thread_obj.command_ready_signal.connect(
            self._on_command_ready
        )
        self.control_thread_obj.debug_signal.connect(
            self.main_window.update_debug_data
        )

        # 主窗口信号
        self.main_window.emergency_stop_signal.connect(
            self._on_emergency_stop
        )
        self.main_window.connect_arm_signal.connect(
            self._on_connect_arm
        )
        self.main_window.disconnect_arm_signal.connect(
            self._on_disconnect_arm
        )

        # 定时器更新统计信息
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # 每秒更新一次

    def start(self):
        """启动系统"""
        print("\n启动系统...")

        # 启动视觉线程
        self.vision_thread = threading.Thread(
            target=self.vision_thread_obj.start_processing,
            daemon=True
        )
        self.vision_thread.start()

        # 启动控制线程
        self.control_thread = threading.Thread(
            target=self.control_thread_obj.start_processing,
            daemon=True
        )
        self.control_thread.start()

        print("系统已启动")

    def stop(self):
        """停止系统"""
        print("\n停止系统...")

        # 停止视觉线程
        if self.vision_thread_obj:
            self.vision_thread_obj.stop()

        # 停止控制线程
        if self.control_thread_obj:
            self.control_thread_obj.stop()

        # 断开机械臂连接
        if self.arm_communicator and self.arm_connected:
            self.arm_communicator.close()
            self.arm_connected = False

        # 停止定时器
        if hasattr(self, 'stats_timer'):
            self.stats_timer.stop()

        print("系统已停止")

    def _on_command_ready(self, command_bytes):
        """处理准备好的指令"""
        if self.arm_communicator and self.arm_connected:
            success = self.arm_communicator.send_command(command_bytes)

            if not success:
                # 发送失败，更新状态
                self.arm_connected = False
                debug_info = {
                    'arm_connected': False,
                    'log_message': "指令发送失败，机械臂可能已断开连接"
                }
                self.main_window.update_debug_data(debug_info)

    def _on_emergency_stop(self):
        """处理急停"""
        print("急停触发!")

        # 发送急停指令
        if self.arm_communicator:
            self.arm_communicator.emergency_stop()

        # 暂停视觉处理
        if self.vision_thread_obj:
            self.vision_thread_obj.pause()

        # 更新UI状态
        debug_info = {
            'log_message': "急停已触发，系统暂停"
        }
        self.main_window.update_debug_data(debug_info)

    def _on_connect_arm(self):
        """连接机械臂"""
        if self.arm_connected:
            print("机械臂已连接")
            return

        print("正在连接机械臂...")

        if self.arm_communicator.open():
            self.arm_connected = True
            print("机械臂连接成功")

            # 更新UI状态
            debug_info = {
                'arm_connected': True,
                'log_message': "机械臂连接成功"
            }
            self.main_window.update_debug_data(debug_info)
        else:
            print("机械臂连接失败")
            debug_info = {
                'arm_connected': False,
                'log_message': "机械臂连接失败，请检查串口连接"
            }
            self.main_window.update_debug_data(debug_info)

    def _on_disconnect_arm(self):
        """断开机械臂连接"""
        if not self.arm_connected:
            print("机械臂未连接")
            return

        print("正在断开机械臂连接...")

        self.arm_communicator.close()
        self.arm_connected = False

        # 更新UI状态
        debug_info = {
            'arm_connected': False,
            'log_message': "机械臂已断开连接"
        }
        self.main_window.update_debug_data(debug_info)

        print("机械臂已断开连接")

    def _update_stats(self):
        """更新统计信息"""
        try:
            # 收集所有统计信息
            stats = {
                'arm_connected': self.arm_connected,
            }

            # 视觉线程统计
            if self.vision_thread_obj:
                vision_stats = self.vision_thread_obj.get_stats()
                stats.update({
                    'fps': vision_stats.get('fps', 0.0),
                    'detection_rate': vision_stats.get('detection_rate', 0.0),
                    'camera_connected': vision_stats.get('running', False) and not vision_stats.get('paused', False),
                })

            # 控制线程统计
            if self.control_thread_obj:
                control_stats = self.control_thread_obj.get_stats()
                stats.update({
                    'send_count': control_stats.get('send_count', 0),
                    'queue_size': control_stats.get('queue_size', 0),
                })

            # 机械臂通信统计
            if self.arm_communicator:
                arm_stats = self.arm_communicator.get_stats()
                stats.update({
                    'port': arm_stats.get('port', 'N/A'),
                    'buffer_remaining': arm_stats.get('buffer_remaining', 0.0),
                })

            # 更新UI
            self.main_window.update_debug_data(stats)

        except Exception as e:
            print(f"[MainController] 更新统计信息时出错: {e}")

    def run(self):
        """运行主循环"""
        try:
            # 显示主窗口
            self.main_window.show()

            # 启动系统
            self.start()

            print("\n系统正在运行...")
            print("按 Ctrl+C 退出")

            # 进入Qt事件循环
            return True

        except Exception as e:
            print(f"运行错误: {e}")
            return False


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 创建主控制器
    controller = MainController()

    # 初始化
    if not controller.initialize():
        print("初始化失败，程序退出")
        return 1

    # 运行
    if not controller.run():
        print("运行失败，程序退出")
        return 1

    # 设置退出处理
    def shutdown():
        print("\n正在关闭程序...")
        controller.stop()
        print("程序已关闭")

    import atexit
    atexit.register(shutdown)

    # 执行应用
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\n接收到中断信号")
        shutdown()
        return 0


if __name__ == "__main__":
    main()