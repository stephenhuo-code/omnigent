# Omnigent on Aliyun ECS

Runs the server on one ECS box: Postgres on a local volume, artifacts in OSS,
a nightly database dump to OSS. Configuration lives in this directory and is
pushed to the box over SSH, so the machine can be rebuilt from the repository.

`.env` 在本机编辑、随 sync 一起推上去。仓库的 `.gitignore` 覆盖了 `.env` 和
`**/.env`，所以填好的副本进不了版本控制。

```
你的 Mac                        ECS (华东1 杭州)                    OSS
  deploy/aliyun-ecs/                                            artifacts/
   ├── .env (本机编辑)                                              ▲
   └── 其余配置        ──sync.sh(rsync)──▶  /opt/omniagent ────写───┤
                                            ├── postgres (本地卷)   │
                                            │      └─每日 pg_dump──▶ backup/
                                            └── omnigent server :8000
                                                     ▲
  omniagent host ────────────────出站 WebSocket ──────┘
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

# Docker Hub 加速器。compose 里的 postgres:16-alpine 来自 Docker Hub，境内
# 直连会 "connection refused"；ACR 只服务自己的镜像，救不了这个。地址在
# 控制台的「容器镜像服务 → 镜像加速器」，每个账号一个。
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{ "registry-mirrors": ["https://<你的ID>.mirror.aliyuncs.com"] }
JSON
systemctl daemon-reload && systemctl restart docker
docker info | grep -A2 "Registry Mirrors"

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

配置在**本机**填好再推上去，不用 ssh 进去编辑：

```bash
# 本机，在 deploy/aliyun-ecs/ 下
./scripts/gen-secrets.sh            # 建 .env，填好两个随机密钥
$EDITOR .env                        # 填镜像地址、IP、管理员密码、OSS 密钥
./scripts/sync.sh root@<ECS IP>     # 连同 .env 一起推上去

# ECS 上，只需两条
ssh root@<ECS IP>
docker login <与 OMNIGENT_IMAGE 相同的主机名> -u <阿里云账号名>   # 一次性
cd /opt/omniagent && ./scripts/deploy.sh
```

`.env` 被仓库的 `.gitignore` 覆盖（`.env` 和 `**/.env` 两条），填好的副本不会被
误提交，所以放在本机编辑是安全的。`gen-secrets.sh` 只填空值，重复执行不会改写
已有密钥——轮换 cookie secret 会让所有人重新登录，轮换 Postgres 密码会让已有
数据卷对不上凭据。

`deploy.sh` 会等到 `/health` 真的返回才算成功，否则打印最近 50 行日志并非零退出。

浏览器打开 `http://<ECS IP>:8000`，用 `admin` + 你设的密码登录。

## 日常操作

```bash
./scripts/deploy.sh                 # 改了 .env 或想拉新镜像，重跑即可（幂等）
docker compose logs -f omnigent
docker compose ps
```

改配置的正确姿势是**在本机改再 sync**，包括 `.env`。不要直接在服务器上编辑——
下次 sync 会用 `--delete` 把它覆盖掉，而且那份改动没进版本控制，环境就不再可
复现了。

## 配置模型 provider

DeepSeek / MiniMax 这两个示例 agent 不写死模型，而是引用同名 provider——端点、
密钥、默认模型都从那里来。**没配 provider 就不会出现对应的卡片**（不能启动的
agent 不该出现在选择器里）。

配置文件放在数据卷上（`OMNIGENT_CONFIG_HOME=/data/config`），容器重建不会丢。
在 ECS 上创建 `/data/config/config.yaml`：

```yaml
providers:
  deepseek:
    kind: key
    openai:
      base_url: https://api.deepseek.com/v1
      api_key_ref: env:DEEPSEEK_API_KEY
      models:
        default: deepseek-v4-flash
  minimax:
    kind: key
    openai:
      base_url: https://api.minimaxi.com/v1
      api_key_ref: env:MINIMAX_API_KEY
      models:
        default: MiniMax-M3
```

密钥本身不写在这里——`api_key_ref: env:X` 指向环境变量，实际的值填在 `.env`
里（`DEEPSEEK_API_KEY` / `MINIMAX_API_KEY`），`.env` 不进版本库。

模型 id 用 `curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $KEY"`
查当前可用的。注意 DeepSeek 的 `-pro` 目前拒绝 agent 形态的调用，会返回 400 并
提示改用 `-flash`。

改完重启：`docker compose restart omnigent`，然后确认卡片出现：

```bash
curl -s http://<host>:8000/v1/agents | grep -o '"name":"[^"]*"' | sort
```

## 隐藏 Claude

`.env` 里设 `OMNIGENT_HIDDEN_HARNESSES=claude-sdk,claude-native`，重跑
`./scripts/deploy.sh`。选择器和 `/v1/harnesses` 都不再出现 Claude，`omnigent
setup` 也不再探测 Claude 订阅。

这只是**不展示**：手写 `harness: claude-sdk` 的 spec 仍然能跑。需要真正禁用请用
别的手段。

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

**`docker pull` 报 `pull access denied`** — 登录的主机名和 `OMNIGENT_IMAGE` 里
的主机名不一致。Docker 凭据按主机名分别存储，ACR 的公网地址和 `-vpc` 内网地址
是两个不同的主机名（同一个仓库），用哪个拉就得登录哪个。

**公网访问超时但 ECS 上 `curl localhost:8000/health` 正常** — 安全组没放行，
或者来源 IP 限制里写的还是你上一个出口 IP。

**登录一直 "Login failed"** — 两种原因，日志会说明是哪种：

```bash
docker compose logs omnigent | grep -iE "admin already exists|needs_setup"
docker compose exec postgres psql -U omnigent -d omnigent -c "select id, is_admin from users;"
```

看到 `admin already exists — ignoring the supplied password`，说明管理员在更早
一次启动时就建好了，之后改 `.env` 里的密码**不生效**——这两个变量只在无管理员
时读取。用户名也未必是 `admin`：默认取 `getpass.getuser()`，在容器里就是 `root`
（所以现在 `.env` 显式钉了 `OMNIGENT_ACCOUNTS_INIT_ADMIN_USERNAME`）。

`users` 表会告诉你真实的用户名。实例里没有值得保留的数据时，最快的修法是
`docker compose down -v` 清库重建；有数据了就从 Web UI 的 Members 页面改密码。

**`docker pull` 报 `dial tcp ...: connection refused` 且地址是 registry-1.docker.io**
— Docker Hub 在境内连不通。配置上面那个镜像加速器。注意 ACR 帮不上忙：它只
服务你自己推上去的镜像，`postgres:16-alpine` 这种第三方基础镜像仍走 Docker Hub。

## HTTPS 与域名

域名**能备案**就走 Caddy overlay（本目录的 `docker-compose.https.yaml` +
`Caddyfile`，从 `../docker/` 移植）。Caddy 占 80/443，自动签发并续期
Let's Encrypt 证书，反代到 docker 网络里的 `omnigent:8000`；omnigent 只在
回环口发布，公网碰不到它。

顺带拿到的是 HTTP/2。这不只是「顺便」：Web UI 每个打开的会话都挂一条长连接的
event-stream，HTTP/1.1 每源约 6 条连接的上限会让用户多开几个窗口就卡住，
HTTP/2 把它们复用到一条连接上。

**不能备案**（如 Cloudflare 注册的域名）→ Cloudflare Tunnel，ECS 不开任何入站
端口，`cloudflared` 主动出站连接，同时解决备案和证书两件事。本目录没有现成
配置。

### 切过去

先动安全组，再部署。反过来的话旧的 `${OMNIGENT_PORT}` 映射已经撤掉、80/443 又
还没放行，你就把自己关在门外了，只能走控制台 VNC 救。

1. 安全组入方向：
   - **80/tcp 来源 `0.0.0.0/0`** —— 不能只放自己的出口 IP。HTTP-01 是
     Let's Encrypt 自己的服务器来验的，源地址不公布，白名单必然验不过。
   - **443/tcp**，来源按需（想收窄就收窄，挑战不走 443）。
   - 旧的 8000 那条先留着做回退，验完再删。
2. DNS 的 A 记录指向 ECS 公网 IP，且**已经生效**——证书签发要靠它。
3. `.env` 三行：

   ```
   OMNIGENT_DOMAIN=<域名>
   COMPOSE_FILE=docker-compose.yaml:docker-compose.https.yaml
   OMNIGENT_ACCOUNTS_BASE_URL=https://<域名>
   ```

   `COMPOSE_FILE` 写在 `.env` 里，Compose 自己会读，所以在机器上直接敲
   `docker compose logs -f caddy` 也能命中 overlay，不用每次重复两个 `-f`。
4. `./scripts/sync.sh root@<ECS IP>` 然后 `./scripts/deploy.sh`。

`deploy.sh` 在这个模式下等两件事：应用在 `127.0.0.1:8000/health` 起来，以及
证书真的能用（用 `--resolve` 把连接钉到本机 Caddy，SNI 和 Host 仍是真域名，
这样不依赖 ECS 能不能回环访问自己的公网 IP——阿里云 EIP 的 hairpin 不可靠）。
两步都过才算绿。

### 切完要跟着改的

- 本机 host：`omniagent host --server https://<域名>`。
- 已发出去的邀请链接带着旧的 `:8000`，端口一关就失效，需要重发。
- `OMNIGENT_ACCOUNTS_BASE_URL` 一旦是 `https://`，session cookie 就启用
  `__Host-` 前缀（`omnigent/server/accounts_config.py`）。浏览器在纯 HTTP 上
  会直接丢掉这种 cookie，导致登录无限重定向——所以这三行必须一起改，不能只改
  两行。Caddy 会把 HTTP 跳到 HTTPS，正常访问碰不到这个坑。

### 排查

**`no working certificate after 120s`** —— 先看 `docker compose logs caddy`。
最常见是安全组的 80 只放了自己的 IP（见上），其次是 DNS 还没生效或指错 IP。

**反复重建导致签发被拒** —— Let's Encrypt 对同一域名的重复证书是每周 5 张。
`caddy-data` 卷存着证书和 ACME 账号密钥，别对这套 `down -v`，否则每次重建都
要重签一张。真要反复调试就先在 Caddyfile 里挂 staging CA。

**ACME 一直超时而不是验证失败** —— 那是 CA 的连通性问题，不是配置问题。
`Caddyfile` 注释里有换用 ZeroSSL 的写法。
