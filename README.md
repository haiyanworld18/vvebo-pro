# VVebo 兼容维护版

**兼容补丁 1.0.0 · 原应用 3.3.31 · 构建号 4.1800**

以用户已验证的 G 版为基线，修复博主主页微博加载，并保留新机显示兼容处理。用户已确认 E 的启动与主页正常、G 的显示正常。正式包只整理发布信息，运行时代码与 G 相同；本包未单独完成真机回归。

[下载正式兼容版 IPA](https://raw.githubusercontent.com/haiyanworld18/vvebo-pro/compat-v1.0.0/downloads/VVebo-3.3.31-Compat-1.0.0.ipa)

## 安装

在全能签重新导入正式版，用当前可用证书签名并覆盖安装。桌面名称为 **VVebo**，无需先卸载或清除本地数据。适用验证环境为 iPhone 17 Pro Max / iOS 26；其他设备尚未逐项验证。

**iCloud 云同步仍关闭。** 当前签名配置没有原云容器授权，原设置中的云入口可能仍会显示，但功能不可用。主页修复和显示处理保留，不伪造云端成功或购买授权。显示处理沿用 G 的 SDK 兼容声明，并非使用新 SDK 重新编译原应用。

## 发布文件

- [使用说明](downloads/VVebo-Compat-1.0.0-说明.txt)
- [源码与构建工具](downloads/VVebo-Compat-1.0.0-source.zip)
- [SHA256 校验值](downloads/VVebo-Compat-1.0.0-SHA256.json)
- [精确差异与签名哈希校验结果](downloads/VVebo-Compat-1.0.0-verification.json)
- [构建复现与源码核对结果](downloads/VVebo-Compat-1.0.0-audit.json)
- [版本变更](CHANGELOG.md)

已核对：全部程序指令、加载声明、主页框架、界面资源及原权限与 G 一致；仅更新应用名称、构建号、补丁版本、测试标记和对应签名哈希。重复构建字节一致，主页框架源码可重建为 G 中的同一二进制。这些校验不代替证书信任、完整真机回归或全部在线功能验证。

## 维护与回退

[维护源码和构建方法](release/README.md)涵盖我们新增的补丁与打包工具；VVebo 原应用没有源码，本仓库不是其完整 Xcode 工程。发布标签为 `compat-v1.0.0`。

- [G 原包备份](downloads/VVebo-3.3.31-iPhone17-Display-G.ipa)：用户已确认显示正常，可重新签名覆盖回退。
- [15A 旧机基线](downloads/VVebo-3.3.31-iOS15-Profile-A.ipa)：用户确认在 iPhone 13 Pro Max / iOS 15 / TrollStore 可使用。
- [历史版本记录](HISTORY.md) · [云同步授权说明](downloads/iCloud-恢复可行性-说明.txt)

主页接口转换依据用户提供并确认有效的 [bin64 QX 脚本](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)。发布资料不包含用户的签名包、证书、描述文件、原始崩溃日志或设备标识。
