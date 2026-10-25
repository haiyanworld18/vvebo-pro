# VVebo 3.3.31 补丁测试包

基于用户提供的 IPA 制作的非官方测试补丁。尚未完成 iOS 26 真机运行验证，不能保证可以启动、主页接口可用或黑边已消除。

## 下载

- [综合测试版 IPA：主页修复 + 窗口填充尝试](downloads/VVebo-3.3.31-ProfileFix-SceneFill-Test.ipa)
- [仅主页修复版 IPA](downloads/VVebo-3.3.31-ProfileFix.ipa)
- [使用说明](downloads/使用说明.txt)
- [补丁源码及封装/检查脚本](downloads/VVeboPatch-source.zip)
- [SHA-256 校验值](downloads/SHA256.json)

打开 IPA 文件页面后，点击 **Download raw file / 下载原始文件**。这两个包使用相同 Bundle ID，择一安装。

## 安装与测试

这些 IPA 使用临时 ad-hoc 代码签名，没有可供普通 iOS 安装使用的开发者或企业证书，需使用支持设备当前系统的工具重新签名安装。标准 TrollStore 的官方支持范围不包含 iOS 26。

不要先卸载原 App，以免丢失本地数据。测试内置主页修复时，暂时关闭 QX 中 VVebo 专用重写。优先测试博主主页、下拉刷新与向下翻页，再检查首页、评论及键盘；若综合版布局异常，可回退到仅主页修复版或原始 IPA。

## 修改范围

主页补丁参考用户提供并确认有效的 [bin64 Quantumult X 脚本](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)：切换为 `profile/statuses/tab` 接口、转换翻页参数、补充博主容器标识，并将卡片响应转换成 VVebo 原有微博列表结构。它在本地应用内处理，不引入新的代理服务器或记录鉴权信息。

综合版额外尝试让主窗口填满系统提供的场景区域，不伪造物理分辨率或 SDK 版本；若黑边来自系统兼容显示模式，该尝试可能无效。

## 已完成的检查与限制

补丁已通过 arm64 iOS 交叉编译及 ZIP、加载命令、依赖绑定、启动入口、代码页和资源签名结构检查。原 App 指令代码、身份和原有权限声明保留。QX 参考算法使用合成数据验证。

Linux 云环境无法启动 UIKit 应用。没有完成真机启动、在线接口、翻页、黑边或正式签名验证。结构检查通过不等于功能修复已完成。
