# test_mode_mapping.py
"""测试无线模式映射"""

from src.tools.router_tool.router_telnet_control import _ASUS_ROUTER_MODE_MAP, BAND_CONFIG
from src.tools.router_tool.AsusRouter.AsusTelnetNvramControl import AsusTelnetNvramControl

print("=" * 60)
print("无线模式映射测试")
print("=" * 60)

# 1. 检查语义层映射
print("\n[1] _ASUS_ROUTER_MODE_MAP:")
for band, modes in _ASUS_ROUTER_MODE_MAP.items():
    print(f"\n{band.upper()}:")
    for semantic, native in modes.items():
        print(f"  {semantic:15} -> {native}")

# 2. 检查底层支持的模式
print("\n[2] AsusTelnetNvramControl.WIRELESS_5:")
print(f"  {AsusTelnetNvramControl.WIRELESS_5}")

# 3. 测试 'a-only' 的完整映射链
print("\n[3] 测试 'a-only' 模式映射链:")
semantic_mode = 'a-only'
native_mode = _ASUS_ROUTER_MODE_MAP['5g'][semantic_mode]
print(f"  语义模式：{semantic_mode}")
print(f"  原生模式：{native_mode}")
print(f"  是否在 WIRELESS_5 中：{native_mode in AsusTelnetNvramControl.WIRELESS_5}")

# 4. 检查底层命令映射
cmd_map = {
    'auto': 'wl1_11ax=1; wl1_nmode_x=0',
    '11a': 'wl1_11ax=0; wl1_nmode_x=7',
    '11n': 'wl1_11ax=0; wl1_nmode_x=1',
    '11ac': 'wl1_11ax=0; wl1_nmode_x=0',
    '11ax': 'wl1_11ax=1; wl1_nmode_x=9',
}
print(f"\n[4] 底层命令映射:")
for mode, cmd in cmd_map.items():
    marker = "← 期望的 11a 命令" if mode == '11a' else ""
    print(f"  {mode:6} -> {cmd:35} {marker}")

print("\n" + "=" * 60)