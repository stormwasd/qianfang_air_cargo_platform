# Kinggo oOr6SIhu（Python 3.10）

这是已验证的 Node `generate.cjs` 和 `replay-offline.cjs` 的 Python 移植。独立目录可直接导入，不需要 Node.js。纯 Python 生成复用项目已有的 `cryptography==41.0.7`；从 HAR 提取配置使用新增的 `playwright==1.55.0`，在独立无界面浏览器中执行 HAR 内的原站脚本。默认自动选择浏览器：Windows 使用 Edge，Linux/macOS 使用 Playwright Chromium。

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

## Ubuntu 服务器使用

纯命令行 Ubuntu VPS 可运行：提取器启用 `headless=True`，无需桌面、DISPLAY 或 Xvfb。仍需安装 Chromium 可执行文件及系统库。下面是主机直接部署的步骤；Docker 部署见后文。

在运行项目的同一个 Conda/虚拟环境、同一个系统用户下安装 Chromium。安装 pip 包不会自动下载浏览器；安装系统依赖时会请求 sudo 权限：

```bash
cd /home/lhj/Personal/Normal/qianfang_air_cargo_platform
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
python -m kinggo_token extract "generated_files/www.kinggo.com.har" "/awb/sms_alert/getCountSms" --method POST --browser chromium --output "kinggo_token/config-from-har.json"
python -m kinggo_token generate "/awb/sms_alert/getCountSms" --config "kinggo_token/config-from-har.json"
```

`generate` 输出的 `value` 就是 `oOr6SIhu`，`url` 是完整请求 URL。只打印参数值：

```bash
python -c 'from kinggo_token import generate, load_config; print(generate("/awb/sms_alert/getCountSms", load_config("kinggo_token/config-from-har.json"))["value"])'
```

更新代码后 Ubuntu 不加 `--browser` 也会自动选择 Chromium；显式使用 `--browser chromium` 同样兼容旧版本。Ubuntu 无需安装 Edge 或图形桌面。系统依赖已由管理员安装时，可仅执行 `python -m playwright install chromium` 下载当前用户的浏览器。管理员单独安装依赖可执行 `sudo /当前环境的绝对路径/bin/python -m playwright install-deps chromium`，然后由运行项目的用户执行下载命令。

API 默认 `channel="auto"`，也可显式使用 `channel=None` 选择 Playwright Chromium、`channel="msedge"` 选择 Edge。自定义路径可用 CLI `--executable-path`、API `executable_path` 或环境变量 `EDGE_EXECUTABLE`；显式路径优先于浏览器选择。

若提示浏览器未安装，请确认安装命令和运行命令使用的是同一 Python 环境及用户。浏览器启动失败会给出安装提示并保留旧配置。输入接口路径时，`/awb/sms_alert/getCountSms` 应完整写在一个参数中；不要在引号里的 `/` 后插入空格或换行。

### CentOS / 阿里云 VPS 部署

CentOS 主机使用项目现有 Docker Compose 方案，浏览器运行在 Debian 容器内，主机无需安装浏览器、桌面或 Playwright 系统依赖。Playwright 1.55 的 `install --with-deps` 适用于支持的 Ubuntu/Debian 系统，不应直接当作 CentOS 的安装方法。VPS 需已有可运行的 Docker/Compose 以及项目生产 `.env`。

进入项目根目录，一条命令完成应用镜像构建、启动及无界面浏览器检查（支持 `docker compose` 和 `docker-compose`）：

```bash
bash scripts/setup_kinggo.sh
```

首次构建需要下载 Python 依赖和 Chromium，后续构建利用 Docker 层缓存；下载失败会停止部署。主机直接使用 Conda 的用户也可在 Windows 上提取配置，将 JSON 复制到服务器后仅执行纯 Python `generate`，这时 CentOS 完全不需要浏览器。

Docker 部署：Dockerfile 在镜像构建阶段安装 Chromium 和系统依赖，浏览器位于 `/opt/playwright`，并执行启动检查。Compose 给应用容器启用 init 和 256 MB 共享内存。服务启动时不重复下载浏览器；运行时无需桌面。构建基础系统固定为 Playwright 1.55 支持的 Debian 12，保留原有 Python 3.11。

```bash
docker compose build app
docker compose up -d --no-deps app
docker compose exec app python -m kinggo_token check-browser --browser chromium
docker compose exec app python -m kinggo_token extract "generated_files/www.kinggo.com.har" "/awb/sms_alert/getCountSms" --method POST --browser chromium --output "generated_files/kinggo/config-from-har.json"
docker compose exec app python -c 'from kinggo_token import generate, load_config; print(generate("/awb/sms_alert/getCountSms", load_config("generated_files/kinggo/config-from-har.json"))["value"])'
```

Compose 场景配置写到已挂载的 `generated_files/kinggo/`，重建容器后仍保留。直接主机运行可继续使用 `kinggo_token/config-from-har.json`。本地 HAR 和会话配置已从 Docker 构建上下文排除，请将 HAR 放到主机挂载的 `generated_files/` 中。HAR 路径是普通文件名 `generated_files/www.kinggo.com.har`，不要粘贴 Markdown 链接形式。

单独检查部署环境：`python -m kinggo_token check-browser --browser chromium`。出现 `status: PASS` 表示浏览器成功启动并执行了 JavaScript；它不证明接口的登录会话或参数已被 Kinggo 服务器接受。提取配置还需 HAR 含 `/main` 和脚本响应内容。

## 已验证的范围

纯 Python 构造器覆盖与已验证 Node 相同的分支：**空请求体、普通 ASCII URL 的请求**。它不会把 JSON/表单请求体作为已验证输入；含百分号编码或非 ASCII 的 URL 会明确报错。带请求体或复杂 URL 应使用原脚本离线重放，并按真实请求头、页面及浏览器状态验证，不能直接假定普通分支适用。`extract --body '原始请求体'` 支持传给原脚本，纯 `generate` 不接收 body。

流程为：请求摘要 CRC32 → 二进制 payload → 前 16 字节与 challenge 异或 → AES-128-CBC（零 IV、PKCS7）→ 封装 → CRC32 → 自定义 Base64。时间、随机数和页面配置都会影响最终值。

Python 3.10 的验证结果见 [VALIDATION.md](VALIDATION.md)。测试向量由实际 Node 实现生成；运行配置和 HAR 默认忽略，不提交到 Git。网站更改算法结构时，提取器可能需要更新；配置只在解密和重新编码通过后保存。
