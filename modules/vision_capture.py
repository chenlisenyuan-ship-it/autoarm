#!/usr/bin/env python3
"""
视觉采集模块
职责：打开摄像头、读取帧、预处理（翻转、色彩转换）
"""

import cv2
import time
from typing import Tuple, Optional
import numpy as np


class VisionCapture:
    """摄像头采集类"""

    def __init__(self, camera_id: int = 0, flip_horizontal: bool = True,
                 width: int = 1280, height: int = 720, fps: int = 30):
        """
        初始化摄像头

        :param camera_id: 摄像头设备ID（0为默认）
        :param flip_horizontal: 是否水平翻转图像（镜像显示）
        :param width: 图像宽度
        :param height: 图像高度
        :param fps: 帧率
        """
        self.camera_id = camera_id
        self.flip_horizontal = flip_horizontal
        self.width = width
        self.height = height
        self.fps = fps

        # 摄像头对象
        self.cap: Optional[cv2.VideoCapture] = None

        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_update = self.start_time
        self.current_fps = 0.0

        # 连接状态
        self.connected = False

    def open(self) -> bool:
        """
        打开摄像头

        :return: 是否成功打开
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_id)

            if not self.cap.isOpened():
                print(f"[VisionCapture] 无法打开摄像头 {self.camera_id}")
                return False

            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            # 验证实际设置的参数
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

            print(f"[VisionCapture] 摄像头 {self.camera_id} 已打开")
            print(f"  分辨率: {actual_width}x{actual_height}, 帧率: {actual_fps:.1f}")

            self.connected = True
            return True

        except Exception as e:
            print(f"[VisionCapture] 打开摄像头时出错: {e}")
            self.connected = False
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        读取一帧图像

        :return: (success, frame)
                 success: bool，是否读取成功
                 frame: numpy.ndarray (H, W, 3) BGR格式，失败时为None
        """
        if self.cap is None or not self.connected:
            return False, None

        try:
            success, frame = self.cap.read()

            if not success:
                print("[VisionCapture] 读取帧失败，尝试重新连接...")
                self.connected = False

                # 尝试重新连接（最多3次）
                for i in range(3):
                    self.release()
                    time.sleep(0.5)
                    if self.open():
                        success, frame = self.cap.read()
                        if success:
                            break

                if not success:
                    return False, None

            # 水平翻转（镜像显示）
            if self.flip_horizontal:
                frame = cv2.flip(frame, 1)

            # 更新FPS统计
            self.frame_count += 1
            current_time = time.time()

            # 每0.5秒更新一次FPS
            if current_time - self.last_fps_update >= 0.5:
                elapsed = current_time - self.last_fps_update
                self.current_fps = self.frame_count / elapsed
                self.frame_count = 0
                self.last_fps_update = current_time

            return True, frame

        except Exception as e:
            print(f"[VisionCapture] 读取帧时出错: {e}")
            self.connected = False
            return False, None

    def get_fps(self) -> float:
        """
        获取当前FPS

        :return: 当前帧率
        """
        return self.current_fps

    def is_connected(self) -> bool:
        """
        检查摄像头是否连接

        :return: 连接状态
        """
        return self.connected

    def release(self):
        """释放摄像头资源"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.connected = False
        print(f"[VisionCapture] 摄像头 {self.camera_id} 已释放")

    def __del__(self):
        """析构函数"""
        self.release()


# 测试函数
def test_vision_capture():
    """测试视觉采集模块"""
    print("测试视觉采集模块...")

    # 创建采集对象
    capture = VisionCapture(camera_id=0, flip_horizontal=True)

    # 打开摄像头
    if not capture.open():
        print("无法打开摄像头，退出测试")
        return

    print("摄像头已打开，按 'q' 键退出测试...")

    try:
        while True:
            # 读取帧
            success, frame = capture.read_frame()

            if not success:
                print("读取帧失败")
                break

            # 显示帧
            cv2.putText(frame, f"FPS: {capture.get_fps():.1f}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("VisionCapture Test", frame)

            # 检查退出键
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("测试被用户中断")

    finally:
        # 释放资源
        capture.release()
        cv2.destroyAllWindows()
        print("测试完成")


if __name__ == "__main__":
    test_vision_capture()