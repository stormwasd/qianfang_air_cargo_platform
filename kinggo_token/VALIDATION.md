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
