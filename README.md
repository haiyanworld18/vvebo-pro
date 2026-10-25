# VVebo 兼容性修复

## 旧机已验证基线：15A

用户反馈 15A 在 iPhone 13 Pro Max / iOS 15 / TrollStore 可以使用。此包保持不变，刷新、翻页等尚未逐项确认。

- [15A IPA](downloads/VVebo-3.3.31-iOS15-Profile-A.ipa)
- [15A 使用说明](downloads/iOS15-Profile-A-说明.txt)
- [15A 源码和检查脚本](downloads/VVProfile15-A-source.zip)
- [15A 校验值](downloads/iOS15-Profile-A-SHA256.json)

## 新机 D：关闭已识别的云操作，异步返回错误

**用户反馈 D 打开后直接白屏，暂停安装推荐。** 白屏是否持续、是否随后退出，以及具体停留位置尚未确认。离线检查未覆盖原应用的完整启动与云错误后的界面流程，不能据此称修复成功。

 C 的最新日志确认构建号 4.1703，在主界面加载时进入另一条 CloudKit 查询并异常退出；此前跳过的账户查询已不在致命调用栈中。不能继续把这次故障归因于证书或主页重写。

- D 测试包仅保留用于诊断，已收到白屏反馈，不建议继续安装。
- [D 使用说明和限制](downloads/iPhone17-D-说明.txt)
- [D 源码、构建和检查脚本](downloads/VVebo-17D-source.zip)
- [D 校验值](downloads/iPhone17-D-SHA256.json)
- [D 精确补丁清单](downloads/iPhone17-D-patch-manifest.json)

用户已同意暂时关闭 iCloud 云功能。D 从 15A 构建，保留 6 处关闭默认云容器的处理，恢复 C 跳过的两个调用方，关闭目前识别出的 23 处查询/保存操作创建入口。22 处完成回调收到异步返回的普通 NSError，进入原应用的失败处理；另一处保存没有完成回调。不会伪造云查询成功或购买授权。原应用对错误的后续处理仍需真机确认。

主页修复继续使用 A 的同一份网络目标文件，新增错误回调辅助代码与其重新链接。保留原 Bundle ID 和权限声明，不新增清账号、删除本地数据的操作。云同步及相关云端账户资料功能不可用。程序仍含其他 CloudKit 对象和调用，不能称为彻底移除 CloudKit。本版未修改屏幕显示适配。

D 的标识为 **VVebo 17D**、构建号 **4.1704**。保留现有 App 和本地数据。先核对原程序在云恢复错误时跳过后续回调的行为，是否影响启动仍待确认；不直接把错误改成伪造的云成功。

离线检查通过：精确 5 个文件变化、51 处指令替换、代码区域范围、权限保留、代码页和资源哈希、框架段对齐；ARM64 执行检查覆盖调用参数、栈和寄存器、Swift 构造参数释放、异步回调和错误参数，以及原网络钩子的注册。测试中的运行时、Foundation、dispatch 和引用计数为替身。**这些不证明 iOS 签名信任、完整登录、重新启动或在线功能可用，需用户真机确认。**

## B / C 历史结果

B 在新机登录前可打开，登录后闪退；C 登录后仍闪退。两者只保留用于追踪，均不作为可用新机版本推荐。

- [B 说明](downloads/iPhone17-B-说明.txt) · [B 源码](downloads/VVebo-17B-source.zip)
- [C 说明](downloads/iPhone17-C-说明.txt) · [C 源码](downloads/VVebo-17C-source.zip)

主页转换依据用户确认有效的 [bin64 QX 脚本](https://raw.githubusercontent.com/bin64/Scripts/main/QuantumultX/vvebo.js)。原始日志、用户签名包、描述文件、证书和设备标识不公开。
