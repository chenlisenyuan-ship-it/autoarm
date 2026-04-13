#!/usr/bin/env python3
"""
手势解析模块
职责：从 MediaPipe 结果中提取关键特征：
1. 夹爪开合：拇指尖（4）与食指尖（8）的 3D 欧氏距离。
2. 手腕姿态：Pitch（俯仰）和 Roll（翻滚）角度。
3. 手部位置：手腕（0）的 3D 坐标相对于图像中心的归一化偏移。
"""

import math
from typing import Dict, Optional, Tuple, List
import numpy as np


class GestureParser:
    """手势解析类"""

    def __init__(self, image_width: int = 1280, image_height: int = 720):
        """
        初始化手势解析器

        :param image_width: 图像宽度（像素）
        :param image_height: 图像高度（像素）
        """
        self.image_width = image_width
        self.image_height = image_height

        # 图像中心点
        self.image_center_x = image_width / 2
        self.image_center_y = image_height / 2

        # 特征历史（用于平滑）
        self.feature_history = {
            'grip_distance': [],
            'wrist_pitch': [],
            'wrist_roll': [],
            'hand_x': [],
            'hand_y': [],
            'hand_z': []
        }
        self.max_history_size = 5

        # 统计信息
        self.parse_count = 0
        print(f"[GestureParser] 初始化完成，图像尺寸: {image_width}x{image_height}")

    def extract_features(self, hand_landmarks, world_landmarks) -> Optional[Dict]:
        """
        提取手势特征

        :param hand_landmarks: 单个手的图像坐标地标（mediapipe格式）
        :param world_landmarks: 单个手的世界坐标地标（mediapipe格式）
        :return: dict 包含特征值，失败时返回None
        """
        if hand_landmarks is None or world_landmarks is None:
            return None

        try:
            # 获取地标列表
            hand_points = hand_landmarks.landmark
            world_points = world_landmarks.landmark

            if len(hand_points) < 21 or len(world_points) < 21:
                print(f"[GestureParser] 地标数量不足: {len(hand_points)}/{len(world_points)}")
                return None

            # 1. 计算夹爪开合距离（拇指尖与食指尖的3D欧氏距离）
            grip_distance = self._calculate_grip_distance(world_points)

            # 2. 计算手腕姿态角度（Pitch和Roll）
            wrist_pitch, wrist_roll = self._calculate_wrist_angles(world_points)

            # 3. 计算手部位置（归一化）
            hand_x, hand_y, hand_z = self._calculate_hand_position(hand_points, world_points)

            # 4. 创建特征字典
            features = {
                'grip_distance': grip_distance,        # 夹爪距离（米）
                'wrist_pitch': wrist_pitch,            # 手腕俯仰角（弧度）
                'wrist_roll': wrist_roll,              # 手腕翻滚角（弧度）
                'hand_x': hand_x,                      # 手部水平位置（归一化[-1,1]）
                'hand_y': hand_y,                      # 手部垂直位置（归一化[-1,1]）
                'hand_z': hand_z,                      # 手部深度（归一化[0,1]）
            }

            # 5. 更新历史记录（用于平滑）
            self._update_feature_history(features)

            self.parse_count += 1
            return features

        except Exception as e:
            print(f"[GestureParser] 提取特征时出错: {e}")
            return None

    def _calculate_grip_distance(self, world_points) -> float:
        """
        计算拇指尖（4）与食指尖（8）的3D欧氏距离

        :param world_points: 世界坐标地标列表
        :return: 距离（米）
        """
        # 拇指尖（4号点）
        thumb = world_points[4]
        # 食指尖（8号点）
        index = world_points[8]

        # 计算3D欧氏距离
        distance = math.sqrt(
            (thumb.x - index.x) ** 2 +
            (thumb.y - index.y) ** 2 +
            (thumb.z - index.z) ** 2
        )

        return distance

    def _calculate_wrist_angles(self, world_points) -> Tuple[float, float]:
        """
        计算手腕姿态角度（Pitch和Roll）

        Pitch（俯仰）：手腕（0）与中指根（9）在Y-Z平面上的夹角
        Roll（翻滚）：手腕（0）与食指根（5）在X-Z平面上的夹角

        :param world_points: 世界坐标地标列表
        :return: (pitch, roll) 弧度
        """
        # 手腕点（0号点）
        wrist = world_points[0]
        # 中指根（9号点）
        middle_base = world_points[9]
        # 食指根（5号点）
        index_base = world_points[5]

        # 计算Pitch（俯仰）：手腕与中指根在Y-Z平面上的夹角
        # 向量：wrist -> middle_base 在 Y-Z 平面上的投影
        dy_pitch = middle_base.y - wrist.y
        dz_pitch = middle_base.z - wrist.z

        # 避免除以零
        if abs(dz_pitch) < 1e-6:
            pitch = math.pi / 2 if dy_pitch > 0 else -math.pi / 2
        else:
            pitch = math.atan2(dy_pitch, dz_pitch)

        # 计算Roll（翻滚）：手腕与食指根在X-Z平面上的夹角
        # 向量：wrist -> index_base 在 X-Z 平面上的投影
        dx_roll = index_base.x - wrist.x
        dz_roll = index_base.z - wrist.z

        # 避免除以零
        if abs(dz_roll) < 1e-6:
            roll = math.pi / 2 if dx_roll > 0 else -math.pi / 2
        else:
            roll = math.atan2(dx_roll, dz_roll)

        # 限制角度范围在[-π/2, π/2]之间
        pitch = max(-math.pi/2, min(math.pi/2, pitch))
        roll = max(-math.pi/2, min(math.pi/2, roll))

        return pitch, roll

    def _calculate_hand_position(self, hand_points, world_points) -> Tuple[float, float, float]:
        """
        计算手部位置（归一化）

        :param hand_points: 图像坐标地标列表
        :param world_points: 世界坐标地标列表
        :return: (x, y, z) 归一化位置
        """
        # 手腕点（0号点）的2D图像坐标
        wrist_2d = hand_points[0]

        # 计算水平位置（x）：归一化到[-1, 1]，0为图像中心
        # 将像素坐标归一化到[0, 1]，然后映射到[-1, 1]
        x_normalized = (wrist_2d.x * self.image_width - self.image_center_x) / self.image_center_x
        x_normalized = max(-1.0, min(1.0, x_normalized))

        # 计算垂直位置（y）：归一化到[-1, 1]，0为图像中心
        # 注意：图像坐标系y轴向下为正，但我们需要y向上为正（符合直觉）
        y_normalized = -(wrist_2d.y * self.image_height - self.image_center_y) / self.image_center_y
        y_normalized = max(-1.0, min(1.0, y_normalized))

        # 计算深度（z）：归一化到[0, 1]
        # 使用手腕点的世界坐标z值，但需要归一化处理
        # MediaPipe的z坐标：值越小表示离摄像头越近
        wrist_z = world_points[0].z

        # 估计归一化深度（简单方法：假设z在[-0.2, 0.2]范围内）
        # 实际应用中可能需要校准
        z_min = -0.2
        z_max = 0.2
        z_normalized = (wrist_z - z_min) / (z_max - z_min)
        z_normalized = max(0.0, min(1.0, z_normalized))

        # 反转：0表示最近（手向前伸），1表示最远（手向后缩）
        z_normalized = 1.0 - z_normalized

        return x_normalized, y_normalized, z_normalized

    def _update_feature_history(self, features: Dict):
        """更新特征历史记录（用于平滑）"""
        for key, value in features.items():
            if key in self.feature_history:
                self.feature_history[key].append(value)

                # 限制历史记录大小
                if len(self.feature_history[key]) > self.max_history_size:
                    self.feature_history[key].pop(0)

    def get_smoothed_features(self, alpha: float = 0.5) -> Optional[Dict]:
        """
        获取平滑后的特征值（使用历史记录的加权平均）

        :param alpha: 平滑系数（0-1），越大表示越信任新值
        :return: 平滑后的特征字典
        """
        if self.parse_count == 0:
            return None

        smoothed = {}

        for key, history in self.feature_history.items():
            if not history:
                smoothed[key] = 0.0
                continue

            # 指数加权移动平均（EMA）
            weights = []
            for i in range(len(history)):
                weight = alpha * ((1 - alpha) ** (len(history) - i - 1))
                weights.append(weight)

            # 归一化权重
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]

            # 计算加权平均
            weighted_sum = sum(h * w for h, w in zip(history, weights))
            smoothed[key] = weighted_sum

        return smoothed

    def get_parse_count(self) -> int:
        """获取解析次数"""
        return self.parse_count

    def reset_history(self):
        """重置历史记录"""
        for key in self.feature_history:
            self.feature_history[key] = []

    @staticmethod
    def features_to_string(features: Dict) -> str:
        """
        将特征字典转换为可读字符串

        :param features: 特征字典
        :return: 格式化字符串
        """
        if features is None:
            return "No features"

        lines = []
        lines.append(f"夹爪距离: {features.get('grip_distance', 0):.3f}m")
        lines.append(f"手腕俯仰: {math.degrees(features.get('wrist_pitch', 0)):.1f}°")
        lines.append(f"手腕翻滚: {math.degrees(features.get('wrist_roll', 0)):.1f}°")
        lines.append(f"手部位置: X={features.get('hand_x', 0):.2f}, Y={features.get('hand_y', 0):.2f}, Z={features.get('hand_z', 0):.2f}")

        return "\n".join(lines)


# 测试函数
def test_gesture_parser():
    """测试手势解析模块"""
    print("测试手势解析模块...")

    # 创建解析器
    parser = GestureParser(image_width=1280, image_height=720)

    # 模拟数据（假设检测到手）
    # 注意：实际测试需要结合 HandDetector 使用
    print("模块功能验证完成")
    print(f"图像中心: ({parser.image_center_x}, {parser.image_center_y})")

    # 测试特征转换
    test_features = {
        'grip_distance': 0.1,
        'wrist_pitch': 0.5,
        'wrist_roll': -0.3,
        'hand_x': 0.2,
        'hand_y': -0.1,
        'hand_z': 0.7
    }

    print("\n特征字符串表示:")
    print(parser.features_to_string(test_features))

    # 测试平滑功能
    parser.feature_history['grip_distance'] = [0.09, 0.10, 0.11, 0.12, 0.13]
    smoothed = parser.get_smoothed_features(alpha=0.5)
    print(f"\n平滑后的夹爪距离: {smoothed.get('grip_distance', 0):.3f}")

    print("\n测试完成")


if __name__ == "__main__":
    test_gesture_parser()