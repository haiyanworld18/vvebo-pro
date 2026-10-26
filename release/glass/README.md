# 原生控件 E：第一阶段实现与验证

用户要求继续实现 iOS 26 原生液态玻璃效果。A/B/D 的背景材质尝试没有达到要求，C 启动闪退，这些结论不更改。E 改走系统控件配置路线，不宣称全 App 已完成或真机效果已成功。

产物 `VVebo-3.3.31-NativeControls-E.ipa`，桌面名称 **VVebo 控件E**，构建号 **4.2001**，固定 G 底包，原主程序 SDK 18、全部 __text 与原框架保持 G；只新增适配框架和加载声明。无 C 的 SDK 26 主程序声明，无会员修改，云同步仍关闭。新增框架自身使用 SDK 26 声明及运行时 API 检查。

## 原生 UIKit 控件

SDK 26 的 UIButtonConfiguration.h 明确提供：

- `+glassButtonConfiguration`
- `+prominentGlassButtonConfiguration`

UIButton.h 说明非 nil configuration 会启用配置型按钮行为；automaticallyUpdatesConfiguration 控制其状态自动更新。E 的样例使用真实 UIButton 和这两种系统配置，允许触摸并显式启用自动状态更新。不自绘折射、不模拟高光、不手写按压动画。UIKit 的真实显示及形变是否在当前旧 App 兼容环境生效，仍需真机验证。

E 的编译模块不再使用 UIBlurEffect、UIGlassEffect 或 effectWithStyle。API 依据为 iOS-SDKs 镜像 `iPhoneOS26.0.sdk/System/Library/Frameworks/UIKit.framework/Headers/UIButtonConfiguration.h` 和 `UIButton.h`（2026-10-26 核对）。

## 原按钮适配范围

仅处理 BaseBarView 后代中，原 configuration 为 nil、24~180 × 24~88 point、有图标（固有尺寸不超过 64 point）而无标题的 UIButton。保存原对象与 target/action 注册，配置使用原图标、capsule 圆角与零 contentInsets；没有事件复制/转发，没有重建原事件目标。文字/关注状态按钮、照片/大头像、已有 configuration、空内容、大图按钮区以及非目标页面跳过。

只在 UIButton 自有类上添加/替换 layoutSubviews 入口，先调用保存的原 IMP，再检查范围。设置配置前写入标志，防止 UIKit 布局重入造成重复配置。开启降低透明度或离开目标栏时，恢复原来的 nil configuration。

配置型 UIButton 会改变部分旧 inset/layout API 的行为，实际图标排布、状态变化、原操作仍需真机检查。不能把模型中的原事件数据保持等同于完整 UIKit 行为验证。

原 TabbarButton 继承 BlurButton，BlurButton 继承 UIControl，不是 UIButton。它不能直接使用上述配置，因此当前未迁移自定义底栏。原按钮计数为零不等于 API 失败，样例用于独立确认系统控件路线。不得将当前阶段描述成整个 VVebo 的液态玻璃适配完成。

## 可操作样例

启动约两秒后显示一个临时面板。两个系统 UIButton 分别使用 standard/prominent glass 配置，可以按住、滑出再松开。样例没有业务 target/action，不能触发登录、发布、购买或改账号数据。面板允许触摸，约二十秒后移除，不增加持续轮询。

原控件计数与样例标题只反映配置代码或预期类型，不证明真实折射、高光或按压形变。需要实机观察并反馈结果；当前云环境无 iOS UIKit 运行时，模型无法填补这一点。

## 构建与检查

Zig 0.13.0、ld64.lld 19.1.7、Python 3；模型另需 unicorn。公开 API 声明与系统符号提供方由本目录头文件、stub 记录。

```bash
ZIG_BIN=/path/to/zig LD64_LLD_BIN=/path/to/ld64.lld bash release/glass/build.sh
python3 release/glass/package_glass.py /path/to/G.ipa /tmp/vvebo-glass-native/VVGlass /tmp/vvebo-native-controls-package
PYTHONPATH=/path/to/unicorn python3 release/glass/test_native.py /tmp/vvebo-glass-native/VVGlass
```

模型执行编译 ARM64，替身实现 ObjC/UIKit/Foundation，检查系统/类型/范围门禁、原图标与原 frame/action 数据未被代码重写、配置参数及 Insets ABI、重入标志、重复布局、透明度恢复、原回调接收者/参数与顺序、样例配置/触摸/自动更新属性与清理。

打包校验原程序 __text、SDK、权限、原资源/网络框架相同，以及新框架、代码与资源签名哈希。源码压缩包应可重建相同框架与 IPA。这些检查不证明 UIKit 真正绘制或动画、签名信任、完整生命周期和稳定性。

## 安装

全能签完整重签（含新增框架）后覆盖，不先卸载/清数据。若发生异常，完整重签覆盖已验证的 G 原包回退。
