# VVebo：iOS 15 主页修复 A

**用户已反馈：VVebo 15A 在本轮约定的 iPhone 13 Pro Max / iOS 15 / TrollStore 环境可以使用。**

此为用户真机反馈；刷新、翻页及其他页面尚未获得逐项结果。用户另外确认：同一个 15A 包在 iPhone 17 Pro Max 上仍无法打开或闪退。新机的具体签名/加载/运行失败原因尚未取得本版日志确认，先排查启动差异，显示适配随后处理。15A 的二进制与源码固定保留，后续显示适配使用独立测试包。

用户重新提供并确认原版 IPA 在上述环境可正常运行。文件与最初原包完全一致，不含先前补丁。先前面向新机的测试包均收到启动失败反馈，已撤回；本轮仅处理主页，显示适配待本轮稳定后再开展。

## 本轮测试文件

- [iOS 15 主页修复 A 测试 IPA](downloads/VVebo-3.3.31-iOS15-Profile-A.ipa)
- [安装步骤与验证范围](downloads/iOS15-Profile-A-说明.txt)
- [新补丁源码、构建与 ARM64 方法登记测试](downloads/VVProfile15-A-source.zip)
- [SHA-256 校验值](downloads/iOS15-Profile-A-SHA256.json)

在这台 iPhone 13 Pro Max 的 iOS 15 上使用原来可用的 TrollStore 安装。桌面名称应为 **VVebo 15A**，构建号 **4.1501**。无需先卸载原 App。先检查能否打开，能打开后关闭 QX 的 VVebo 专用重写，检查博主主页、刷新和翻页。

沿用原 Bundle ID，不能与原版并排安装。请保留原始 IPA，勿先删除本地 App 数据。

## 实现与检查

新模块为 `VVProfile15.framework`。通过系统 runtime block 捕获各个方法的原实现地址，使用原子锁保护的固定 C 数组登记具体类与方法，不在类对象上关联自定义方法指针对象。没有自定义 Objective-C 类、窗口或屏幕修改。

方法登记函数的真实 ARM64 机器码在 Unicorn 测试中覆盖了重复登记、继承类、不同类、方法缺失、原地址捕获和容量上限。该测试使用运行时 API 与 builder block 的替身，不验证 Apple block trampoline 或完整 Foundation 行为。

编译、ZIP、变更范围、原应用指令保留、Framework 信息、加载路径、段布局、构造入口、系统符号来源及代码页/资源签名结构检查通过。还确认新二进制没有 UIWindow 导入、窗口方法或旧补丁模块。

**验证边界：** 用户已反馈本轮基线版本可以使用；不扩大为所有功能、所有设备或全部系统均已验证。刷新、翻页及其他页面尚未分项确认，新机已收到启动失败反馈，尚未完成故障定位或显示适配。

接口映射依据用户确认有效的 [bin64 QX 脚本](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)。不引入外部代理服务，不记录鉴权数据。原始日志、用户签名后的 IPA、证书和设备信息不公开。
