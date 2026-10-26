# 兼容补丁的维护与构建

这里包含我们维护的网络补丁源码、精确二进制补丁清单，以及统一后的正式版打包工具。VVebo 原应用没有源码；这里不冒充原应用的完整 Xcode 工程。

当前分支构建 1.0.2-rc.1 图片调度候选版，以用户确认可用的 G 包为固定输入，不重新编译原程序。工具校验底包 SHA256，按白名单应用首次登录界面和图片队列优先级这两处指令替换，并更新版本与签名哈希。正式版 1.0.1 的源码保留在 compat-v1.0.1 标签。

## 构建正式包

仅需 Python 3 标准库，在仓库根目录运行：

```bash
python3 release/build.py downloads/VVebo-3.3.31-iPhone17-Display-G.ipa /tmp/vvebo-release
```

版本、底包校验值和输出名称集中在 [config.json](config.json)。生成的 IPA 仍需用户用全能签和可用证书签名安装，内置 ad-hoc 哈希不代表 Apple 签名信任。

源码压缩包不重复收录 IPA；可另行下载[固定版本的 G 底包](https://raw.githubusercontent.com/haiyanworld18/vvebo-pro/e97e673/downloads/VVebo-3.3.31-iPhone17-Display-G.ipa)，构建命令的第一个参数可以使用该文件的任意本地路径。

独立复核：

```bash
python3 release/verify.py downloads/VVebo-3.3.31-iPhone17-Display-G.ipa /tmp/vvebo-release/VVebo-3.3.31-Compat-1.0.2-rc.1.ipa
```

发布校验包括：ZIP 完整性、精确三个变更文件、主程序代码签名前缀除白名单指令外完全相同、全部框架和资源相同、原权限与 Bundle ID 保留、仅两个签名特殊槽及补丁所在代码页哈希更新，以及所有代码页和资源哈希正确。检查使用显式异常，在 `python -O` 下同样生效。

## 首次登录界面修复

[startup-cloud-ui.json](patches/startup-cloud-ui.json) 记录 1.0.1 的界面指令替换：`0x17d3dc` 的 `tbz w19, #0, 0x10017d414` 改为 `nop`。原代码读取 `accountRestored` 后，false 会经尾调用进入创建“iCloud 同步中”界面的 `0x17c884`；新代码沿 `0x17d3e0` 走原普通登录路径。不会设置恢复完成、云成功或登录成功状态，原微博认证逻辑不变。

可选执行实际 ARM64 片段测试（需安装 unicorn）：

```bash
python3 release/tests/test_startup_ui_arm64.py /path/to/G.ipa /path/to/VVebo-3.3.31-Compat-1.0.1.ipa
```

测试对照原始 false 状态会进入云等待页，补丁状态会走普通登录；已恢复、有账号、有旧遮罩等分支保持原路由。检查 key 引用清理、栈、自身模型及偏好数据不变。系统方法使用替身，不执行完整 UIKit，不证明真机登录结果。

## 图片调度实验

[ui-and-image-priority.json](patches/ui-and-image-priority.json) 包含首次登录修复及 `0x289d0` 的唯一图片改动：`mov w2, #9` 改为 `mov w2, #25`。YYWebImageManager 的共享队列原本设置 NSQualityOfServiceBackground，候选版使用 NSQualityOfServiceUserInitiated，仍保留 respondsToSelector 可用性检查、异步队列、缓存接线及引用清理。没有改动并发数、图片 URL、清晰度或磁盘缓存策略。

```bash
python3 release/tests/test_image_queue_arm64.py /path/to/G.ipa /path/to/VVebo-3.3.31-Compat-1.0.2-rc.1.ipa
```

该测试执行实际 ARM64 初始化片段、对比 QoS 参数 9/25，并核对不支持 setter 时仍跳过设置，缓存/队列接线、引用收尾和栈保持一致。ObjC 方法使用替身，不测实际延迟、解码速度、耗电或滚动帧率。主程序和嵌入框架中未找到 preferredFramesPerSecond/frameInterval 的显式设置，原 Info.plist 的 CADisableMinimumFrameDurationOnPhone 已为 true；这不足以证明真实运行时没有帧率限制，候选版不宣称已解决高刷体验。

当前候选版保留 App Store 原恢复购买及收据处理代码，不写会员状态。已购用户的恢复表现仍需结合实际错误信息核对。

## 网络补丁源码

[network/VVProfile15.m](network/VVProfile15.m) 是 G 使用的同一份主页修复源码，保留原始文件名，未在正式包中重新链接。它将指定博主主页接口请求和响应转换为旧客户端认识的格式，依据用户提供并验证的 [bin64 QX 方案](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)。不增加其他服务地址。

可选源码重建需要 Zig 0.13 和 LLVM 19.1.7 的标准 `ld64.lld`，不得用 Zig 自带 Mach-O 链接器替代。运行 `bash release/network/build.sh`，可通过 `ZIG_BIN`、`LD64_LLD_BIN` 指定工具路径。脚本会将重建结果与已验证框架的 SHA256 比较；不同则拒绝作为已验证结果。发布打包不会使用这个可选步骤的输出。

[patches/cloud-disabled.json](patches/cloud-disabled.json) 记录当前 34 处云功能停用指令；[patches/display.json](patches/display.json) 记录主程序的 SDK 显示兼容声明变更。它们是可审查的历史变更清单，不会在已修改的 G 上重复应用。

## 验证范围

用户已确认 E 的启动和主页正常，并确认 G 的显示正常。1.0.1 新增的首次登录界面绕过尚待真机确认；其他功能和全部设备不因此视为通过测试。云同步仍停用；使用 SDK 18 兼容声明不代表原应用已用 SDK 18 重新编译。

构建工具将拒绝被重签、损坏或版本不符的底包。源码包不收录用户的签名包、证书、描述文件、崩溃日志或设备标识。
