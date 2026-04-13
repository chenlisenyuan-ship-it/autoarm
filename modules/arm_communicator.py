#!/usr/bin/env python3
"""
机械臂通信模块
职责：
1. 打开/关闭串口。
2. 发送打包后的二进制指令。
3. 实现硬件重启缓冲（发送指令后等待 4 秒，确保机械臂完成动作并稳定）。
"""

import time
import threading
from typing import Optional, Tuple, Dict
import serial
import serial.tools.list_ports


class ArmCommunicator:
    """机械臂通信类"""

    def __init__(self, port: str = 'COM3', baudrate: int = 115200,
                 timeout: float = 1.0, restart_buffer: float = 4.0):
        """
        初始化串口通信

        :param port: 串口号（Windows 为 COM3、COM4 等，Linux 为 /dev/ttyUSB0）
        :param baudrate: 波特率（与 ESP32 固件一致）
        :param timeout: 读取超时（秒）
        :param restart_buffer: 硬件重启缓冲时间（秒）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.restart_buffer = restart_buffer

        # 串口对象
        self.ser: Optional[serial.Serial] = None

        # 状态管理
        self.connected = False
        self.last_send_time = 0.0
        self.send_lock = threading.Lock()  # 发送锁，防止并发发送

        # 统计信息
        self.send_count = 0
        self.error_count = 0
        self.buffer_skip_count = 0

        print(f"[ArmCommunicator] 初始化完成，端口: {port}, 波特率: {baudrate}")
        print(f"                 重启缓冲: {restart_buffer}秒")

    def open(self) -> bool:
        """
        打开串口

        :return: 是否成功打开
        """
        if self.connected and self.ser is not None:
            print("[ArmCommunicator] 串口已打开")
            return True

        try:
            # 尝试打开串口
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1.0
            )

            # 等待串口稳定
            time.sleep(0.5)

            # 验证连接
            if self.ser.is_open:
                self.connected = True
                print(f"[ArmCommunicator] 串口 {self.port} 已成功打开")
                return True
            else:
                print(f"[ArmCommunicator] 无法打开串口 {self.port}")
                return False

        except serial.SerialException as e:
            print(f"[ArmCommunicator] 打开串口时出错: {e}")
            self.error_count += 1
            return False
        except Exception as e:
            print(f"[ArmCommunicator] 未知错误: {e}")
            self.error_count += 1
            return False

    def close(self):
        """关闭串口"""
        with self.send_lock:
            if self.ser is not None and self.ser.is_open:
                try:
                    self.ser.close()
                    print(f"[ArmCommunicator] 串口 {self.port} 已关闭")
                except Exception as e:
                    print(f"[ArmCommunicator] 关闭串口时出错: {e}")

            self.ser = None
            self.connected = False

    def send_command(self, command_bytes: bytes) -> bool:
        """
        发送指令，并启动重启缓冲计时

        :param command_bytes: FilterController.pack_command() 返回的字节串
        :return: 是否发送成功
        """
        if command_bytes is None or len(command_bytes) == 0:
            print("[ArmCommunicator] 指令为空")
            return False

        # 检查串口连接
        if not self.connected or self.ser is None:
            print("[ArmCommunicator] 串口未连接，尝试重新打开...")
            if not self.open():
                print("[ArmCommunicator] 重新打开串口失败")
                return False

        # 使用锁防止并发发送
        with self.send_lock:
            # 检查是否在重启缓冲期内
            if not self.is_ready():
                self.buffer_skip_count += 1
                # print(f"[ArmCommunicator] 跳过发送，仍在缓冲期内（{self._get_buffer_remaining():.1f}秒）")
                return False

            try:
                # 发送指令
                self.ser.write(command_bytes)
                self.ser.flush()  # 确保所有数据都已发送

                # 更新发送时间
                self.last_send_time = time.time()
                self.send_count += 1

                # 打印调试信息（每隔10次发送打印一次）
                if self.send_count % 10 == 0:
                    hex_str = ' '.join(f'{b:02x}' for b in command_bytes[:10])
                    print(f"[ArmCommunicator] 已发送指令 #{self.send_count}，缓冲开始...")

                return True

            except serial.SerialTimeoutException:
                print("[ArmCommunicator] 发送超时")
                self.error_count += 1
                self.connected = False
                return False
            except serial.SerialException as e:
                print(f"[ArmCommunicator] 串口错误: {e}")
                self.error_count += 1
                self.connected = False
                return False
            except Exception as e:
                print(f"[ArmCommunicator] 发送指令时出错: {e}")
                self.error_count += 1
                return False

    def is_ready(self) -> bool:
        """
        检查是否已过重启缓冲时间

        :return: 是否可以发送下一条指令
        """
        if self.last_send_time == 0:
            return True  # 第一次发送

        elapsed = time.time() - self.last_send_time
        return elapsed >= self.restart_buffer

    def _get_buffer_remaining(self) -> float:
        """获取剩余的缓冲时间（秒）"""
        if self.last_send_time == 0:
            return 0.0

        elapsed = time.time() - self.last_send_time
        remaining = max(0.0, self.restart_buffer - elapsed)
        return remaining

    def emergency_stop(self) -> bool:
        """
        发送急停指令（所有关节回到中位）

        :return: 是否发送成功
        """
        print("[ArmCommunicator] 发送急停指令...")

        # 急停指令：所有关节PWM=1500（中位）
        # 帧头 + 6个关节(中位) + 校验和
        emergency_command = bytes([
            0x55, 0xAA,  # 帧头
            1, 0xDC, 0x05,  # 关节1: 1500 = 0x05DC
            2, 0xDC, 0x05,  # 关节2: 1500
            3, 0xDC, 0x05,  # 关节3: 1500
            4, 0xDC, 0x05,  # 关节4: 1500
            5, 0xDC, 0x05,  # 关节5: 1500（夹爪闭合）
            6, 0xDC, 0x05,  # 关节6: 1500
            0xA8  # 校验和
        ])

        # 强制发送（跳过缓冲检查）
        success = self._force_send(emergency_command)

        if success:
            print("[ArmCommunicator] 急停指令已发送")
        else:
            print("[ArmCommunicator] 急停指令发送失败")

        return success

    def _force_send(self, command_bytes: bytes) -> bool:
        """强制发送指令（跳过缓冲检查）"""
        if not self.connected or self.ser is None:
            if not self.open():
                return False

        try:
            self.ser.write(command_bytes)
            self.ser.flush()
            self.last_send_time = time.time()  # 仍然更新发送时间
            return True
        except Exception as e:
            print(f"[ArmCommunicator] 强制发送失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'connected': self.connected,
            'send_count': self.send_count,
            'error_count': self.error_count,
            'buffer_skip_count': self.buffer_skip_count,
            'buffer_remaining': self._get_buffer_remaining(),
            'port': self.port,
            'baudrate': self.baudrate,
        }

    def is_connected(self) -> bool:
        """检查是否连接"""
        return self.connected

    @staticmethod
    def list_available_ports() -> list:
        """
        列出可用的串口

        :return: 可用串口列表
        """
        ports = []
        try:
            available_ports = list(serial.tools.list_ports.comports())

            for port in available_ports:
                port_info = {
                    'device': port.device,
                    'description': port.description,
                    'manufacturer': port.manufacturer if port.manufacturer else 'N/A',
                    'hwid': port.hwid,
                }
                ports.append(port_info)

        except Exception as e:
            print(f"[ArmCommunicator] 列出串口时出错: {e}")

        return ports

    def __del__(self):
        """析构函数"""
        self.close()


# 测试函数
def test_arm_communicator():
    """测试机械臂通信模块"""
    print("测试机械臂通信模块...")

    # 列出可用串口
    print("可用串口:")
    ports = ArmCommunicator.list_available_ports()
    for i, port_info in enumerate(ports):
        print(f"  {i+1}. {port_info['device']} - {port_info['description']}")

    if not ports:
        print("未找到可用串口，跳过实际通信测试")
        print("进行模拟测试...")

        # 创建通信对象（模拟模式）
        communicator = ArmCommunicator(port='COM3', baudrate=115200, restart_buffer=2.0)

        # 测试指令打包（使用FilterController生成测试指令）
        from modules.filter_control import FilterController
        controller = FilterController()
        test_pwms = controller._get_default_pwms()
        command = controller.pack_command(test_pwms)

        print(f"\n测试指令（{len(command)}字节）:")
        controller.print_command_hex(command)

        # 模拟发送（实际不会发送）
        print("\n模拟发送指令...")
        # 注意：这里不会实际发送，因为串口不存在

        # 测试缓冲逻辑
        print("\n测试缓冲逻辑（2秒缓冲）...")
        print(f"初始状态 - 是否可以发送: {communicator.is_ready()}")

        # 模拟发送时间更新
        communicator.last_send_time = time.time()
        print(f"发送后 - 是否可以发送: {communicator.is_ready()}")
        print(f"剩余缓冲时间: {communicator._get_buffer_remaining():.1f}秒")

        # 等待1秒
        print("等待1秒...")
        time.sleep(1)
        print(f"1秒后 - 是否可以发送: {communicator.is_ready()}")
        print(f"剩余缓冲时间: {communicator._get_buffer_remaining():.1f}秒")

        # 等待额外1秒
        print("再等待1秒...")
        time.sleep(1)
        print(f"2秒后 - 是否可以发送: {communicator.is_ready()}")

        # 显示统计信息
        print("\n统计信息:")
        stats = communicator.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    else:
        # 实际硬件测试
        print("\n选择第一个可用串口进行测试...")
        test_port = ports[0]['device']
        print(f"测试串口: {test_port}")

        communicator = ArmCommunicator(port=test_port, baudrate=115200, restart_buffer=2.0)

        # 尝试打开串口
        if communicator.open():
            print("串口打开成功")

            # 创建测试指令
            from modules.filter_control import FilterController
            controller = FilterController()
            test_pwms = controller._get_default_pwms()
            command = controller.pack_command(test_pwms)

            print(f"\n测试指令（{len(command)}字节）:")
            controller.print_command_hex(command)

            # 发送测试指令
            print("\n发送测试指令...")
            success = communicator.send_command(command)

            if success:
                print("指令发送成功")
                print(f"等待缓冲时间（{communicator.restart_buffer}秒）...")
                time.sleep(communicator.restart_buffer)

                # 测试急停
                print("\n测试急停指令...")
                communicator.emergency_stop()
            else:
                print("指令发送失败")

            # 关闭串口
            communicator.close()
        else:
            print("串口打开失败")

    print("\n测试完成")


if __name__ == "__main__":
    test_arm_communicator()