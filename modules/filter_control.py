#!/usr/bin/env python3
"""
滤波与控制模块
职责：
1. EMA滤波：对每个关节的PWM值进行一阶低通滤波（Alpha = 0.4）。
2. 死区判断：仅当滤波后的PWM与上一次下发值的差值 > 15时才触发下发。
3. 指令打包：将6个PWM值按小端序打包为二进制帧。
4. 安全限幅：确保PWM值在机械臂允许范围内（[500, 2500]）。
"""

import struct
import time
from typing import Dict, Optional, Tuple
import numpy as np


class FilterController:
    """滤波控制器类"""

    def __init__(self, alpha: float = 0.4, dead_zone: int = 15,
                 min_pwm: int = 500, max_pwm: int = 2500):
        """
        初始化滤波控制器

        :param alpha: EMA滤波系数（0~1），越小滤波越强
        :param dead_zone: 死区阈值，避免微小波动导致频繁下发
        :param min_pwm: 最小PWM值
        :param max_pwm: 最大PWM值
        """
        self.alpha = alpha
        self.dead_zone = dead_zone
        self.min_pwm = min_pwm
        self.max_pwm = max_pwm

        # 状态记录
        self.last_raw_pwms = None      # 上一次的原始PWM值
        self.last_filtered_pwms = None # 上一次的滤波后PWM值
        self.last_sent_pwms = None     # 上一次实际下发的PWM值
        self.last_send_time = 0        # 上一次下发时间

        # 关节顺序（与MappingEngine一致）
        self.joint_names = ['joint_1', 'joint_2', 'joint_3',
                           'joint_4', 'joint_5', 'joint_6']

        # 统计信息
        self.filter_count = 0
        self.send_count = 0
        self.skip_count = 0

        print(f"[FilterController] 初始化完成，alpha={alpha}, 死区={dead_zone}")

    def apply_filter(self, new_pwms: Dict) -> Dict:
        """
        对新的PWM字典进行EMA滤波

        :param new_pwms: MappingEngine输出的PWM字典
        :return: 滤波后的PWM字典
        """
        if new_pwms is None:
            return self.last_filtered_pwms or self._get_default_pwms()

        # 验证PWM字典
        if not self._validate_pwms(new_pwms):
            print("[FilterController] PWM字典无效，使用默认值")
            return self.last_filtered_pwms or self._get_default_pwms()

        # 安全限制（双重保险）
        safe_pwms = self._apply_safety_clamp(new_pwms)

        # 如果是第一次调用，直接使用输入值
        if self.last_filtered_pwms is None:
            filtered_pwms = safe_pwms.copy()
        else:
            # EMA滤波：filtered = alpha * new + (1 - alpha) * last
            filtered_pwms = {}
            for joint in self.joint_names:
                new_value = safe_pwms.get(joint, 1500)
                last_value = self.last_filtered_pwms.get(joint, 1500)

                filtered = self.alpha * new_value + (1 - self.alpha) * last_value
                filtered_pwms[joint] = int(filtered)

        # 更新状态
        self.last_raw_pwms = new_pwms.copy()
        self.last_filtered_pwms = filtered_pwms.copy()

        self.filter_count += 1
        return filtered_pwms

    def should_send(self, filtered_pwms: Dict) -> bool:
        """
        判断是否需要下发指令（死区检查）

        :param filtered_pwms: 滤波后的PWM字典
        :return: bool，是否需要下发
        """
        if filtered_pwms is None:
            return False

        # 如果是第一次下发，需要发送
        if self.last_sent_pwms is None:
            return True

        # 检查是否有任何一个关节的变化超过死区阈值
        for joint in self.joint_names:
            if joint in filtered_pwms and joint in self.last_sent_pwms:
                delta = abs(filtered_pwms[joint] - self.last_sent_pwms[joint])
                if delta > self.dead_zone:
                    return True

        # 所有关节的变化都在死区内
        self.skip_count += 1
        return False

    def pack_command(self, pwms: Dict, joint_ids: Optional[Dict] = None) -> bytes:
        """
        将PWM字典打包为二进制帧

        帧格式（LOBOT机械臂协议）：
        <头 0x55 0xAA> <ID1> <PWM低字节> <PWM高字节> … <ID6> <PWM低字节> <PWM高字节> <校验和>

        :param pwms: 关节PWM字典
        :param joint_ids: 关节ID映射字典，如果为None则使用默认映射
        :return: bytes对象（长度 = 2 + 6*3 + 1 = 21字节）
        """
        if pwms is None:
            return self._pack_default_command()

        if joint_ids is None:
            # 默认关节ID映射（与MappingEngine一致）
            joint_ids = {
                'joint_1': 1,  # 底座旋转
                'joint_2': 2,  # 近端关节
                'joint_3': 3,  # 大臂
                'joint_4': 4,  # 小臂
                'joint_5': 5,  # 夹爪
                'joint_6': 6,  # 夹爪旋转
            }

        try:
            # 帧头
            frame = bytearray([0x55, 0xAA])

            # 计算校验和（初始值为0）
            checksum = 0

            # 添加每个关节的数据
            for joint_name in self.joint_names:
                if joint_name not in joint_ids:
                    print(f"[FilterController] 未知关节: {joint_name}")
                    continue

                joint_id = joint_ids[joint_name]
                pwm_value = pwms.get(joint_name, 1500)

                # 限制PWM范围
                pwm_value = max(self.min_pwm, min(self.max_pwm, pwm_value))

                # 将PWM值拆分为低字节和高字节（小端序）
                pwm_low = pwm_value & 0xFF          # 低8位
                pwm_high = (pwm_value >> 8) & 0xFF  # 高8位

                # 添加到帧中
                frame.append(joint_id)
                frame.append(pwm_low)
                frame.append(pwm_high)

                # 更新校验和（所有字节的和，取低8位）
                checksum = (checksum + joint_id + pwm_low + pwm_high) & 0xFF

            # 确保帧长度正确（6个关节）
            if len(frame) != 20:  # 2字节头 + 6*3字节数据 = 20字节
                print(f"[FilterController] 帧长度错误: {len(frame)} 字节")
                return self._pack_default_command()

            # 添加校验和
            frame.append(checksum & 0xFF)

            return bytes(frame)

        except Exception as e:
            print(f"[FilterController] 打包指令时出错: {e}")
            return self._pack_default_command()

    def update_last_sent(self, pwms: Dict):
        """
        更新上一次下发的PWM值（仅在指令实际发送后调用）

        :param pwms: 实际下发的PWM字典
        """
        if pwms is not None:
            self.last_sent_pwms = pwms.copy()
            self.last_send_time = time.time()
            self.send_count += 1

    def reset_filter(self):
        """重置滤波状态"""
        self.last_filtered_pwms = None
        self.last_raw_pwms = None
        print("[FilterController] 滤波状态已重置")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'filter_count': self.filter_count,
            'send_count': self.send_count,
            'skip_count': self.skip_count,
            'skip_rate': self.skip_count / max(self.filter_count, 1),
        }

    def _validate_pwms(self, pwms: Dict) -> bool:
        """验证PWM字典是否有效"""
        if not isinstance(pwms, dict):
            return False

        # 检查必需的关节
        for joint in self.joint_names:
            if joint not in pwms:
                print(f"[FilterController] 缺少关节: {joint}")
                return False

            # 检查值类型
            value = pwms[joint]
            if not isinstance(value, (int, float)):
                print(f"[FilterController] 关节 {joint} 的值类型错误: {type(value)}")
                return False

        return True

    def _apply_safety_clamp(self, pwms: Dict) -> Dict:
        """应用安全限制"""
        safe_pwms = {}
        for joint, pwm in pwms.items():
            safe_pwm = int(np.clip(pwm, self.min_pwm, self.max_pwm))
            safe_pwms[joint] = safe_pwm
        return safe_pwms

    def _get_default_pwms(self) -> Dict:
        """获取默认PWM值（安全位置）"""
        safe_pwm = (self.min_pwm + self.max_pwm) // 2
        return {
            'joint_1': safe_pwm,
            'joint_2': safe_pwm,
            'joint_3': safe_pwm,
            'joint_4': safe_pwm,
            'joint_5': 1500,  # 夹爪闭合（安全）
            'joint_6': safe_pwm,
        }

    def _pack_default_command(self) -> bytes:
        """打包默认指令（安全位置）"""
        default_pwms = self._get_default_pwms()
        return self.pack_command(default_pwms)

    @staticmethod
    def print_command_hex(command_bytes: bytes):
        """
        以十六进制格式打印指令（用于调试）

        :param command_bytes: 指令字节串
        """
        if command_bytes is None:
            print("指令为空")
            return

        hex_str = ' '.join(f'{b:02x}' for b in command_bytes)
        print(f"指令: {hex_str}")

    @staticmethod
    def parse_command_bytes(command_bytes: bytes) -> Optional[Dict]:
        """
        解析二进制指令为PWM字典（用于测试）

        :param command_bytes: 指令字节串
        :return: 解析出的PWM字典
        """
        if len(command_bytes) != 21:
            print(f"[FilterController] 指令长度错误: {len(command_bytes)} 字节")
            return None

        try:
            # 验证帧头
            if command_bytes[0] != 0x55 or command_bytes[1] != 0xAA:
                print("[FilterController] 帧头错误")
                return None

            pwms = {}
            checksum = 0

            # 解析每个关节（6个关节）
            for i in range(6):
                offset = 2 + i * 3
                joint_id = command_bytes[offset]
                pwm_low = command_bytes[offset + 1]
                pwm_high = command_bytes[offset + 2]

                pwm_value = (pwm_high << 8) | pwm_low
                pwms[f'joint_{joint_id}'] = pwm_value

                # 更新校验和
                checksum = (checksum + joint_id + pwm_low + pwm_high) & 0xFF

            # 验证校验和
            expected_checksum = command_bytes[20] & 0xFF
            if checksum != expected_checksum:
                print(f"[FilterController] 校验和错误: {checksum} != {expected_checksum}")

            return pwms

        except Exception as e:
            print(f"[FilterController] 解析指令时出错: {e}")
            return None


# 测试函数
def test_filter_controller():
    """测试滤波控制器模块"""
    print("测试滤波控制器模块...")

    # 创建滤波控制器
    controller = FilterController(alpha=0.4, dead_zone=15)

    # 测试PWM字典
    test_pwms = {
        'joint_1': 1500,  # 底座
        'joint_2': 1500,  # 近端关节
        'joint_3': 1500,  # 大臂
        'joint_4': 1500,  # 小臂
        'joint_5': 1500,  # 夹爪
        'joint_6': 1500,  # 夹爪旋转
    }

    print("初始PWM值:")
    for joint, pwm in test_pwms.items():
        print(f"  {joint}: {pwm}")

    # 测试滤波
    print("\n测试EMA滤波...")
    filtered = controller.apply_filter(test_pwms)
    print(f"滤波后结果: {filtered}")

    # 测试死区判断
    print(f"\n测试死区判断（阈值={controller.dead_zone}）...")
    should_send = controller.should_send(filtered)
    print(f"是否需要下发: {should_send}")

    if should_send:
        # 测试指令打包
        print("\n测试指令打包...")
        command = controller.pack_command(filtered)
        controller.print_command_hex(command)

        # 测试指令解析
        print("\n测试指令解析...")
        parsed = controller.parse_command_bytes(command)
        if parsed:
            print(f"解析结果: {parsed}")

        # 更新发送状态
        controller.update_last_sent(filtered)

    # 测试微小变化（不应触发发送）
    print("\n测试微小变化...")
    small_change = test_pwms.copy()
    small_change['joint_1'] = 1510  # 只改变10，小于死区15

    filtered2 = controller.apply_filter(small_change)
    should_send2 = controller.should_send(filtered2)
    print(f"微小变化后是否需要下发: {should_send2}")

    # 测试大幅变化（应触发发送）
    print("\n测试大幅变化...")
    large_change = test_pwms.copy()
    large_change['joint_1'] = 1600  # 改变100，大于死区15

    filtered3 = controller.apply_filter(large_change)
    should_send3 = controller.should_send(filtered3)
    print(f"大幅变化后是否需要下发: {should_send3}")

    # 显示统计信息
    print("\n统计信息:")
    stats = controller.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n测试完成")


if __name__ == "__main__":
    test_filter_controller()