# 玻璃 D：新建原生背景与可见对照

产物 `VVebo-3.3.31-Glass-D.ipa`，桌面名称 **VVebo 玻璃D**，构建号 **4.1904**，固定用户确认可用的 G 为底包。用户要求在 A/B 无视觉变化、C 启动闪退后继续实现。C 保持撤回，其 SDK 声明方案不沿用。

## 新方案

A/B 在旧 UIVisualEffectView 上设置 UIGlassEffect；B 已在真机显示两次替换，但没有可见变化。D 测试不同的整合方式：直接以公开 UIGlassEffect clear 材质初始化一个新的 UIVisualEffectView，而非给旧实例更换 effect。

原 BlurView 位于 BaseBarView 内且不在嵌套 BlurButton 下时，找到其原 UIBlurEffect 视图，在同一容器的 index 0 插入新玻璃视图。复制原 frame、使用 G 的 flexible width/height mask，且每次原布局回调之后重新对齐；启用公开 capsuleConfiguration。原按钮、文字和触摸处理不改动。

原模糊视图的 effect 对象完全保留，保存其原 hidden 状态后隐藏。新视图通过关联对象复用，不在每次布局重复创建；其父视图由 UIKit 管理。系统降低透明度或离开目标范围时，移除新视图并还原旧视图的可见状态。原底色板沿用 B 的有界、结构识别方式暂时隐藏及恢复，不读取 Swift ivar 或偏好。

玻璃视图不接收触摸，因此本版不声称实现系统按钮的交互形变。clear 材质可能影响复杂背景上的前景可读性，仍需实机观察；它不是完整的全 App 界面重构。

## 真机视觉对照

主队列安装后约两秒，在原窗口上显示一次对照卡。八个色块构成重复图案，左右各四个完全相同；左侧新建 UIBlurEffect 对照，右侧新建 UIGlassEffect clear。两侧效果视图均使用同样的 frame 尺寸和胶囊形状。卡片及状态标签约十二秒后移除，不拦截触摸，不使用持续轮询或帧循环。

这提供的是待检查样例，文字“原生玻璃”及“已新建 N 处”不证明系统成功渲染。应观察样例与真实底栏，并反馈是否有视觉差异；只有样例变、底栏不变时，需进一步诊断原栏整合。模型无法替用户判断这个结果。

## 保持 G 主程序行为

- 主程序 LC_BUILD_VERSION 的 SDK 保持 18.0、最低版本保持 14.0，所有 __text 与 G 一致。
- 不写入 C 的 UIDesignRequiresCompatibility=false，不改原 DTSDK 构建元数据。
- 所有原框架、资源和原权限与 G 一致；增加 VVGlass 框架及弱加载声明、更新元数据/签名。
- 仅新增、无 Swift 代码的适配框架声明 SDK 26、最低 iOS 14。新系统类使用运行时查找，iOS 26 以下不创建玻璃。原 App 没有使用 SDK 26 重新编译。
- 不含会员、图片调度或首次云等待分支的实验补丁；云同步保持关闭。

## 构建与校验

Zig 0.13.0、ld64.lld 19.1.7、Python 3；执行 ARM64 模型另需 unicorn。头文件仅声明公开 API，链接 stub 明确系统提供方。

```bash
ZIG_BIN=/path/to/zig LD64_LLD_BIN=/path/to/ld64.lld bash release/glass/build.sh
python3 release/glass/package_glass.py /path/to/G.ipa /tmp/vvebo-glass-native/VVGlass /tmp/vvebo-glass-package
PYTHONPATH=/path/to/unicorn python3 release/glass/test_native.py /tmp/vvebo-glass-native/VVGlass
```

固定 G SHA256：`543f3c816da02bbef4ec6757058381114674e1abc0e3143ed7d87f47f472167c`。

模型运行编译产物的实际 ARM64，替身实现 ObjC/UIKit/Foundation。检查新视图创建、index 0 插入、frame ABI 与后续更新、旧对象不修改、重复布局复用、类型/范围排除、透明度回退、底色恢复、原回调参数/顺序、栈/寄存器，以及两种材质对照卡和定时清理。打包检查原程序 __text、原框架、SDK/权限、代码和资源哈希；源码包可重建相同框架与 IPA。

这些检查不证明真实 UIKit 的渲染、生命周期、签名信任或稳定性；不宣称帧率、加载速度改善。A/B 无可见效果、C 启动闪退均完整保留为历史反馈，没有因模型通过而覆盖这些事实。

## 使用

全能签完整重签（含新增框架）后覆盖安装，不先卸载或清数据。异常时完整重签并覆盖已验证 G。

API 核对来自 iOS 26 SDK 镜像的 UIGlassEffect.h 与 UICornerConfiguration.h：effectWithStyle 的 regular=0、clear=1；UICornerConfiguration 提供 capsuleConfiguration。采用公开 API，不使用私有玻璃滤镜或自绘边框冒充原生玻璃。
