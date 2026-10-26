# 原生玻璃材质实验 A

本实验以用户确认可用的 G IPA 为唯一底包，产物为 `VVebo-3.3.31-Glass-A.ipa`，桌面名称 **VVebo 玻璃A**，构建号 **4.1901**。不包含失败的会员实验、图片调度实验或首次云等待页的指令修改；正式维护构建配置保持 1.0.1。

## 范围与实现

- iOS 26 上动态查找公开的 `UIGlassEffect`，调用 `effectWithStyle:0`，使用 regular 材质。没有引用新的硬绑定类、私有 API 或手写折射滤镜。
- 仅在 `_TtC5VVebo8BlurView` 位于 `_TtC5VVebo11BaseBarView` 后代时，替换它已有的 `UIVisualEffectView` 中的 `UIBlurEffect`。底栏 Tabbar、用户栏 UserBarView 和导航栏 NavigationBarView 均继承 BaseBarView；仅这些控件中实际采用该 BlurView 的背景会改变。
- G 中 BlurView 将 UIVisualEffectView 放在一个自有 UIView 容器内，因此检查浅层子视图，不进入 UIKit 的效果内部视图或嵌套 BlurView。跳过 vibrancy 效果。每次检查最多 32 个节点。
- 只接管 BlurView 自有的 `layoutSubviews` 和 `updateAppStyle:`，先调用精确保存的原始 IMP，再应用材质。不改手势、触摸、尺寸、裁剪、图标、文字和控制器。
- 材质已存在时不重复创建；深浅色更新后跟随原视图的新状态重新应用。系统“降低透明度”开启时保留/恢复原效果。这里不新增通知监听，设置变化在后续布局或原主题回调时生效。
- 模块构造函数仅向主队列提交一次安装，避开加载器回调内的 UIKit/Swift 初始化。安装后只做一次有界的已有窗口检查，不加轮询、网络、磁盘缓存或逐帧刷新。
- iOS 26 以下、目标类/API 不存在、Bundle ID 不符时不安装。框架最低系统版本保持 14.0。

第一版不承诺所有弹出菜单或整个 App 的动画都呈现玻璃效果；它不是使用 iOS 26 SDK 重编译原应用，也不会将原 SDK 兼容声明改成 26 来触发未知布局变更。

## 构建

需要 Zig 0.13.0、ld64.lld 19.1.7 和 Python 3。头文件仅声明所用公开 API，链接 stub 明确记录真实系统提供方。

```bash
ZIG_BIN=/path/to/zig LD64_LLD_BIN=/path/to/ld64.lld bash release/glass/build.sh
python3 release/glass/package_glass.py /path/to/G.ipa /tmp/vvebo-glass-native/VVGlass /tmp/vvebo-glass-package
```

模块先以 ad-hoc 签名打包，整个 IPA 仍需用全能签的有效证书完整重签，包含嵌套框架。保留原应用 Bundle ID；覆盖安装，无需先卸载或清除数据。云同步保持 G 的关闭状态。

主程序只在空白 Mach-O 头部空间增加该框架的弱加载声明，再刷新对应哈希。整个 `__text` 与 G 逐字节一致，所有原框架、资源和权限保持原样。`macho_support.py` 复用既有兼容包的 ad-hoc 签名逻辑，仅用于新增框架，不重写主程序指令。

## 检查及限制

```bash
PYTHONPATH=/path/to/unicorn python3 release/glass/test_native.py /tmp/vvebo-glass-native/VVGlass
```

测试执行编译产物的实际 ARM64，使用 ObjC/UIKit/系统版本的模型检查：类和系统版本门禁、仅目标背景修改、嵌套容器、vibrancy 排除、重复布局不重复生成、透明度选项恢复、原方法的接收者/selector/参数与调用次序、栈及寄存器恢复。打包校验检查代码/资源签名、嵌套框架 cdhash、全部主程序指令不变及网络框架相同。

模型无法验证真实 UIKit 的玻璃渲染、视图生命周期、完整登录、全能签信任、实际帧率和真机稳定性，因此仅作为测试版发布。此前会员实验通过离线测试但真机闪退的事实仍适用：这些检查不等于真机通过。

API 核对来源：[iOS 26 UIGlassEffect.h SDK 镜像](https://raw.githubusercontent.com/xybp888/iOS-SDKs/master/iPhoneOS26.0.sdk/System/Library/Frameworks/UIKit.framework/Headers/UIGlassEffect.h)，2026-10-26 读取。声明显示 UIGlassEffect 继承 UIVisualEffect，iOS 26 可用，公开 factory 为 `+effectWithStyle:`；此版不使用 interactive/tintColor 或玻璃融合容器。

## 回退

若启动或显示出现异常，用全能签重新签名并覆盖 G 原包。IPA 本身不写入任何会员、云同步或玻璃设置偏好；不要求先删除本地数据。
