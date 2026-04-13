#!/usr/bin/env python3
"""
配置文件
"""

# 摄像头配置
CAMERA_CONFIG = {
    'id': 0,                # 摄像头设备ID（0为默认）
    'flip_horizontal': True,  # 是否水平翻转图像（镜像显示）
    'width': 1280,          # 图像宽度
    'height': 720,          # 图像高度（720P）
    'fps': 30,              # 帧率
}

# 手势检测配置
HAND_DETECTOR_CONFIG = {
    'static_image_mode': False,
    'max_num_hands': 1,
    'min_detection_confidence': 0.7,
    'min_tracking_confidence': 0.7,
}

# 串口配置（机械臂）
SERIAL_CONFIG = {
    'port': 'COM3',         # Windows串口号，Linux通常为 /dev/ttyUSB0
    'baudrate': 115200,     # 波特率
    'timeout': 1,           # 读取超时（秒）
    'restart_buffer': 4.0,  # 硬件重启缓冲时间（秒）
}

# 滤波与控制配置
FILTER_CONFIG = {
    'alpha': 0.4,           # EMA滤波系数（0~1），越小滤波越强
    'dead_zone': 15,        # 死区阈值，避免微小波动导致频繁下发
}

# 映射配置
MAPPING_CONFIG = {
    # 夹爪映射：距离 [min, max] -> PWM [open, close]
    'grip': {
        'input_range': (0.030, 0.407),  # 拇指与食指的3D距离（米）
        'output_range': (1500, 600),    # PWM值（1500=闭合，600=张开）
    },
    # 手腕俯仰（Pitch）映射：弧度 -> PWM
    'pitch': {
        'input_range': (-1.57, 1.57),   # 弧度，约±90度
        'output_range': (500, 2500),    # PWM范围
    },
    # 手腕翻滚（Roll）映射：弧度 -> PWM
    'roll': {
        'input_range': (-1.57, 1.57),   # 弧度，约±90度
        'output_range': (500, 2500),    # PWM范围
    },
    # 手部X位置映射：归一化[-1,1] -> PWM
    'x': {
        'input_range': (-1, 1),         # 归一化位置，-1左，1右
        'output_range': (500, 2500),    # PWM范围
    },
    # 手部Y位置映射：归一化[-1,1] -> PWM
    'y': {
        'input_range': (-1, 1),         # 归一化位置，-1下，1上
        'output_range': (500, 2500),    # PWM范围
    },
    # 手部Z位置（深度）映射：归一化[0,1] -> PWM
    'z': {
        'input_range': (0, 1),          # 归一化深度，0最近，1最远
        'output_range': (500, 2500),    # PWM范围
    },
}

# UI配置
UI_CONFIG = {
    'theme': 'dark',                    # 主题：dark/light
    'background_color': '#1E222A',      # 背景色（深色主题）
    'update_interval_ms': 50,           # UI刷新间隔（毫秒）
    'debug_max_lines': 1000,            # 调试信息最大行数
}

# 关节ID映射（根据LOBOT机械臂协议）
JOINT_IDS = {
    'base': 1,          # 底座旋转
    'shoulder': 2,      # 近端关节（肩部）
    'elbow': 3,         # 大臂关节（肘部）
    'wrist': 4,         # 小臂关节（腕部）
    'grip': 5,          # 夹爪开合
    'grip_rotate': 6,   # 夹爪旋转
}

# 安全配置
SAFETY_CONFIG = {
    'min_pwm': 500,     # 最小PWM值
    'max_pwm': 2500,    # 最大PWM值
    'emergency_stop_pwm': 1500,  # 急停时所有关节PWM值（中位）
    'gesture_exit_timeout': 3.0, # 握拳触发退出的持续时间（秒）
}

if __name__ == '__main__':
    print("配置文件加载成功")
    print(f"摄像头配置: {CAMERA_CONFIG}")
    print(f"串口配置: {SERIAL_CONFIG}")