# Python 移植验证记录

验证日期：2026-10-13。使用独立的 Python 3.10.2 环境，`cryptography==41.0.7`、`playwright==1.55.0` 和本机 Microsoft Edge。

| 检查 | 结果 |
| --- | --- |
| 旧 HAR `www.kinggo.com.har` 的参数解密、重建、重新编码 | 8/8 逐字一致 |
| 新 HAR `www.kinggo.com_1.har` 的参数解密、重建、重新编码 | 6/6 逐字一致 |
| 实际 Node 实现生成的固定时间/随机数对照向量 | 12/12：参数、完整 URL 和 payload 全部一致 |
| Python + Edge 从两份 HAR 提取配置 | 两份均成功，支持不同混淆变量名 |
| 提取时原站脚本新生成的参数，由纯 Python 重新生成 | 两份均逐字一致 |
| HAR 包含无法按 UTF-8 解码的 base64 图片 | 不影响脚本提取 |
| 新参数生成、CRC32 损坏检测、错误配置、长度边界、非法输入 | 通过 |
| CLI extract → verify → generate → decode | 通过，verify 报告 6/6 |
| Python 编译检查、Git diff 空白检查 | 通过 |

执行 `python -m unittest discover -s kinggo_token/tests -v`，设置 `KINGGO_TEST_HARS` 为上述两份文件，7 项测试全部通过。`tests/reference_vectors.json` 由 Node 参考实现生成，未使用 Python 自行生成预期值。

用户已确认 Node 版本在线可用；本次验证重点为 Python 与该实现的字节兼容及独立提取流程，没有额外发送线上业务请求。空请求体、普通 ASCII URL 的范围与原 Node 构造器一致。在线使用应匹配有效登录会话、当前页面配置及实际请求内容。

本地 `config-from-har.json` 从 `www.kinggo.com_1.har` 提取并已验证。它仅代表该次页面配置；部署时需要替换为当前会话配置。原始 HAR 与生成配置不纳入 Git。

## Ubuntu 浏览器默认值修复（2026-10-13）

- 默认浏览器改为按平台选择：Windows Edge、Linux/macOS Playwright Chromium。CLI 与异步 API 均适用；显式浏览器、可执行文件路径和环境变量覆盖继续有效。
- 浏览器启动失败提供安装提示，以退出码 1 结束，保留已有配置；拒绝接口参数中的换行或制表符。
- Python 3.10.2 完整回归 12 项测试通过，包括 Windows/Linux/macOS 浏览器选择、CLI 传参和失败时保留配置，以及原有 14 个 HAR 样本、12 个 Node 对照向量、两份 HAR 的真实 Edge 提取。
- 另用本机 Chromium 执行真实 CLI 提取，新 HAR 全部 6/6 参数通过验证；故意指定不存在的可执行文件，确认给出清晰错误且不写入配置。
- 本次未连接用户的 Ubuntu 服务器。Linux 浏览器选择通过模拟平台验证；实际 Ubuntu 运行仍需在服务器当前 Python 环境及系统用户下安装 Chromium 和系统依赖。

## CentOS 部署接入（2026-10-14）

生产主机确认是 CentOS，部署采用项目现有 Docker Compose：在 Debian 12 镜像内安装 Chromium 和系统依赖，提供 `bash scripts/setup_kinggo.sh` 构建、启动并检查应用。增加 `check-browser` 无网络启动检查，HAR 和本地配置不进入镜像；容器配置保存到已挂载的 `generated_files/kinggo/`。

Python 3.10 回归 14 项通过，包含两份 HAR 提取；本机真实 Chromium 无界面检查通过。首次回归曾出现原脚本随机字段超出纯构造器范围的偶发结果，后续回归通过，该分支未修改生成算法。本地完整 Docker 构建在下载依赖阶段按用户要求中止，尚未完成镜像及 CentOS 服务器端验证；部署脚本和镜像构建会主动检查实际浏览器启动结果。
