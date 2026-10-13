# Kinggo oOr6SIhu（Python 3.10）

这是已验证的 Node `generate.cjs` 和 `replay-offline.cjs` 的 Python 移植。独立目录可直接导入，不需要 Node.js。纯 Python 生成复用项目已有的 `cryptography==41.0.7`；从 HAR 提取配置使用新增的 `playwright==1.55.0`，在独立无界面 Edge 中执行 HAR 内的原站脚本。

## 安装与首次使用

以下命令在项目根目录执行，使用项目的 Python 3.10 环境：

```powershell
cd D:\Personal\qianfang_air_cargo_platform
python -m pip install -r requirements.txt
```

Windows 已安装 Edge 时无需安装 Playwright 浏览器。仅验证此模块也可安装两个依赖：

```powershell
python -m pip install cryptography==41.0.7 playwright==1.55.0
```

1. 在 Edge 登录 Kinggo，打开 F12 → Network，保留日志后刷新 `/main`，让目标接口出现。
2. 导出**包含响应内容**的 HAR。文件需包含 `/main`、页面加载的两段保护脚本和带 `oOr6SIhu` 的请求。只有请求列表、缺少脚本响应内容的 HAR 不够。
3. 提取该次页面的配置（不需要手工抄 AES 密钥等字段）：

```powershell
python -m kinggo_token extract "C:\Users\17658\Pictures\www.kinggo.com_1.har" /awb/sms_alert/getCountSms --method POST --output kinggo_token/config-from-har.json
```

4. 生成新参数：

```powershell
python -m kinggo_token generate /awb/sms_alert/getCountSms --config kinggo_token/config-from-har.json
```

输出的 `value` 是 `oOr6SIhu` 的值，`url` 是已添加该参数的完整 URL。每次调用自动使用当前毫秒时间和新的随机数。

## 项目代码中调用

```python
from pathlib import Path
from kinggo_token import generate, load_config

config_file = Path(__file__).resolve().parent / "kinggo_token" / "config-from-har.json"
config = load_config(config_file)  # 在项目根目录的调用文件中，加载一次即可
result = generate("/awb/sms_alert/getCountSms", config)
token = result["value"]
request_url = result["url"]
```

`generate(url, config)` 的两个必填入参：

| 入参 | 含义 |
| --- | --- |
| `url` | 实际请求的路径和查询参数，例如 `/awb/sms_alert/getCountSms`，或 `https://www.kinggo.com/...`。查询参数也参与计算；传入已有 token 会替换它。 |
| `config` | `load_config(...)` 加载的字典，包含该次页面的密钥、字母表、challenge、context 和状态字段。兼容 Node 提取的配置 JSON。 |

返回字典包括 `parameter`、`value`、`url`、`payloadHex`，与 Node 输出字段一致。通常不要指定时间和随机数；`timestamp_ms`、`random_high` 等可选参数用于复现和测试。

实际请求仍需使用对应有效登录会话的 Cookie 及接口所需请求头。配置文件不是登录 Cookie；本模块生成参数，不维护登录或发送业务请求。刷新或重新登录后，如果页面下发配置变化，重新导出 HAR 并提取配置。不要把测试样本的配置长期当作生产配置。

FastAPI 等异步代码可直接提取配置：

```python
from kinggo_token.har import replay_offline

async def extract_config(har_path: str):
    result = await replay_offline(har_path, "/awb/sms_alert/getCountSms", method="POST")
    return result["config"]
```

提取过程所有 HTTP 请求均由本地拦截返回，不使用正在打开的 Edge 会话，也不向 Kinggo 发出业务请求。HAR 脚本会在独立浏览器中执行；`probe.js` 是随模块提供的浏览器端探针，不依赖 Node。

## 校验与其他命令

```powershell
# 当前配置逐字复现此 HAR 的全部参数
python -m kinggo_token verify "C:\Users\17658\Pictures\www.kinggo.com_1.har" --config kinggo_token/config-from-har.json

# 解密查看某个参数
python -m kinggo_token decode "实际的oOr6SIhu值" --config kinggo_token/config-from-har.json

# 无浏览器、无 HAR 的 Node 对照向量测试
python -m unittest kinggo_token.tests.test_generator -v

# 完整离线提取和原脚本生成对照测试（可配置多份 HAR）
$env:KINGGO_TEST_HARS='C:\Users\17658\Pictures\www.kinggo.com.har;C:\Users\17658\Pictures\www.kinggo.com_1.har'
python -m unittest kinggo_token.tests.test_har -v
```

Linux/服务器没有 Edge 时，另行安装浏览器及系统依赖：

```bash
python -m playwright install --with-deps chromium
python -m kinggo_token extract capture.har /awb/sms_alert/getCountSms --browser chromium
```

API 使用 `channel=None` 选择 Playwright Chromium。自定义 Edge 路径可用 CLI `--executable-path`、API `executable_path` 或环境变量 `EDGE_EXECUTABLE`。

## 已验证的范围

纯 Python 构造器覆盖与已验证 Node 相同的分支：**空请求体、普通 ASCII URL 的请求**。它不会把 JSON/表单请求体作为已验证输入；含百分号编码或非 ASCII 的 URL 会明确报错。带请求体或复杂 URL 应使用原脚本离线重放，并按真实请求头、页面及浏览器状态验证，不能直接假定普通分支适用。`extract --body '原始请求体'` 支持传给原脚本，纯 `generate` 不接收 body。

流程为：请求摘要 CRC32 → 二进制 payload → 前 16 字节与 challenge 异或 → AES-128-CBC（零 IV、PKCS7）→ 封装 → CRC32 → 自定义 Base64。时间、随机数和页面配置都会影响最终值。

Python 3.10 的验证结果见 [VALIDATION.md](VALIDATION.md)。测试向量由实际 Node 实现生成；运行配置和 HAR 默认忽略，不提交到 Git。网站更改算法结构时，提取器可能需要更新；配置只在解密和重新编码通过后保存。
