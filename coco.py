# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import asyncio
import telnetlib3


async def telnet_client(host, port, command):
    reader, writer = await telnetlib3.open_connection(host, port)

    async def safe_read():
        try:
            return await asyncio.wait_for(reader.read(1024), timeout=2)  # 2 秒超时
        except asyncio.TimeoutError:
            return "Read timeout"

    async def read_all(timeout=2):
        """循环读取数据，若超时无数据，则退出"""
        while True:
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout)
                if not data:  # 服务器关闭连接
                    break
                print(data, end="")
            except asyncio.TimeoutError:
                break

    # 读取服务器的欢迎信息
    welcome = await safe_read()

    # 读取服务器回显
    response = await safe_read()

    # 发送命令
    writer.write(command + "\n")
    await writer.drain()

    # 读取命令执行结果
    result = await read_all()
    # print(f"Command Output: {result}")

    # 关闭连接
    writer.close()
    return result


# 示例调用
host = "192.168.50.110"
port = 23
command = "iw wlan0 link"

print(asyncio.run(telnet_client(host, port, command)))
