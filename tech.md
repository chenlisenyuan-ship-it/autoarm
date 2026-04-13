# 技术架构文档 (tech.md)

## 1. 项目概述

**项目名称**：基于视觉伺服的手势控制机械臂系统  
**核心目标**：通过普通 USB 摄像头捕捉操作者手部姿态，实时解析为机械臂关节控制指令，实现“手怎么动，机械臂就怎么动”的自然交互。  
**应用场景**：教育演示、远程操作、康复辅助、智能家居。

**系统特点**：
- **纯视觉输入**：无需穿戴设备，单目摄像头即可工作。
- **低延迟控制**：视觉处理 + 滤波 + 串口通信全链路 < 100ms。
- **安全可靠**：软件死区、指令限幅、硬件重启缓冲等多重保护。
- **现代 UI**：深色主题、实时视频、调试信息流，便于监控与调试。

## 2. 技术栈与依赖

### 2.1 运行环境
- **操作系统**：Windows 10/11（已测试）
- **Python 版本**：3.10（推荐使用 Conda 环境 `pyarm`）
- **包管理**：`pip`（国内镜像可配置清华源）

### 2.2 核心库
| 库名 | 版本 | 用途 |
|------|------|------|
| `opencv-python` | 4.8.x | 视频采集、图像渲染、色彩转换 |
| `mediapipe` | 0.10.9 | 手部关键点检测（3D 坐标） |
| `PySide6` | 6.5.x | 现代 GUI 框架，提供深色卡片布局 |
| `pyserial` | 3.5.x | 串口通信，控制机械臂 |
| `numpy` | 1.24.x | 数值计算、线性插值、限幅 |

### 2.3 硬件清单
| 设备 | 型号/规格 | 接口 | 备注 |
|------|-----------|------|------|
| 机械臂 | 幻尔（Hiwonder）LOBOT 6DOF | USB‑转‑TTL（ESP32） | PWM 舵机控制，支持串口指令 |
| 摄像头 | 普通 USB 摄像头（720P/1080P） | USB 2.0/3.0 | 帧率 ≥ 30fps |
| 主机 | 普通 PC 或笔记本 | USB ×2 | 需同时连接摄像头与机械臂 |

## 3. 系统架构

### 3.1 逻辑分层
```
┌─────────────────────────────────────────────────────────┐
│                   应用层 (Application)                   │
├──────────────┬──────────────┬──────────────┬────────────┤
│   视觉处理   │  手势解析     │  控制滤波    │   UI 渲染  │
│   (Vision)   │  (Gesture)   │  (Control)   │   (GUI)    │
├──────────────┼──────────────┼──────────────┼────────────┤
│              │              │              │            │
│  OpenCV      │  MediaPipe   │   EMA滤波    │  PySide6   │
│  采集/渲染   │  手部地标     │  死区检查    │  窗口/布局 │
│              │              │  指令打包    │            │
└──────────────┴──────────────┴──────────────┴────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   串口通信层       │
                    │   (Serial Comm)   │
                    │  struct 封包      │
                    │  小端序，CRC可选   │
                    └─────────▲─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   硬件层 (HW)      │
                    │  机械臂（ESP32）   │
                    │  6DOF 舵机        │
                    └───────────────────┘
```

### 3.2 数据流
```
摄像头帧 → OpenCV → MediaPipe → 手势解析 → 映射 → 滤波 → 死区判断 → 封包 → 串口 → 机械臂
              │                                         │
              └─────────→ UI 视频渲染 ←─── 调试信息 ←────┘
```

### 3.3 线程模型
- **主线程**：PySide6 事件循环，负责 UI 更新与用户交互。
- **视觉线程**：持续抓取摄像头帧，调用 MediaPipe 推理，计算手势特征。
- **控制线程**：接收手势特征，进行映射、滤波、死区判断，并通过串口发送指令。
- **通信线程**（可选）：专门负责串口写入，避免阻塞控制逻辑。

> 注意：线程间通过信号/槽（PySide6）或线程安全队列（`queue.Queue`）传递数据。

## 4. 模块详细设计

### 4.1 视觉采集模块 (`vision_capture.py`)
**职责**：打开摄像头、读取帧、预处理（翻转、色彩转换）。

**接口**：
```python
class VisionCapture:
    def __init__(self, camera_id=0, flip_horizontal=True):
        """
        :param camera_id: 摄像头设备 ID（0 为默认）
        :param flip_horizontal: 是否水平翻转图像（镜像显示）
        """
        
    def read_frame(self):
        """
        读取一帧图像。
        :return: (success, frame) 
                 success: bool，是否读取成功
                 frame: numpy.ndarray (H, W, 3) BGR 格式
        """
        
    def release(self):
        """释放摄像头资源"""
```

### 4.2 手势检测模块 (`hand_detector.py`)
**职责**：调用 MediaPipe Hands 模型，获取手部 3D 地标坐标。

**接口**：
```python
class HandDetector:
    def __init__(self, static_image_mode=False, max_num_hands=1,
                 min_detection_confidence=0.7, min_tracking_confidence=0.7):
        """
        参数与 mediapipe.solutions.hands.Hands 一致。
        """
        
    def process(self, rgb_image):
        """
        处理一帧 RGB 图像。
        :param rgb_image: numpy.ndarray (H, W, 3) RGB 格式
        :return: results 对象（mediapipe 格式），包含 multi_hand_landmarks 等属性
        """
        
    def draw_landmarks(self, image, hand_landmarks):
        """
        在图像上绘制手部地标与连接线（用于调试）。
        :param image: BGR 图像
        :param hand_landmarks: 单个手的地标列表
        :return: 绘制后的图像
        """
```

### 4.3 手势解析模块 (`gesture_parser.py`)
**职责**：从 MediaPipe 结果中提取关键特征：
1. **夹爪开合**：拇指尖（4）与食指尖（8）的 3D 欧氏距离。
2. **手腕姿态**：
   - **Pitch（俯仰）**：手腕（0）与中指根（9）在 Y‑Z 平面上的夹角。
   - **Roll（翻滚）**：手腕（0）与食指根（5）在 X‑Z 平面上的夹角。
3. **手部位置**：手腕（0）的 3D 坐标（x, y, z）相对于图像中心的归一化偏移。

**接口**：
```python
class GestureParser:
    def __init__(self, image_width, image_height):
        """
        :param image_width: 图像宽度（像素）
        :param image_height: 图像高度（像素）
        """
        
    def extract_features(self, hand_landmarks):
        """
        提取手势特征。
        :param hand_landmarks: 单个手的 21 个地标（mediapipe 格式）
        :return: dict {
            'grip_distance': float,  # 拇指‑食指距离（归一化 [0, 1]）
            'wrist_pitch': float,    # 手腕俯仰角（弧度，范围 [-π/2, π/2]）
            'wrist_roll': float,     # 手腕翻滚角（弧度，范围 [-π/2, π/2]）
            'hand_x': float,         # 手部水平位置（归一化 [-1, 1]，0 为图像中心）
            'hand_y': float,         # 手部垂直位置（归一化 [-1, 1]，0 为图像中心）
            'hand_z': float,         # 手部深度（归一化 [0, 1]，0 最近，1 最远）
        }
        """
```

### 4.4 映射模块 (`mapping.py`)
**职责**：将手势特征映射为机械臂关节的 PWM 值（或角度）。所有映射均采用线性插值，并经过限幅保护。

**映射规则**：

| 手势特征 | 机械臂关节 | 映射范围（输入→输出） | 备注 |
|----------|------------|----------------------|------|
| 夹爪距离 | 夹爪舵机（ID=5） | [0.030, 0.407] → PWM [1500, 600] | 距离越小（手指捏合）→ PWM 越小（夹爪闭合） |
| 手腕 Pitch | 近端关节（ID=2） | [-π/2, π/2] → PWM [500, 2500] | 俯仰角正负对应关节正反转 |
| 手腕 Roll | 夹爪旋转（ID=6） | [-π/2, π/2] → PWM [500, 2500] | 翻滚角正负对应旋转方向 |
| 手部 X | 底座旋转（ID=1） | [-1, 1] → PWM [500, 2500] | 手向左/右移动 → 底座逆/顺时针 |
| 手部 Y | 大臂关节（ID=3） | [-1, 1] → PWM [500, 2500] | 手向上/下移动 → 大臂抬升/下降 |
| 手部 Z | 小臂关节（ID=4） | [0, 1] → PWM [500, 2500] | 手远离/靠近摄像头 → 小臂伸展/收回 |

**接口**：
```python
class MappingEngine:
    def __init__(self):
        # 定义各关节的输入范围与输出范围
        self.mapping_config = {
            'grip': {'input_range': (0.030, 0.407), 'output_range': (1500, 600)},
            'pitch': {'input_range': (-1.57, 1.57), 'output_range': (500, 2500)},
            'roll': {'input_range': (-1.57, 1.57), 'output_range': (500, 2500)},
            'x': {'input_range': (-1, 1), 'output_range': (500, 2500)},
            'y': {'input_range': (-1, 1), 'output_range': (500, 2500)},
            'z': {'input_range': (0, 1), 'output_range': (500, 2500)},
        }
        
    def map_features(self, features):
        """
        将手势特征字典映射为 6 个关节的 PWM 值。
        :param features: GestureParser 输出的特征字典
        :return: dict {
            'joint_1': int,  # 底座旋转
            'joint_2': int,  # 近端关节（pitch）
            'joint_3': int,  # 大臂
            'joint_4': int,  # 小臂
            'joint_5': int,  # 夹爪开合
            'joint_6': int,  # 夹爪旋转（roll）
        }
        """
        # 使用 np.interp 线性插值，再用 np.clip 限制在 [500, 2500]
```

### 4.5 滤波与控制模块 (`filter_control.py`)
**职责**：
1. **EMA 滤波**：对每个关节的 PWM 值进行一阶低通滤波（Alpha = 0.4）。
2. **死区判断**：仅当滤波后的 PWM 与上一次下发值的差值 > 15 时才触发下发。
3. **指令打包**：将 6 个 PWM 值按小端序打包为二进制帧。
4. **安全限幅**：确保 PWM 值在机械臂允许范围内（[500, 2500]）。

**接口**：
```python
class FilterController:
    def __init__(self, alpha=0.4, dead_zone=15):
        """
        :param alpha: EMA 滤波系数（0~1），越小滤波越强
        :param dead_zone: 死区阈值，避免微小波动导致频繁下发
        """
        self.alpha = alpha
        self.dead_zone = dead_zone
        self.last_pwms = None  # 上一帧的 PWM 字典
        self.filtered_pwms = None  # 滤波后的 PWM 字典
        
    def apply_filter(self, new_pwms):
        """
        对新的 PWM 字典进行 EMA 滤波。
        :param new_pwms: MappingEngine 输出的 PWM 字典
        :return: 滤波后的 PWM 字典
        """
        # 若 last_pwms 为空，直接使用 new_pwms
        # 否则：filtered = alpha * new + (1 - alpha) * last
        
    def should_send(self, filtered_pwms):
        """
        判断是否需要下发指令（死区检查）。
        :param filtered_pwms: 滤波后的 PWM 字典
        :return: bool
        """
        # 比较 filtered_pwms 与 last_pwms 的每个关节差值
        # 任一关节差值 > dead_zone 则返回 True
        
    def pack_command(self, pwms):
        """
        将 PWM 字典打包为二进制帧。
        帧格式：<头 0x55 0xAA> <ID1> <PWM低字节> <PWM高字节> … <ID6> <PWM低字节> <PWM高字节> <校验和>
        :param pwms: 关节 PWM 字典
        :return: bytes 对象（长度 = 2 + 6*3 + 1 = 21 字节）
        """
        import struct
        # 使用 struct.pack('<BBH', id, pwm_low, pwm_high) 打包每个关节
        # 校验和 = sum(所有字节) % 256
        
    def update_last(self, pwms):
        """更新上一次下发的 PWM 值（仅在指令实际发送后调用）"""
```

### 4.6 机械臂通信模块 (`arm_communicator.py`)
**职责**：
1. 打开/关闭串口。
2. 发送打包后的二进制指令。
3. 实现硬件重启缓冲（发送指令后等待 4 秒，确保机械臂完成动作并稳定）。

**接口**：
```python
class ArmCommunicator:
    def __init__(self, port='COM3', baudrate=115200, restart_buffer=4.0):
        """
        :param port: 串口号（Windows 为 COM3、COM4 等）
        :param baudrate: 波特率（与 ESP32 固件一致）
        :param restart_buffer: 硬件重启缓冲时间（秒）
        """
        
    def open(self):
        """打开串口"""
        
    def close(self):
        """关闭串口"""
        
    def send_command(self, command_bytes):
        """
        发送指令，并启动重启缓冲计时。
        :param command_bytes: FilterController.pack_command() 返回的字节串
        :return: bool 是否发送成功
        """
        # 若距离上次发送不足 restart_buffer 秒，则跳过此次发送（保护硬件）
        # 否则写入串口，并记录发送时间
        
    def is_ready(self):
        """
        检查是否已过重启缓冲时间。
        :return: bool 是否可以发送下一条指令
        """
```

### 4.7 UI 界面模块 (`main_window.py`)
**职责**：提供深色现代风格的图形界面，实时显示摄像头画面与调试信息。

**界面布局**：
- **整体风格**：深色背景 `#1E222A`，圆角卡片，白色文字。
- **左侧栏（30%）**：调试信息流，使用 `QTextEdit` 或 `QLabel` 滚动显示。
  - 系统状态（摄像头、串口、机械臂连接状态）
  - 实时 FPS（视觉处理帧率）
  - 手势特征值（夹爪距离、手腕角度、手部位置）
  - 映射后的 PWM 值
  - 下发指令日志
- **右侧栏（70%）**：视频渲染区，使用 `QLabel` 显示 OpenCV 图像（需转换为 QPixmap）。

**接口**：
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化 UI 组件
        
    def update_video_frame(self, frame):
        """
        更新右侧视频区的图像。
        :param frame: numpy.ndarray (H, W, 3) BGR 格式
        """
        # 将 BGR 转换为 RGB，再转换为 QImage → QPixmap，最后设置给 QLabel
        
    def update_debug_data(self, data_dict):
        """
        更新左侧调试信息。
        :param data_dict: dict 包含以下键值（示例）：
            {
                'fps': 30.5,
                'grip_distance': 0.12,
                'wrist_pitch': 0.34,
                'wrist_roll': -0.21,
                'hand_x': 0.05,
                'hand_y': -0.12,
                'hand_z': 0.45,
                'pwms': [1500, 1200, 1800, 2000, 800, 2100],
                'arm_connected': True,
                'last_command': '2023‑10‑01 12:34:56 → 下发 PWM [1500, 1200, ...]'
            }
        """
        # 格式化字符串，追加到调试信息流中（可设置最大行数防内存溢出）
        
    def closeEvent(self, event):
        """窗口关闭时释放资源"""
```

## 5. 接口定义与数据流

### 5.1 视觉线程 → UI 线程
- **视频帧**：通过信号/槽 `update_video_frame` 传递（需转换为 QPixmap）。
- **调试数据**：通过信号/槽 `update_debug_data` 传递（字典格式）。

### 5.2 手势解析 → 控制线程
- **特征字典**：通过线程安全队列 `queue.Queue` 传递。

### 5.3 控制线程 → 通信线程
- **打包指令**：通过队列传递 bytes 对象。

### 5.4 全局状态管理
使用一个共享的 `GlobalState` 类（线程安全）记录：
- 摄像头连接状态
- 串口连接状态
- 机械臂就绪状态
- 当前手势特征
- 当前 PWM 值
- 最后下发时间

## 6. 错误处理与安全机制

### 6.1 视觉层
- 摄像头断开时尝试重连（最多 3 次）。
- MediaPipe 检测失败时使用上一帧特征（短期记忆）。

### 6.2 控制层
- **PWM 限幅**：所有映射输出均经过 `np.clip(pwm, 500, 2500)`。
- **死区过滤**：差值 ≤ 15 的微小变化不触发下发。
- **EMA 滤波**：Alpha = 0.4，平滑突变信号。

### 6.3 通信层
- **串口断连**：自动重试，并在 UI 显示警告。
- **硬件重启缓冲**：发送指令后锁定 4 秒，防止高频指令冲击舵机。
- **校验和**：每个指令帧包含校验和，机械臂端可验证完整性。

### 6.4 用户安全
- **急停按钮**：UI 上提供红色急停按钮，按下后立即停止所有指令下发。
- **手势退出**：持续 3 秒握拳（五指捏合）触发系统软停止。

## 7. 部署与运行指南

### 7.1 环境搭建
```bash
# 1. 创建 Conda 环境
conda create -n pyarm python=3.10
conda activate pyarm

# 2. 安装依赖
pip install opencv-python mediapipe==0.10.9 PySide6 pyserial numpy

# 3. 克隆代码（假设已有仓库）
git clone <repo_url>
cd arm
```

### 7.2 硬件连接
1. 将 USB 摄像头插入主机。
2. 使用 USB‑转‑TTL 线连接机械臂 ESP32 与主机。
3. 打开设备管理器，确认串口号（如 COM3）。
4. 为机械臂供电（注意电压与电流要求）。

### 7.3 配置文件
创建 `config.yaml`（或 `config.py`）：
```yaml
camera:
  id: 0
  flip: true
  
serial:
  port: COM3
  baudrate: 115200
  
filter:
  alpha: 0.4
  dead_zone: 15
  
mapping:
  grip_range: [0.030, 0.407]
  grip_pwm: [1500, 600]
  # ... 其他关节映射范围
  
ui:
  theme: dark
  update_interval_ms: 50  # UI 刷新间隔
```

### 7.4 启动顺序
```python
# main.py
import sys
from PySide6.QtWidgets import QApplication
from main_window import MainWindow
from vision_thread import VisionThread
from control_thread import ControlThread

app = QApplication(sys.argv)
window = MainWindow()

# 创建线程
vision_thread = VisionThread(camera_id=0)
control_thread = ControlThread(serial_port='COM3')

# 连接信号/槽
vision_thread.video_frame.connect(window.update_video_frame)
vision_thread.debug_data.connect(window.update_debug_data)
vision_thread.features.connect(control_thread.on_features)

control_thread.command_ready.connect(window.update_command_log)

# 启动线程
vision_thread.start()
control_thread.start()

window.show()
sys.exit(app.exec())
```

### 7.5 测试步骤
1. **纯视觉测试**：运行 `python test_vision.py`，确认手势检测正常。
2. **UI 测试**：运行 `python test_ui.py`，验证界面布局与更新。
3. **串口测试**：运行 `python test_serial.py`，发送固定 PWM 检查机械臂动作。
4. **集成测试**：启动完整系统，进行手势‑机械臂联动验证。

## 8. 性能指标与优化

### 8.1 关键指标
- **端到端延迟**：手势变化到机械臂动作 < 200ms（目标 < 100ms）。
- **视觉帧率**：≥ 30fps（720P 分辨率）。
- **CPU 占用**：< 50%（主流 i5/i7）。
- **内存占用**：< 500MB。

### 8.2 优化建议
- **图像降采样**：将摄像头分辨率从 1080P 降至 720P，提升 MediaPipe 推理速度。
- **线程优先级**：视觉线程设为高优先级，控制线程中优先级，UI 线程低优先级。
- **指令合并**：若多个关节同时变化，合并为一条指令帧发送。
- **动态滤波**：根据手势运动速度自适应调整 EMA 系数（快动时 α 增大，慢动时 α 减小）。

## 9. 扩展与未来工作

### 9.1 短期扩展
- **多手势模式**：握拳、五指张开、剪刀手等触发不同预设动作。
- **轨迹录制**：记录手势运动序列，可回放控制机械臂重复动作。
- **ROS 接口**：将手势解析结果发布为 ROS topic，与 ROS 控制的机械臂集成。

### 9.2 长期愿景
- **多摄像头融合**：使用双目摄像头提升深度估计精度。
- **机器学习优化**：收集数据训练专用手势‑关节映射模型，替代线性插值。
- **Web 控制界面**：将 UI 移植为 Web 应用，支持远程监控与控制。

---

**文档版本**：v1.0  
**最后更新**：2026‑04‑10  
**维护者**：Claude Code  

> 本文档描述的技术方案已通过可行性验证，所有选型均为最简单成熟的组合，可直接交付 AI 编程工具生成实现代码。