# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"]=["SimHei"] #设置字体
plt.rcParams["axes.unicode_minus"]=False #该语句解决图像中的“-”负号的乱码问题


# 基本参数
fs = 1000           # 采样率（Hz）
f_c = 10            # 载波频率（Hz）
t = np.arange(0, 1, 1/fs)  # 时间轴，1秒

# 要传的两个比特值（比如 I = 1, Q = -1）
I = 1
Q = -1

# 构造发射信号：QAM = I*cos(wt) + Q*sin(wt)
carrier_I = I * np.cos(2 * np.pi * f_c * t)
carrier_Q = Q * np.sin(2 * np.pi * f_c * t)
qam_signal = carrier_I + carrier_Q

# 接收端：本地生成载波
local_cos = np.cos(2 * np.pi * f_c * t)
local_sin = np.sin(2 * np.pi * f_c * t)

# 相干解调：乘本地载波，然后积分（相当于低通滤波器）
I_received = 2 * np.mean(qam_signal * local_cos)
Q_received = 2 * np.mean(qam_signal * local_sin)

# 画图展示
plt.figure(figsize=(12, 8))

plt.subplot(3, 1, 1)
plt.plot(t, qam_signal, label="发送的QAM信号")
plt.title("QAM调制信号（I=1, Q=-1）")
plt.xlabel("时间")
plt.ylabel("振幅")
plt.grid(True)
plt.legend()

plt.subplot(3, 1, 2)
plt.plot(t, qam_signal * local_cos, label="解调后的同相分量")
plt.title("接收端：QAM信号 × 本地cos载波")
plt.xlabel("时间")
plt.ylabel("乘积")
plt.grid(True)
plt.legend()

plt.subplot(3, 1, 3)
plt.plot(t, qam_signal * local_sin, label="解调后的正交分量", color='orange')
plt.title("接收端：QAM信号 × 本地sin载波")
plt.xlabel("时间")
plt.ylabel("乘积")
plt.grid(True)
plt.legend()

plt.tight_layout()
plt.show()

(I_received, Q_received)
