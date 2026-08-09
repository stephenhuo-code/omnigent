# Omnigent on Aliyun ECS

Runs the server on one ECS box: Postgres on a local volume, artifacts in OSS,
a nightly database dump to OSS. Configuration lives in this directory and is
pushed to the box over SSH, so the machine can be rebuilt from the repository.

Secrets never enter the repository. `.env` exists only on the box, and
`scripts/sync.sh` excludes it.

```
你的 Mac                        ECS (华东1 杭州)                    OSS
  repo ──sync.sh(rsync)──▶  /opt/omniagent                    artifacts/
                             ├── docker-compose.yaml   ──写──▶  backup/
                             ├── .env  (仅存于此)
                             ├── postgres (本地卷)
                             └── omnigent server :8000
                                      ▲
  omniagent host ───────出站 WebSocket ┘
```

## 为什么数据库不放 OSS

Postgres 要求 POSIX 语义：`fsync` 顺序、文件锁、页内随机写、原子 rename。对象
存储一样都不提供。用 ossfs 之类挂载「看起来能跑」，但崩溃时会静默损坏，而且
往往几周后才发现——那时备份也轮换掉了。所以数据库留在本地卷，持久性由每日
`pg_dump` 到 OSS 保证。

artifacts 相反：写一次读多次的整体文件，无事务、无随机写，正是对象存储的适用
场景，而且会无限增长，不该占 ECS 磁盘。

---

## 一次性准备

### 1. OSS

控制台建 bucket：

| 项 | 值 |
|---|---|
| 地域 | 华东1（杭州）——与 ECS、ACR 同地域才能走内网 |
| 名称 | 全局唯一，如 `omnigent-<后缀>` |
| 读写权限 | **私有** |
| 版本控制 | 建议开启，误删可恢复 |

一个 bucket，两个前缀：`artifacts/` 由应用写，`backup/` 由备份脚本写。

建 RAM 用户（仅编程访问），附加自定义策略，权限收敛到这两个前缀：

```json
{
  "Version": "1",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["oss:GetObject","oss:PutObject","oss:DeleteObject","oss:AbortMultipartUpload"],
      "Resource": ["acs:oss:*:*:<bucket>/artifacts/*","acs:oss:*:*:<bucket>/backup/*"] },
    { "Effect": "Allow",
      "Action": ["oss:ListObjects"],
      "Resource": ["acs:oss:*:*:<bucket>"],
      "Condition": { "StringLike": { "oss:Prefix": ["artifacts/*","backup/*"] } } }
  ]
}
```

生成 AccessKey，**只在创建时显示一次**。

> ECS 实例 RAM 角色对 artifacts **无效**：artifact store 走 boto3 的标准凭据链，
> 只认 AWS 格式，读不到阿里云实例元数据。必须用 AccessKey。

### 2. ECS

```bash
curl -fsSL https://get.docker.com | sh -s -- --mirror Aliyun
systemctl enable --now docker
docker compose version          # 必须有 compose 插件

# ossutil，备份脚本依赖
curl -fL -o /usr/local/bin/ossutil \
  https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
# 下载源是个 OSS bucket，版本号写错会返回一个 XML 错误页而不是 404 的空响应。
# 不校验就 chmod +x 的话，执行时会报 "syntax error near unexpected token"。
file /usr/local/bin/ossutil | grep -q ELF \
  || { echo "下载的不是二进制，检查 URL"; head -c 200 /usr/local/bin/ossutil; }
chmod +x /usr/local/bin/ossutil
ossutil version
```

配置凭据。**用交互式的 `ossutil config` 不带参数**，密钥就不会进入
`~/.bash_history`：

```bash
ossutil config
#   endpoint          : oss-cn-hangzhou-internal.aliyuncs.com
#   accessKeyID       : <粘贴>
#   accessKeySecret   : <粘贴>
#   stsToken          : 留空
```

安全组入方向开 **8000，来源限定为你的出口 IP**。

> 现阶段是明文 HTTP 直接暴露在公网 IP 上——密码、会话 cookie、host 的
> WebSocket 全都不加密。**安全组是唯一的防线**，不要放开到 `0.0.0.0/0`，
> 也不要在接入 HTTPS 之前放真实敏感数据。

---

## 部署

```bash
# 本机
./scripts/sync.sh root@<ECS IP>

# ECS 上
cd /opt/omniagent
./scripts/bootstrap.sh              # 生成密钥，建 .env 骨架
vi .env                             # 填镜像地址、BASE_URL、管理员密码、AccessKey
docker login <ACR VPC 地址> -u <账号名>
./scripts/deploy.sh
```

`deploy.sh` 会等到 `/health` 真的返回才算成功，否则打印最近 50 行日志并非零退出。

浏览器打开 `http://<ECS IP>:8000`，用 `admin` + 你设的密码登录。

## 日常操作

```bash
./scripts/deploy.sh                 # 改了 .env 或想拉新镜像，重跑即可（幂等）
docker compose logs -f omnigent
docker compose ps
```

改配置的正确姿势是**改仓库里的文件再 sync**，不要直接在服务器上编辑——那样
下次 sync 会被 `--delete` 覆盖掉，环境也不再可复现。`.env` 是唯一的例外。

## 备份

```bash
./scripts/backup.sh                 # 手动跑一次，确认能用

# 装定时任务
cp systemd/omnigent-backup.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now omnigent-backup.timer
systemctl list-timers | grep omnigent
```

**恢复演练不能跳。** 没验证过恢复的备份不算备份：

```bash
./scripts/restore.sh                              # 列出可用备份
./scripts/restore.sh omnigent-db-2026-08-09-0300.sql.gz
```

默认恢复到临时库 `omnigent_restore_check`，不碰生产。核对表数量无误，才说明
这条链路是通的。真要覆盖生产库得显式 `--into` 并二次确认。

## 验证清单

| # | 检查 | 命令 | 期望 |
|---|---|---|---|
| 1 | 镜像含 boto3 | `docker compose exec omnigent /opt/venv/bin/python -c "import boto3"` | 无报错 |
| 2 | 容器健康 | `docker compose ps` | 两个都 healthy |
| 3 | server 存活 | `curl -s localhost:8000/health` | `{"status":"ok"}` |
| 4 | artifacts 落 OSS | UI 里产生一个 artifact，`ossutil ls oss://<bucket>/artifacts/` | 出现对象 |
| 5 | 登录 | 浏览器 `http://<IP>:8000` | 进入 UI |
| 6 | host 连通 | Mac: `omniagent host --server http://<IP>:8000` | 日志显示已注册 |
| 7 | 端到端 | UI 里让 agent 读一个本地文件 | 返回真实内容 |
| 8 | 备份 | `./scripts/backup.sh` | OSS 出现 `.sql.gz` |
| 9 | 恢复 | `./scripts/restore.sh <object>` | 表数量与生产一致 |
| 10 | 定时 | `systemctl list-timers \| grep omnigent` | 有下次执行时间 |
| 11 | 重启不丢数据 | `docker compose restart` | 会话历史还在 |

第 4、8、9 是这套方案的核心，必须全过。

## 排查

**server 起不来，日志有 `ImportError: ... boto3`** — 镜像没带 `s3` extra。
`oss-publish-images.yml` 里 server 那一步需要 `build-args: OMNIGENT_EXTRAS=s3`，
改完重新构建再拉。临时绕过：清空 `.env` 里的 `OMNIGENT_ARTIFACT_URI`，artifacts
退回本地卷。

**artifacts 上传报签名错误** — artifact store 固定用 SigV4。确认
`AWS_ENDPOINT_URL_S3` 和 `AWS_REGION` 与 bucket 实际地域一致。仍不行就先清空
`OMNIGENT_ARTIFACT_URI` 让业务跑起来，再单独排查。

**`docker pull` 报 `pull access denied`** — 登录的主机名和拉取的主机名不一致。
Docker 凭据按主机名分别存储，公网地址和 `-vpc` 内网地址是两个不同的主机名，
用哪个拉就得登录哪个。

**公网访问超时但 ECS 上 `curl localhost:8000/health` 正常** — 安全组没放行，
或者来源 IP 限制里写的还是你上一个出口 IP。

## 接入域名

现在没有域名，直接用 IP 跑。有可用域名后改三处：

1. `.env` 的 `OMNIGENT_ACCOUNTS_BASE_URL` 换成 `https://<域名>`
2. 端口映射改回 `80:8000`，或前置 Caddy / Cloudflare Tunnel
3. 本地 host 的 `--server` 换成域名

走哪条取决于域名能否备案。**能备案** → Caddy + Let's Encrypt，
`../docker/docker-compose.https.yaml` 有现成 overlay 可复用。**不能备案**
（如 Cloudflare 注册的域名）→ Cloudflare Tunnel，ECS 不开任何入站端口，
`cloudflared` 主动出站连接，同时解决备案和证书两件事。
