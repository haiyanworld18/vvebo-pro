# 兼容补丁的维护与构建

这里包含我们维护的网络补丁源码、精确二进制补丁清单，以及统一后的正式版打包工具。VVebo 原应用没有源码；这里不冒充原应用的完整 Xcode 工程。

正式版以用户确认可用的 G 包为固定输入，不重新编译或修改运行时代码。工具会校验底包 SHA256，只更新应用名称、构建号、兼容补丁版本和相应的两个 CodeDirectory 元数据哈希。保留 G 的所有指令、主页框架、界面资源、显示兼容声明及云同步停用处理。

## 构建正式包

仅需 Python 3 标准库，在仓库根目录运行：

```bash
python3 release/build.py downloads/VVebo-3.3.31-iPhone17-Display-G.ipa /tmp/vvebo-release
```

版本、底包校验值和输出名称集中在 [config.json](config.json)。生成的 IPA 仍需用户用全能签和可用证书签名安装，内置 ad-hoc 哈希不代表 Apple 签名信任。

源码压缩包不重复收录 IPA；可另行下载[固定版本的 G 底包](https://raw.githubusercontent.com/haiyanworld18/vvebo-pro/e97e673/downloads/VVebo-3.3.31-iPhone17-Display-G.ipa)，构建命令的第一个参数可以使用该文件的任意本地路径。

独立复核：

```bash
python3 release/verify.py downloads/VVebo-3.3.31-iPhone17-Display-G.ipa /tmp/vvebo-release/VVebo-3.3.31-Compat-1.0.0.ipa
```

发布校验包括：ZIP 完整性、精确三个变更文件、整个主程序代码签名前缀相同、全部框架和资源相同、原权限与 Bundle ID 保留、仅两个签名特殊槽更新，以及所有代码页和资源哈希正确。检查使用显式异常，在 `python -O` 下同样生效。

## 网络补丁源码

[network/VVProfile15.m](network/VVProfile15.m) 是 G 使用的同一份主页修复源码，保留原始文件名，未在正式包中重新链接。它将指定博主主页接口请求和响应转换为旧客户端认识的格式，依据用户提供并验证的 [bin64 QX 方案](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)。不增加其他服务地址。

可选源码重建需要 Zig 0.13 和 LLVM 19.1.7 的标准 `ld64.lld`，不得用 Zig 自带 Mach-O 链接器替代。运行 `bash release/network/build.sh`，可通过 `ZIG_BIN`、`LD64_LLD_BIN` 指定工具路径。脚本会将重建结果与已验证框架的 SHA256 比较；不同则拒绝作为已验证结果。发布打包不会使用这个可选步骤的输出。

[patches/cloud-disabled.json](patches/cloud-disabled.json) 记录当前 34 处云功能停用指令；[patches/display.json](patches/display.json) 记录主程序的 SDK 显示兼容声明变更。它们是可审查的历史变更清单，不会在已修改的 G 上重复应用。

## 验证范围

用户已确认 E 的启动和主页正常，并确认 G 的显示正常。正式包仅更新打包元数据，未单独完成真机回归；其他功能和全部设备不因此视为通过测试。云同步仍停用；使用 SDK 18 兼容声明不代表原应用已用 SDK 18 重新编译。

构建工具将拒绝被重签、损坏或版本不符的底包。源码包不收录用户的签名包、证书、描述文件、崩溃日志或设备标识。
