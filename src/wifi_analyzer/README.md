# Wi-Fi Capture Analyzer (PSK / SAE / EAP 基线)

## 先决条件
- 已安装 Wireshark/tshark（建议 >= 3.6）
- Linux: `dumpcap` 需 root 权限；Windows: 以管理员运行 PowerShell
- Python 3.8+（仅用标准库，无第三方依赖）

## 抓包（Linux）
```bash
sudo ./scripts/capture_start.sh wlan0 case001 captures  # 后台开始抓包
# 运行你的测试用例……
sleep 15
sudo ./scripts/capture_stop.sh captures                 # 停止，打印 pcap 路径
