#!/usr/bin/env python3
"""
系统测试脚本
测试核心模块功能（不包括UI）
"""

import sys
import time
import numpy as np

print("=" * 60)
print("基于视觉伺服的手势控制机械臂系统 - 功能测试")
print("=" * 60)

# 测试1: 导入模块
print("\n[1/6] 测试模块导入...")

try:
    import config
    print("✓ config 导入成功")
except Exception as e:
    print(f"✗ config 导入失败: {e}")
    sys.exit(1)

modules_to_test = [
    ('modules.vision_capture', 'VisionCapture'),
    ('modules.hand_detector', 'HandDetector'),
    ('modules.gesture_parser', 'GestureParser'),
    ('modules.mapping', 'MappingEngine'),
    ('modules.filter_control', 'FilterController'),
    ('modules.arm_communicator', 'ArmCommunicator'),
]

for module_name, class_name in modules_to_test:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✓ {module_name}.{class_name} 导入成功")
    except ImportError as e:
        print(f"✗ {module_name} 导入失败: {e}")
        print(f"  请确保已安装依赖: pip install opencv-python mediapipe pyserial numpy")
        sys.exit(1)
    except AttributeError as e:
        print(f"✗ {module_name} 中找不到 {class_name}: {e}")
        sys.exit(1)

print("✓ 所有模块导入成功")

# 测试2: 配置加载
print("\n[2/6] 测试配置加载...")
try:
    from config import CAMERA_CONFIG, HAND_DETECTOR_CONFIG, SERIAL_CONFIG, FILTER_CONFIG, MAPPING_CONFIG
    print("✓ 配置加载成功")
    print(f"  摄像头配置: {CAMERA_CONFIG}")
    print(f"  手势检测配置: {HAND_DETECTOR_CONFIG}")
except Exception as e:
    print(f"✗ 配置加载失败: {e}")
    sys.exit(1)

# 测试3: 手势解析和映射逻辑
print("\n[3/6] 测试手势解析和映射逻辑...")
try:
    from modules.gesture_parser import GestureParser
    from modules.mapping import MappingEngine
    from modules.filter_control import FilterController

    # 创建测试对象
    parser = GestureParser(image_width=1280, image_height=720)
    mapper = MappingEngine()
    filter_ctrl = FilterController(alpha=0.4, dead_zone=15)

    # 测试特征
    test_features = {
        'grip_distance': 0.2,
        'wrist_pitch': 0.0,
        'wrist_roll': 0.0,
        'hand_x': 0.0,
        'hand_y': 0.0,
        'hand_z': 0.5,
    }

    # 测试映射
    pwms = mapper.map_features(test_features)
    print(f"✓ 映射测试成功")
    print(f"  输入特征: {test_features}")
    print(f"  输出PWM: {pwms}")

    # 测试滤波
    filtered = filter_ctrl.apply_filter(pwms)
    should_send = filter_ctrl.should_send(filtered)
    print(f"  滤波后PWM: {filtered}")
    print(f"  是否需要发送: {should_send}")

    # 测试指令打包
    command = filter_ctrl.pack_command(filtered)
    print(f"  指令长度: {len(command)} 字节")

except Exception as e:
    print(f"✗ 手势解析和映射测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: 机械臂通信模块（模拟）
print("\n[4/6] 测试机械臂通信模块（模拟）...")
try:
    from modules.arm_communicator import ArmCommunicator

    # 列出可用串口
    ports = ArmCommunicator.list_available_ports()
    print(f"  可用串口: {[p['device'] for p in ports]}")

    # 创建通信对象（不实际打开串口）
    communicator = ArmCommunicator(port='COM3', baudrate=115200, restart_buffer=2.0)
    print(f"✓ 通信模块初始化成功")

    # 测试缓冲逻辑
    print(f"  初始状态 - 是否可以发送: {communicator.is_ready()}")

except Exception as e:
    print(f"✗ 机械臂通信模块测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试5: 视觉采集模块（如果摄像头可用）
print("\n[5/6] 测试视觉采集模块（模拟）...")
try:
    from modules.vision_capture import VisionCapture

    # 创建采集对象
    capture = VisionCapture(camera_id=0, flip_horizontal=True, width=640, height=480)

    # 尝试打开摄像头（如果可用）
    if capture.open():
        print("✓ 摄像头打开成功")

        # 尝试读取一帧
        success, frame = capture.read_frame()
        if success:
            print(f"  帧读取成功: {frame.shape}")
        else:
            print("  帧读取失败（可能摄像头被占用）")

        capture.release()
    else:
        print("⚠ 摄像头不可用（跳过实际测试）")

except Exception as e:
    print(f"⚠ 视觉采集模块测试警告: {e}")
    print("  这可能是因为摄像头不可用或权限问题")

# 测试6: 手势检测模块（模拟）
print("\n[6/6] 测试手势检测模块（模拟）...")
try:
    from modules.hand_detector import HandDetector

    # 创建检测器
    detector = HandDetector(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    print("✓ 手势检测模块初始化成功")

    # 创建测试图像
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # 转换为RGB
    rgb_image = test_image[:, :, ::-1]

    # 处理图像（模拟）
    results = detector.process(rgb_image)
    print(f"  处理结果: {'有手势' if results and results.multi_hand_landmarks else '无手势'}")

    detector.release()

except Exception as e:
    print(f"⚠ 手势检测模块测试警告: {e}")
    print("  这可能是因为mediapipe模型未加载或其他问题")

print("\n" + "=" * 60)
print("功能测试完成!")
print("=" * 60)

print("\n下一步:")
print("1. 安装UI依赖: pip install PySide6")
print("2. 运行完整系统: python main.py")
print("3. 或运行纯视觉测试: python main_vision_control.py")

# 检查缺失的依赖
print("\n检查依赖...")
try:
    import PySide6
    print("✓ PySide6 已安装")
except ImportError:
    print("✗ PySide6 未安装，UI将无法运行")

try:
    import cv2
    print("✓ OpenCV 已安装")
except ImportError:
    print("✗ OpenCV 未安装")

try:
    import mediapipe
    print("✓ MediaPipe 已安装")
except ImportError:
    print("✗ MediaPipe 未安装")

try:
    import serial
    print("✓ PySerial 已安装")
except ImportError:
    print("✗ PySerial 未安装")

print("\n测试完成!")