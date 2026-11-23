# main 分支生产更新与 MySQL 整库替换

本文针对已有 Docker Compose 部署。命令在 Linux Bash 执行；生产地址、目录和现场容器信息未核实，先填实际值。不要直接更换已有 Compose 项目名、MySQL 镜像或数据卷。

## 1. 服务与外部依赖

| 部分 | 运行位置及发布要求 |
| --- | --- |
| FastAPI、RPA Worker、南航直连订舱 Worker、深航直连开单 Worker、各类同步/通知调度器 | 均在 `app` 中，由 `app/main.py` 启动；单容器、Uvicorn 单 Worker，不用 `--reload`，不需要另起 Celery |
| MySQL | `mysql`，当前编排基线为 MySQL 8.0.39，`mysql_data` 持久化；代码含 `SKIP LOCKED`，不能按 MySQL 5.7 部署 |
| 携程代理缓存、接口、采集器 | `ctrip-proxy-redis`、`ctrip-proxy-pool`、`ctrip-proxy-scheduler`；Redis 仅供代理池使用，非业务队列 |
| KingGo 签名浏览器 | 已在 Dockerfile 安装 Playwright Chromium 和系统库，构建时执行浏览器启动检查；不是独立服务 |
| RPA 平台、Windows 登录/打印机器人、文件同步/共享 | 外部设施，不包含在 Compose 内；保留生产凭据、机器人、队列和原文件同步配置 |
| 航司、携程、高德、企业微信接口 | 外部服务，需生产网络、权限、有效 Token/HAR 和对应开关；不部署本地 Postman 模拟器 |
| 前端、Nginx/域名/HTTPS | 本仓库只提供后端；沿用另行部署的前端及反向代理 |

`documents`、`generated_files`、`static/uploads` 均绑定宿主机目录。数据库 SQL 不包含这些文件。数据库内的附件/单据路径必须能在生产目录找到对应文件。

## 2. 先盘点、备份，再更新代码和构建

进入实际生产项目目录，检查：

```bash
git status --short --branch
git remote -v
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker inspect qianfang-app --format '{{index .Config.Labels "com.docker.compose.project"}}'
docker inspect qianfang-app --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
docker inspect qianfang-app --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
docker inspect qianfang-mysql --format '{{.Config.Image}}'
docker inspect qianfang-mysql --format '{{range .Mounts}}{{println .Name .Source "->" .Destination}}{{end}}'
```

确认线上确实使用这里的容器名，否则后续替换为实际名称。若 MySQL 仍为 5.7，先另行制定升级方案，不把新版镜像直接接到原数据卷。

在项目目录外建立备份目录，保存生产 `.env`、Compose 主文件/override、旧代码版本、旧应用镜像和运行目录。数据库最终备份在停止写入后做（第 4 节）。备份不能放进公开共享目录。

```bash
umask 077
RELEASE_STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/qianfang_release_backups/$RELEASE_STAMP"
mkdir -p "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/old-commit.txt"
cp -p .env docker-compose.yml "$BACKUP_DIR/"
# 若有 override/额外 --env-file，也分别备份。
OLD_IMAGE_ID=$(docker inspect --format '{{.Image}}' qianfang-app)
docker image tag "$OLD_IMAGE_ID" "qianfang-app:rollback-$RELEASE_STAMP"
```

工作区干净时拉 main；有线上改动先逐项保存、比较，尤其是 `app/config.py`、Compose、模板。不要强制 reset 或覆盖整个目录。

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

使用原项目名、原文件组合。下面是只有一个编排文件时的例子；从前面的标签取得项目名，将 `实际原项目名` 替换后执行。有 override 则追加原 `-f`。仅有 V1 时将 `docker compose` 改为 `docker-compose`，并确认支持配置。

```bash
DC=(docker compose -p 实际原项目名 -f docker-compose.yml)
"${DC[@]}" config --quiet
"${DC[@]}" config --services
"${DC[@]}" build app
```

`config --quiet` 只做校验，不将含密码的最终配置输出到终端。构建完成前让旧服务继续运行。构建必须包括 Chromium 下载和启动检查。

逐项核对生产 `.env`（不直接复制测试 `.env`）：

```dotenv
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=qianfang_air_cargo
# MYSQL_USER/MYSQL_PASSWORD 使用生产实例现有账号。
# MYSQL_ROOT_PASSWORD 不会修改已初始化数据卷中的实际 root 密码。
DEBUG=False
RPA_GENERATED_FILES_DIR=/app/generated_files
SHENZHEN_AIR_KINGGO_HAR_PATH=/app/generated_files/www.kinggo.com.har
SHENZHEN_AIR_KINGGO_BROWSER=chromium
CTRIP_PROXY_ENABLED=True
CTRIP_PROXY_POOL_URL=http://ctrip-proxy-pool:5010
```

`MYSQL_HOST=mysql` 仅适用于 MySQL 和 app 确实在同一 Compose 网络时。保留原生产 `SECRET_KEY`、应用端口、RPA/航司身份及打印机器人的 Windows 路径；移除不适用于容器的 `SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH`、`EDGE_EXECUTABLE` 覆盖，不填宿主机 Chrome 路径。不要覆盖镜像的 `PLAYWRIGHT_BROWSERS_PATH=/opt/playwright`。HAR 必须含 Cookie、`/main` 和保护脚本响应，并保持有效；Docker 安装浏览器不等于自动登录。

## 3. 测试库导出：在 MySQL 容器的 shell 中执行

先确认应用实际连接的业务库名、源和目标 MySQL 版本。本文示例均使用 `qianfang_air_cargo`；实际不同就逐处替换。导出整个业务库（表结构、全部数据、视图、触发器、例程和事件），不是导出 MySQL 系统用户及权限。

2026-11-23 只读核实：192.168.0.24 上测试 MySQL 容器名为 `qianfang_air_cargo_platform_mysql_mysql`，镜像/服务版本为 8.0.39，映射宿主机端口 43306，业务库为 `qianfang_air_cargo`。库中 48 张表均为 InnoDB，当前模型所需的 47 张表及字段均存在。导出时仍应重新确认现场信息。

最终快照前，停止测试应用及其他写库进程，排空已派发的机器人任务；直到切换完成不要恢复同账号测试自动任务。192.168.0.24 上本项目目前为原生 Conda/Uvicorn，不能用 `docker compose stop app` 代替停止那个真实进程。使用原终端/进程管理器正常停止，勿影响同机其他项目。

在测试宿主机：

```bash
docker exec -it qianfang_air_cargo_platform_mysql_mysql bash
```

以下在容器 shell 执行，`-p` 会交互提示输入实际 MySQL root 密码：

```bash
umask 077
mysql -u root -p -e 'SELECT VERSION(), @@server_uuid; SHOW CREATE DATABASE qianfang_air_cargo;'
mysqldump -u root -p \
  --single-transaction --quick \
  --routines --triggers --events --hex-blob \
  --default-character-set=utf8mb4 --no-tablespaces \
  --set-gtid-purged=OFF \
  --result-file=/tmp/qianfang_test_full.sql \
  qianfang_air_cargo
# 紧接着检查退出码，必须为 0。
echo $?
test -s /tmp/qianfang_test_full.sql
tail -n 5 /tmp/qianfang_test_full.sql
exit
```

不要加 `--all-databases`，避免替换生产系统库、用户和权限；也不要加 `--databases`，便于按目标库名导入。检查视图/例程的显式库名引用和 DEFINER 账号；目标需相应对象权限，不能盲目删除 DEFINER。`--single-transaction` 保障 InnoDB 快照，不保证并发写入的非事务表；导出期间不做 DDL。若源库有事件，先核实源/目标 `event_scheduler`，防止恢复事件后提前写入。

回到测试宿主机，复制备份到容器外并校验：

```bash
umask 077
mkdir -p "$HOME/qianfang_db_transfer"
docker cp qianfang_air_cargo_platform_mysql_mysql:/tmp/qianfang_test_full.sql "$HOME/qianfang_db_transfer/"
chmod 600 "$HOME/qianfang_db_transfer/qianfang_test_full.sql"
cd "$HOME/qianfang_db_transfer"
sha256sum qianfang_test_full.sql > qianfang_test_full.sql.sha256
```

将这两个文件通过现有安全传输方式送到生产宿主机的受限目录；生产执行 `sha256sum -c qianfang_test_full.sql.sha256`。源 SQL 包含业务数据、密码哈希和会话，勿提交 Git。至少在隔离空库预演恢复，并保存源库表清单、逐表准确 `COUNT(*)`；不能只看文件非空就认定可恢复。

## 4. 生产维护窗口：停止写入并备份原库

阻止用户写入、让正在执行的航司任务收尾，停止真实生产应用及其他写库者（包括外部同步和机器人回写）；不要强杀仍在开单的任务。

```bash
"${DC[@]}" stop app
docker exec -it qianfang-mysql bash
```

在生产 MySQL 容器 shell：

```bash
umask 077
mysql -u root -p -e 'SELECT VERSION(), @@server_uuid; SHOW CREATE DATABASE qianfang_air_cargo;'
mysqldump -u root -p \
  --single-transaction --quick --routines --triggers --events --hex-blob \
  --default-character-set=utf8mb4 --no-tablespaces --set-gtid-purged=OFF \
  --result-file=/tmp/qianfang_prod_before.sql \
  qianfang_air_cargo
echo $?
test -s /tmp/qianfang_prod_before.sql
tail -n 5 /tmp/qianfang_prod_before.sql
exit
```

必须确认导出成功，再在宿主机保存到容器外：

```bash
docker cp qianfang-mysql:/tmp/qianfang_prod_before.sql "$BACKUP_DIR/"
chmod 600 "$BACKUP_DIR/qianfang_prod_before.sql"
sha256sum "$BACKUP_DIR/qianfang_prod_before.sql" > "$BACKUP_DIR/qianfang_prod_before.sql.sha256"
```

维护窗口内还应备份原 `generated_files`、`documents` 和上传附件，保留权限、软链接及同步路径。旧 app 如没有 `/app/static/uploads` 持久挂载，先 `docker cp qianfang-app:/app/static/uploads "$BACKUP_DIR/uploads-from-old-container"`，核实备份内容，再追加迁入宿主机 `static/uploads/`，同名冲突先比较，不能用空目录挂载后把唯一副本遮住。

## 5. 生产 MySQL 容器内整库替换

此操作明确删除这一个生产业务库并恢复测试快照，生产独有数据不会保留。先确认第 4 节的备份已复制出容器且可恢复。不要删除 MySQL 容器或数据卷。

生产宿主机，在 SQL 所在目录执行：

```bash
sha256sum -c qianfang_test_full.sql.sha256
docker cp qianfang_test_full.sql qianfang-mysql:/tmp/qianfang_test_full.sql
docker exec -it qianfang-mysql bash
```

容器 shell：

```bash
mysql -u root -p
```

在 **mysql 提示符** 中，先确认库名，然后执行下列替换。字符集/排序规则应沿用第 3 节源库 `SHOW CREATE DATABASE` 的实际值，下面仅为项目默认示例：

```sql
SHOW DATABASES;
DROP DATABASE `qianfang_air_cargo`;
CREATE DATABASE `qianfang_air_cargo`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

回到 **容器 shell** 导入，不能把 mysqldump 或 shell 重定向写在 mysql 提示符里：

```bash
mysql -u root -p --default-character-set=utf8mb4 \
  qianfang_air_cargo < /tmp/qianfang_test_full.sql
echo $?
# 必须为 0；有错误立即停在此处，不加 --force，不启动 app。
mysql -u root -p qianfang_air_cargo
```

mysql 提示符中先检查：

```sql
SHOW TABLES;
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM waybills;
SELECT COUNT(*) FROM bookings;
SELECT status, COUNT(*) FROM rpa_tasks GROUP BY status;
SELECT status, COUNT(*) FROM china_southern_air_booking_tasks GROUP BY status;
SELECT status, COUNT(*) FROM shenzhen_air_direct_waybill_tasks GROUP BY status;
EXIT;
```

再逐表核对源库清单及准确行数、视图、触发器、事件、例程、关键主键与附件路径，并核对应用账号的目标库授权。不要只用 `information_schema.TABLES.TABLE_ROWS` 的估算行数验收。整库 SQL 不复制源 MySQL root 密码，生产仍使用原 MySQL 用户密码。

复制库会连同测试账号、财务数据、机器人配置、航司 Token、未执行/执行中队列及调度状态一起带过来。2026-11-23 的只读检查发现 22 条 pending RPA 任务、1 条 running RPA 任务和 10 条 unknown 深航开单任务；这是当时快照，切换时须重新查询、与航司/机器人侧逐项核查，避免测试开单任务在生产重放。不要全表清队列或无差别修改状态。`RPA_QUEUE_ENABLED=False` 不会关闭所有直连 Worker。若先做禁用自动任务的验收，至少分别关闭 RPA、南航直连订舱、深航直连开单、航班同步、货物类型同步和单号扫描开关，并核对两项深航 direct 调度的启动条件，不能把一个总开关当成所有后台任务的暂停开关。

项目启动的 `Base.metadata.create_all()` 只补缺表，不会给已有表补列。恢复的是当前 dev/test 的完整结构时不必盲目跑旧迁移；如发现结构落后，针对缺失项应用 `sql/`、`migrations/` 中相应脚本并验证。不要对已恢复业务库运行 `init_db.py`。

## 6. 启动和验收

退出 MySQL 容器，回到原生产项目目录和原 `DC` 配置。先启动新增的代理服务，再仅替换 app；保留原 MySQL 镜像、容器和卷：

```bash
"${DC[@]}" up -d ctrip-proxy-redis ctrip-proxy-pool ctrip-proxy-scheduler
# 先运行独立诊断，不启动 ASGI 和业务 Worker。
"${DC[@]}" run --rm --no-deps -T app python -m kinggo_token check-browser --browser chromium
"${DC[@]}" up -d --no-deps app
"${DC[@]}" ps
"${DC[@]}" logs --tail=150 app ctrip-proxy-pool ctrip-proxy-scheduler
"${DC[@]}" exec -T app python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10).status)'
"${DC[@]}" exec -T ctrip-proxy-pool python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:5010/count/", timeout=10).read().decode())'
```

浏览器 PASS 只证明能启动并执行 JS；`/health` 不查询数据库，代理 API 返回 200 也不保证有可用代理。还需核对登录和数据库查询、附件/单据、KingGo 当天同步成功日志、南航凭据、机器人 HAR/Token 刷新与文件同步、前端入口及按需选择的真实业务验收。不要用随意创建真实运单来探测服务。免费代理库存为 0 时需解决可用代理来源或明确调整回退策略。

出现导入错误时保持 app 停止，清空重建这个业务库后从完整备份重新恢复；MySQL 的整库导入不会整体事务回滚。回退必须同时还原旧数据库快照、对应运行文件和旧应用镜像/配置，不能只换旧代码。切换后的新增写入需要另行处理，不能直接丢弃。

禁止在此流程执行 `docker compose down -v`、删除/清理 MySQL 卷、`rsync --delete` 或覆盖生产 `.env`。保留备份，验收完成后再按实际留存要求清理容器内 `/tmp/` 的 SQL 副本。
