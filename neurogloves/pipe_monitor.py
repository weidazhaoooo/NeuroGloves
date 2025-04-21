"""
OpenGloves命名管道监视器
创建一个模拟OpenGloves的命名管道服务器，接收并解析发送到该管道的消息。
"""

import os
import sys
import time
import struct
import threading
import win32pipe
import win32file
import win32api
import win32con
import pywintypes
import win32security

# 命名管道路径
PIPE_NAME = r'\\.\pipe\vrapplication\input\glove\v1\right'
BUFFER_SIZE = 1024
PIPE_TIMEOUT = 5000  # 毫秒

def create_pipe_server():
    """创建并返回一个命名管道服务器句柄"""
    try:
        # 使用默认安全设置创建管道，移除需要管理员权限的标志
        pipe_handle = win32pipe.CreateNamedPipe(
            PIPE_NAME,
            win32pipe.PIPE_ACCESS_INBOUND,  # 移除 win32con.WRITE_DAC
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1,  # 最大实例数
            BUFFER_SIZE,
            BUFFER_SIZE,
            PIPE_TIMEOUT,
            None  # 使用默认安全属性而非自定义ACL
        )
        print(f"成功创建命名管道服务器: {PIPE_NAME}")
        return pipe_handle
    except pywintypes.error as e:
        print(f"创建命名管道失败: {e}")
        
        # 如果错误是"管道已存在"，可以尝试连接到现有管道
        if e.winerror == 231:  # 管道忙
            print("尝试连接到现有管道...")
            try:
                return win32file.CreateFile(
                    PIPE_NAME,
                    win32con.GENERIC_READ,
                    0,
                    None,
                    win32con.OPEN_EXISTING,
                    0,
                    None
                )
            except pywintypes.error as e2:
                print(f"连接到现有管道失败: {e2}")
                
        sys.exit(1)

def decode_data(data):
    """解码从管道接收到的二进制数据"""
    if len(data) < 28:  # 至少需要5个浮点数(20字节)和8个布尔值(8字节)
        print(f"收到的数据太短: {len(data)} 字节")
        return None
    
    try:
        # 解析5个手指弯曲值 (5个浮点数)
        fingers = struct.unpack('@5f', data[:20])
        
        # 解析摇杆值 (2个浮点数)
        joys = struct.unpack('@2f', data[20:28])
        
        # 解析按钮状态 (8个布尔值)
        buttons = struct.unpack('@8?', data[28:36])
        
        return {
            'fingers': fingers,
            'joys': joys,
            'buttons': buttons
        }
    except struct.error as e:
        print(f"解析数据出错: {e}")
        print(f"原始数据(十六进制): {data.hex()}")
        return None

def print_decoded_data(decoded_data):
    """打印解码后的数据"""
    if not decoded_data:
        return
    
    fingers = decoded_data['fingers']
    joys = decoded_data['joys']
    buttons = decoded_data['buttons']
    
    print("\n" + "="*60)
    print(f"手指弯曲度: [拇指: {fingers[0]:.2f}, 食指: {fingers[1]:.2f}, "
          f"中指: {fingers[2]:.2f}, 无名指: {fingers[3]:.2f}, 小指: {fingers[4]:.2f}]")
    print(f"摇杆位置: [X: {joys[0]:.2f}, Y: {joys[1]:.2f}]")
    
    button_names = ["摇杆点击", "扳机按钮", "A按钮", "B按钮", "抓取", "捏取", "菜单", "校准"]
    active_buttons = [name for name, state in zip(button_names, buttons) if state]
    print(f"按钮状态: {', '.join(active_buttons) if active_buttons else '无活动按钮'}")
    print("="*60)

def monitor_pipe():
    """监控命名管道并处理接收到的数据"""
    print("开始监听命名管道连接...")
    print("等待客户端连接...")
    
    try:
        while True:
            # 创建新的管道服务器
            pipe_handle = create_pipe_server()
            
            try:
                # 等待客户端连接
                win32pipe.ConnectNamedPipe(pipe_handle, None)
                print("客户端已连接，等待数据...")
                
                # 读取数据
                result, data = win32file.ReadFile(pipe_handle, BUFFER_SIZE)
                if result == 0 and data:
                    print(f"接收到 {len(data)} 字节的数据")
                    decoded = decode_data(data)
                    print_decoded_data(decoded)
                else:
                    print(f"读取错误或无数据: 结果 = {result}")
            except pywintypes.error as e:
                print(f"管道操作错误: {e}")
            finally:
                # 关闭当前管道句柄
                win32file.CloseHandle(pipe_handle)
    except KeyboardInterrupt:
        print("\n正在退出监视器...")
        if 'pipe_handle' in locals():
            win32file.CloseHandle(pipe_handle)
    except Exception as e:
        print(f"发生未预期错误: {e}")
        if 'pipe_handle' in locals():
            win32file.CloseHandle(pipe_handle)

if __name__ == "__main__":
    print("OpenGloves命名管道监视器")
    print("按Ctrl+C退出")
    monitor_pipe()