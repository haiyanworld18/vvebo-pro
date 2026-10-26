# C 已撤回：启动闪退

用户报告 C 打开即闪退。A 无视觉变化，B 执行两次替换仍无视觉变化，均未验证玻璃显示成功。停止推荐玻璃包，先覆盖回退至已验证 G。

主程序 SDK 26 声明及 UIDesignRequiresCompatibility=false 的对照实验未通过真机启动；尚无崩溃栈确定实际终止点，不能宣称仅凭差异已查明原因。当前脚本默认拒绝生成 C。下文历史构建命令要追加 `--reproduce-withdrawn-c` 才能进行审计复现，不应用来重新分发给用户试装。

原包、标签与校验结果保留用于追踪。离线检查通过不能抵消真机失败，未提供新玻璃候选版。正式构建配置未改动。

---

# 玻璃实验 C：系统兼容声明对照

当前产物 `VVebo-3.3.31-Glass-C.ipa`，桌面名称 **VVebo 玻璃C**，构建号 **4.1903**，以固定 G 底包构建。不含会员、图片队列或首次云等待分支的补丁。

用户报告 B 已显示两次背景替换，但无视觉变化。因此不能认定 B 已完成原生玻璃适配，也不能再把该现象归因于未加载模块。

C 的待验证假设是旧 SDK 声明导致 UIKit 保持旧应用兼容行为。具体仅改变主程序 LC_BUILD_VERSION 的 SDK 字段 18.0 -> 26.0，并设置公开的 UIDesignRequiresCompatibility=false；最低版本不变。原 DTSDK 构建元数据保留，**这不是用 SDK 26 重新编译，也不保证触发所需显示行为**。当前没有真机 UIKit 内部状态证明假设成立。

玻璃适配模块的全部 __text 与 B 相同，只将状态标签 B 改成 C。原主程序所有 __text 也与 G 相同。新 SDK 声明可能改变系统控件外观或布局，针对当前 iOS 26 设备单独测试，不承诺旧系统行为完全不受影响。构建/校验命令在下文；B 的材质处理逻辑与其模型限制仍适用于 C。

以下为 B 的实现依据与沿用范围，不是已解决的声明。

## A 的反馈与 B 的依据

用户报告 A 版没有玻璃视觉变化，未报告这次发生崩溃。不能据此断定 A 模块已经加载或成功替换材质。

在固定 G 程序中检查到：

- BlurView 的 ObjC ivar 名称包括 `blurView`、`containerView` 和 `$__lazy_storage_$_colorView`。这些名称仅用于静态调查，适配代码不通过 ivar 或 Swift 内存布局读写视图。
- `0x37ce54` 把 containerView 加入 BlurView，`0x37cf24` 把效果视图加入容器；`0x37d034` 在同一容器中再添加独立 colorView。后者无交互，其创建函数 `0x37cb4c` 返回一个普通 UIView。
- colorView 的动态配色经 `0x1c752c -> 0x1cad80`，常用分支调用 colorWithAlphaComponent，常数 `0x596c60` 为 0.8。A 只替换材质，保留了这层覆盖色。因此底色遮挡是一个有静态证据的待验证原因，而非已证实的唯一原因。

## B 的范围与行为

- iOS 26 动态查找公开 `UIGlassEffect`，调用 `effectWithStyle:0`（regular）。只在原 BlurView 位于 BaseBarView 内时处理其原有 UIBlurEffect；不进入嵌套 BlurButton，也不替换 vibrancy 或屏幕外的无关背景。
- 原始 `layoutSubviews` 与 `updateAppStyle:` 总是先按保存的原 IMP 调用，之后适配。保持其原接收者、selector 和通知参数。只修改已有背景效果，不改变原尺寸、手势或控制器。
- 每个容器存在本模块创建的玻璃时，只隐藏同容器内精确为 UIView、无交互、无子视图且有背景色的底色板。不会隐藏带内容的 UIView、UILabel、按钮或整个页面背景。保存原 hidden 状态；停用时恢复，不强制所有视图显示。
- 在公开 API 存在时，为效果视图设置 `UICornerConfiguration.capsuleConfiguration`，让玻璃知道其胶囊形状。保存原圆角配置；恢复材质时一起还原。不修改旧 SDK 的布局声明来强行切换全应用样式。
- 已经是本模块的玻璃时不重复创建。系统“降低透明度”开启时保留/恢复原模糊和底色；设置变化在后续布局、主题回调或重开 App 时体现。
- iOS 26 以下、目标类/API 不存在、Bundle ID 不符时不安装。原程序 __text、网络框架、原权限和资源与 G 一致，只有头部新增框架弱加载声明及新框架/签名。

### 测试状态提示

构造函数只排一次主线程安装。B 每次启动约两秒后再做一次有界窗口检查，显示一个五秒后移除的无交互 UILabel，不新增持续轮询或帧循环。

可能提示“玻璃 B：已执行 N 次背景替换”、系统降低透明度、应用标识变更、接口/目标栏未找到等。N 是替换操作次数，不是唯一控件数，更不代表 UIKit 已渲染成功。C 将提示中的版本标签改为 C；该提示用于真机诊断；没有提示也可能是模块未加载或当时无可用窗口，不能直接判定渲染器问题。

## 构建与检查

需要 Zig 0.13.0、ld64.lld 19.1.7、Python 3；ARM64 模型测试另需 unicorn。所有头文件仅声明公开系统 API，链接 stub 记录实际提供方。

```bash
ZIG_BIN=/path/to/zig LD64_LLD_BIN=/path/to/ld64.lld bash release/glass/build.sh
python3 release/glass/package_glass.py /path/to/G.ipa /tmp/vvebo-glass-native/VVGlass /tmp/vvebo-glass-package
PYTHONPATH=/path/to/unicorn python3 release/glass/test_native.py /tmp/vvebo-glass-native/VVGlass
```

固定 G 的 SHA256：`543f3c816da02bbef4ec6757058381114674e1abc0e3143ed7d87f47f472167c`。

模型执行编译产物的实际 ARM64，检查：门禁、目标范围、嵌套容器、按钮/vibrancy 排除、底色板识别与可逆处理、透明度回退、胶囊配置、重复布局复用、原方法参数/次序、栈和寄存器；另检查状态提示的 CGRect ABI、文字参数、无交互属性和移除。打包校验核对整个原 __text 相同、原框架相同、原权限相同、代码/资源及嵌套框架 cdhash。

UIKit、Foundation、ObjC runtime 在模型中由替身实现。这些检查不证明真实玻璃观感、完整生命周期、签名信任或真机稳定；不宣称性能或帧率改善。A 无视觉变化和会员实验闪退都说明，离线通过不能替代真机结果。

## 安装与回退

全能签完整重签，包括新增框架，覆盖安装；不先卸载或清数据。此包不新增会员或云授权，云同步仍关闭。异常时可完整重签并覆盖 G 原包回退。

API 依据：iOS 26 SDK 镜像的 [UIGlassEffect.h](https://raw.githubusercontent.com/xybp888/iOS-SDKs/master/iPhoneOS26.0.sdk/System/Library/Frameworks/UIKit.framework/Headers/UIGlassEffect.h) 与 [UICornerConfiguration.h](https://raw.githubusercontent.com/xybp888/iOS-SDKs/master/iPhoneOS26.0.sdk/System/Library/Frameworks/UIKit.framework/Headers/UICornerConfiguration.h)，2026-10-26 核对。只使用公开材质和胶囊配置，不使用私有滤镜或伪造折射。
