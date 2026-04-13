#!/usr/bin/env python3
"""
手势检测模块
职责：调用 MediaPipe Hands 模型，获取手部 3D 地标坐标
"""

import cv2
import mediapipe as mp
from typing import Optional, List, Tuple, Any
import numpy as np


class HandDetector:
    """手势检测类"""

    def __init__(self,
                 static_image_mode: bool = False,
                 max_num_hands: int = 1,
                 min_detection_confidence: float = 0.7,
                 min_tracking_confidence: float = 0.7):
        """
        初始化 MediaPipe Hands 模型

        :param static_image_mode: 是否为静态图像模式
        :param max_num_hands: 最大检测手数
        :param min_detection_confidence: 最小检测置信度
        :param min_tracking_confidence: 最小跟踪置信度
        """
        # 初始化 MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils

        # 手势检测器
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        # 检测结果缓存
        self.last_results = None
        self.last_hand_landmarks = None
        self.last_world_landmarks = None

        # 统计信息
        self.detection_count = 0
        self.failed_count = 0

        print(f"[HandDetector] 初始化完成，最大手数: {max_num_hands}")

    def process(self, rgb_image: np.ndarray) -> Optional[mp.solutions.hands.Hands]:
        """
        处理一帧 RGB 图像

        :param rgb_image: numpy.ndarray (H, W, 3) RGB格式
        :return: results对象（mediapipe格式），包含multi_hand_landmarks等属性
        """
        if rgb_image is None or rgb_image.size == 0:
            self.failed_count += 1
            return None

        try:
            # 执行手势检测
            self.last_results = self.hands.process(rgb_image)

            # 更新缓存
            if self.last_results.multi_hand_landmarks:
                self.last_hand_landmarks = self.last_results.multi_hand_landmarks[0]
                self.detection_count += 1
            else:
                self.last_hand_landmarks = None
                self.failed_count += 1

            if self.last_results.multi_hand_world_landmarks:
                self.last_world_landmarks = self.last_results.multi_hand_world_landmarks[0]
            else:
                self.last_world_landmarks = None

            return self.last_results

        except Exception as e:
            print(f"[HandDetector] 处理图像时出错: {e}")
            self.failed_count += 1
            return None

    def draw_landmarks(self, image: np.ndarray,
                       hand_landmarks: Any,
                       connections: bool = True) -> np.ndarray:
        """
        在图像上绘制手部地标与连接线（用于调试）

        :param image: BGR图像
        :param hand_landmarks: 单个手的地标列表
        :param connections: 是否绘制连接线
        :return: 绘制后的图像
        """
        if image is None or hand_landmarks is None:
            return image

        try:
            # 绘制地标点和连接线
            self.mp_draw.draw_landmarks(
                image,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS if connections else None,
                self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),  # 点样式
                self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2, circle_radius=1)   # 线样式
            )

            # 标记关键点（拇指尖和食指尖）
            h, w, _ = image.shape
            landmarks = hand_landmarks.landmark

            # 拇指尖（4号点）
            thumb_tip = landmarks[4]
            tx, ty = int(thumb_tip.x * w), int(thumb_tip.y * h)
            cv2.circle(image, (tx, ty), 8, (255, 0, 0), cv2.FILLED)

            # 食指尖（8号点）
            index_tip = landmarks[8]
            ix, iy = int(index_tip.x * w), int(index_tip.y * h)
            cv2.circle(image, (ix, iy), 8, (0, 0, 255), cv2.FILLED)

            # 绘制拇指与食指之间的连线
            cv2.line(image, (tx, ty), (ix, iy), (0, 255, 0), 2)

            # 手腕点（0号点）
            wrist = landmarks[0]
            wx, wy = int(wrist.x * w), int(wrist.y * h)
            cv2.circle(image, (wx, wy), 10, (255, 255, 0), cv2.FILLED)

            return image

        except Exception as e:
            print(f"[HandDetector] 绘制地标时出错: {e}")
            return image

    def get_landmark_coords(self, hand_landmarks, image_shape: Tuple[int, int]) -> List[Tuple[float, float, float]]:
        """
        获取地标的图像坐标和深度

        :param hand_landmarks: 手部地标
        :param image_shape: 图像形状 (height, width)
        :return: 列表，每个元素为 (x, y, z) 坐标
        """
        if hand_landmarks is None:
            return []

        h, w = image_shape[:2]
        coords = []

        for landmark in hand_landmarks.landmark:
            # x, y 是归一化坐标（0-1），需要转换为像素坐标
            # z 是相对深度，值越小表示离摄像头越近
            x_px = landmark.x * w
            y_px = landmark.y * h
            z = landmark.z  # 相对深度

            coords.append((x_px, y_px, z))

        return coords

    def get_world_coords(self, world_landmarks) -> List[Tuple[float, float, float]]:
        """
        获取世界坐标系中的地标坐标（3D坐标，单位：米）

        :param world_landmarks: 世界坐标系中的地标
        :return: 列表，每个元素为 (x, y, z) 坐标
        """
        if world_landmarks is None:
            return []

        coords = []

        for landmark in world_landmarks.landmark:
            # MediaPipe 世界坐标：以手腕为原点，单位是米
            coords.append((landmark.x, landmark.y, landmark.z))

        return coords

    def get_last_results(self):
        """获取上一次的检测结果"""
        return self.last_results

    def get_last_hand_landmarks(self):
        """获取上一次的手部地标（图像坐标）"""
        return self.last_hand_landmarks

    def get_last_world_landmarks(self):
        """获取上一次的世界坐标地标"""
        return self.last_world_landmarks

    def get_detection_rate(self) -> float:
        """获取检测成功率"""
        total = self.detection_count + self.failed_count
        if total == 0:
            return 0.0
        return self.detection_count / total

    def release(self):
        """释放资源"""
        if self.hands:
            self.hands.close()
        print("[HandDetector] 资源已释放")


# 测试函数
def test_hand_detector():
    """测试手势检测模块"""
    print("测试手势检测模块...")

    # 创建检测器
    detector = HandDetector(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    print("摄像头已打开，请将手伸入画面。按 'q' 键退出...")

    try:
        while True:
            # 读取帧
            success, frame = cap.read()
            if not success:
                print("读取帧失败")
                break

            # 水平翻转（镜像显示）
            frame = cv2.flip(frame, 1)

            # 转换为RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 处理手势检测
            results = detector.process(rgb_frame)

            # 绘制结果
            if results and results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    frame = detector.draw_landmarks(frame, hand_landmarks)

                # 显示检测信息
                detection_rate = detector.get_detection_rate() * 100
                cv2.putText(frame, f"Detection Rate: {detection_rate:.1f}%",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # 获取世界坐标（用于距离计算）
                if results.multi_hand_world_landmarks:
                    world_coords = detector.get_world_coords(results.multi_hand_world_landmarks[0])
                    if len(world_coords) >= 9:  # 确保有足够的地标
                        thumb_tip = world_coords[4]  # 拇指尖
                        index_tip = world_coords[8]  # 食指尖

                        # 计算3D欧氏距离
                        import math
                        distance = math.sqrt(
                            (thumb_tip[0] - index_tip[0]) ** 2 +
                            (thumb_tip[1] - index_tip[1]) ** 2 +
                            (thumb_tip[2] - index_tip[2]) ** 2
                        )

                        cv2.putText(frame, f"Thumb-Index Distance: {distance:.3f}m",
                                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            else:
                cv2.putText(frame, "No hand detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # 显示帧
            cv2.imshow("Hand Detector Test", frame)

            # 检查退出键
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("测试被用户中断")

    finally:
        # 释放资源
        detector.release()
        cap.release()
        cv2.destroyAllWindows()
        print(f"测试完成，检测次数: {detector.detection_count}")


if __name__ == "__main__":
    test_hand_detector()