#!/usr/bin/env python3
"""
映射模块
职责：将手势特征映射为机械臂关节的 PWM 值（或角度）。
所有映射均采用线性插值，并经过限幅保护。
"""

import numpy as np
from typing import Dict, Tuple, List


class MappingEngine:
    """映射引擎类"""

    def __init__(self, mapping_config: Dict = None):
        """
        初始化映射引擎

        :param mapping_config: 映射配置字典，如果为None则使用默认配置
        """
        if mapping_config is None:
            # 默认映射配置（与tech.md一致）
            mapping_config = {
                'grip': {
                    'input_range': (0.030, 0.407),  # 夹爪距离（米）
                    'output_range': (1500, 600),     # PWM值（1500=闭合，600=张开）
                },
                'pitch': {
                    'input_range': (-1.57, 1.57),   # 手腕俯仰角（弧度，±π/2）
                    'output_range': (500, 2500),    # PWM范围
                },
                'roll': {
                    'input_range': (-1.57, 1.57),   # 手腕翻滚角（弧度，±π/2）
                    'output_range': (500, 2500),    # PWM范围
                },
                'x': {
                    'input_range': (-1, 1),         # 手部水平位置（归一化）
                    'output_range': (500, 2500),    # PWM范围
                },
                'y': {
                    'input_range': (-1, 1),         # 手部垂直位置（归一化）
                    'output_range': (500, 2500),    # PWM范围
                },
                'z': {
                    'input_range': (0, 1),          # 手部深度（归一化）
                    'output_range': (500, 2500),    # PWM范围
                },
            }

        self.mapping_config = mapping_config

        # 关节ID映射（根据LOBOT机械臂协议）
        self.joint_ids = {
            'joint_1': 1,   # 底座旋转（对应x）
            'joint_2': 2,   # 近端关节（对应pitch）
            'joint_3': 3,   # 大臂关节（对应y）
            'joint_4': 4,   # 小臂关节（对应z）
            'joint_5': 5,   # 夹爪开合（对应grip）
            'joint_6': 6,   # 夹爪旋转（对应roll）
        }

        # 安全限制
        self.min_pwm = 500
        self.max_pwm = 2500

        # 映射统计
        self.map_count = 0

        print("[MappingEngine] 初始化完成")

    def map_features(self, features: Dict) -> Dict:
        """
        将手势特征字典映射为 6 个关节的 PWM 值

        :param features: GestureParser 输出的特征字典
                      必须包含以下键：'grip_distance', 'wrist_pitch', 'wrist_roll',
                      'hand_x', 'hand_y', 'hand_z'
        :return: dict {
            'joint_1': int,  # 底座旋转（x）
            'joint_2': int,  # 近端关节（pitch）
            'joint_3': int,  # 大臂（y）
            'joint_4': int,  # 小臂（z）
            'joint_5': int,  # 夹爪开合（grip）
            'joint_6': int,  # 夹爪旋转（roll）
        }
        """
        if features is None:
            # 返回安全位置（所有关节中位）
            return self._get_safe_position()

        try:
            # 确保所有必需的特征都存在
            required_features = ['grip_distance', 'wrist_pitch', 'wrist_roll',
                                'hand_x', 'hand_y', 'hand_z']

            for feat in required_features:
                if feat not in features:
                    print(f"[MappingEngine] 缺少特征: {feat}")
                    return self._get_safe_position()

            # 1. 夹爪开合映射（特殊：输入越大，PWM越小）
            grip_pwm = self._linear_map(
                value=features['grip_distance'],
                input_range=self.mapping_config['grip']['input_range'],
                output_range=self.mapping_config['grip']['output_range'],
                clamp=True
            )

            # 2. 手腕俯仰映射（pitch）
            pitch_pwm = self._linear_map(
                value=features['wrist_pitch'],
                input_range=self.mapping_config['pitch']['input_range'],
                output_range=self.mapping_config['pitch']['output_range'],
                clamp=True
            )

            # 3. 手腕翻滚映射（roll）
            roll_pwm = self._linear_map(
                value=features['wrist_roll'],
                input_range=self.mapping_config['roll']['input_range'],
                output_range=self.mapping_config['roll']['output_range'],
                clamp=True
            )

            # 4. 手部X位置映射（底座旋转）
            x_pwm = self._linear_map(
                value=features['hand_x'],
                input_range=self.mapping_config['x']['input_range'],
                output_range=self.mapping_config['x']['output_range'],
                clamp=True
            )

            # 5. 手部Y位置映射（大臂关节）
            y_pwm = self._linear_map(
                value=features['hand_y'],
                input_range=self.mapping_config['y']['input_range'],
                output_range=self.mapping_config['y']['output_range'],
                clamp=True
            )

            # 6. 手部Z位置映射（小臂关节）
            z_pwm = self._linear_map(
                value=features['hand_z'],
                input_range=self.mapping_config['z']['input_range'],
                output_range=self.mapping_config['z']['output_range'],
                clamp=True
            )

            # 创建PWM字典
            pwms = {
                'joint_1': int(x_pwm),      # 底座旋转
                'joint_2': int(pitch_pwm),  # 近端关节
                'joint_3': int(y_pwm),      # 大臂
                'joint_4': int(z_pwm),      # 小臂
                'joint_5': int(grip_pwm),   # 夹爪
                'joint_6': int(roll_pwm),   # 夹爪旋转
            }

            # 应用安全限制（双重保险）
            pwms = self._apply_safety_clamp(pwms)

            self.map_count += 1
            return pwms

        except Exception as e:
            print(f"[MappingEngine] 映射特征时出错: {e}")
            return self._get_safe_position()

    def _linear_map(self, value: float, input_range: Tuple[float, float],
                   output_range: Tuple[float, float], clamp: bool = True) -> float:
        """
        线性映射函数（使用np.interp）

        :param value: 输入值
        :param input_range: 输入范围 (min, max)
        :param output_range: 输出范围 (min, max)
        :param clamp: 是否将输入值限制在输入范围内
        :return: 映射后的值
        """
        if clamp:
            # 将输入值限制在输入范围内
            value = max(input_range[0], min(input_range[1], value))

        # 线性插值
        result = np.interp(value, input_range, output_range)

        return result

    def _apply_safety_clamp(self, pwms: Dict) -> Dict:
        """
        应用安全限制（将所有PWM值限制在允许范围内）

        :param pwms: PWM字典
        :return: 限制后的PWM字典
        """
        safe_pwms = {}
        for joint, pwm in pwms.items():
            safe_pwm = int(np.clip(pwm, self.min_pwm, self.max_pwm))
            safe_pwms[joint] = safe_pwm

        return safe_pwms

    def _get_safe_position(self) -> Dict:
        """
        获取安全位置（所有关节中位）

        :return: 安全位置PWM字典
        """
        safe_pwm = (self.min_pwm + self.max_pwm) // 2  # 中位值

        return {
            'joint_1': safe_pwm,  # 底座旋转
            'joint_2': safe_pwm,  # 近端关节
            'joint_3': safe_pwm,  # 大臂
            'joint_4': safe_pwm,  # 小臂
            'joint_5': 1500,      # 夹爪闭合（安全）
            'joint_6': safe_pwm,  # 夹爪旋转
        }

    def get_joint_id(self, joint_name: str) -> int:
        """
        获取关节的ID

        :param joint_name: 关节名称（如'joint_1'）
        :return: 关节ID
        """
        return self.joint_ids.get(joint_name, 0)

    def get_joint_ids(self) -> Dict:
        """获取所有关节的ID映射"""
        return self.joint_ids.copy()

    def get_map_count(self) -> int:
        """获取映射次数"""
        return self.map_count

    @staticmethod
    def pwms_to_string(pwms: Dict) -> str:
        """
        将PWM字典转换为可读字符串

        :param pwms: PWM字典
        :return: 格式化字符串
        """
        if pwms is None:
            return "No PWM values"

        lines = []
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
                lines.append(f"{name}: {pwms[joint]}")

        return "\n".join(lines)

    def update_mapping_config(self, config_name: str, input_range: Tuple[float, float],
                             output_range: Tuple[float, float]):
        """
        更新映射配置

        :param config_name: 配置名称（'grip', 'pitch', 'roll', 'x', 'y', 'z'）
        :param input_range: 新的输入范围
        :param output_range: 新的输出范围
        """
        if config_name in self.mapping_config:
            self.mapping_config[config_name]['input_range'] = input_range
            self.mapping_config[config_name]['output_range'] = output_range
            print(f"[MappingEngine] 更新配置 {config_name}: {input_range} -> {output_range}")
        else:
            print(f"[MappingEngine] 未知配置: {config_name}")


# 测试函数
def test_mapping_engine():
    """测试映射引擎模块"""
    print("测试映射引擎模块...")

    # 创建映射引擎
    mapper = MappingEngine()

    # 测试特征映射
    test_features = {
        'grip_distance': 0.2,      # 中间值
        'wrist_pitch': 0.0,        # 中间值
        'wrist_roll': 0.0,         # 中间值
        'hand_x': 0.0,             # 中心
        'hand_y': 0.0,             # 中心
        'hand_z': 0.5,             # 中间深度
    }

    print("测试特征:")
    for key, value in test_features.items():
        print(f"  {key}: {value}")

    # 映射到PWM
    pwms = mapper.map_features(test_features)

    print("\n映射结果:")
    print(mapper.pwms_to_string(pwms))

    # 测试边界情况
    print("\n边界测试:")
    test_cases = [
        ('最小夹爪距离', {'grip_distance': 0.030, 'wrist_pitch': 0.0, 'wrist_roll': 0.0,
                       'hand_x': 0.0, 'hand_y': 0.0, 'hand_z': 0.5}),
        ('最大夹爪距离', {'grip_distance': 0.407, 'wrist_pitch': 0.0, 'wrist_roll': 0.0,
                       'hand_x': 0.0, 'hand_y': 0.0, 'hand_z': 0.5}),
        ('左侧位置', {'grip_distance': 0.2, 'wrist_pitch': 0.0, 'wrist_roll': 0.0,
                    'hand_x': -1.0, 'hand_y': 0.0, 'hand_z': 0.5}),
        ('右侧位置', {'grip_distance': 0.2, 'wrist_pitch': 0.0, 'wrist_roll': 0.0,
                    'hand_x': 1.0, 'hand_y': 0.0, 'hand_z': 0.5}),
    ]

    for name, features in test_cases:
        pwms = mapper.map_features(features)
        print(f"\n{name}:")
        print(f"  夹爪PWM: {pwms.get('joint_5', 0)}")
        if 'hand_x' in features:
            print(f"  底座PWM: {pwms.get('joint_1', 0)}")

    # 测试安全限制
    print(f"\n安全限制范围: {mapper.min_pwm} - {mapper.max_pwm}")
    print(f"映射次数: {mapper.get_map_count()}")

    print("\n测试完成")


if __name__ == "__main__":
    test_mapping_engine()