# 部署方案

这份文档是 `stephenhuo-code/omnigent` 这个 fork 的**完整构建与部署方案**：所有组件从这个仓库编译，正式版由 GitHub Actions 在打 tag 时构建，server 部署在阿里云 ECS，host 跑在本地 Mac，桌面端下载后连云端 server。

一份文档覆盖全流程，配置内容直接内联可复制。

---

## 1. 架构总览

### 部署图

```
┌─────────────────────────────────────────────────────────────────────┐
│  GitHub · stephenhuo-code/omnigent                                  │
│                                                                     │
│   main 分支 ──push──┐                    v* tag ──push──┐           │
│                     ▼                                   ▼           │
│         ┌───────────────────────┐         ┌───────────────────────┐ │
│         │  dev 通道（滚动）     │         │  release 通道（正式） │ │
│         └───────────┬───────────┘         └───────────┬───────────┘ │
│                     │                                 │             │
│   ┌─────────────────┴─────────────────────────────────┴───────────┐ │
│   │  GitHub Actions（CI/CD 流水线）                               │ │
│   │   ① publish-images   → server / host 镜像                     │ │
│   │   ② electron-build   → 桌面端 × {mac, win, linux}             │ │
│   │   ③ release-omnigent  → wheel → PyPI                          │ │
│   └───────┬───────────────────┬───────────────────┬───────────────┘ │
│           ▼                   ▼                   ▼                 │
│   ghcr.io/stephenhuo-code   GitHub Releases    pypi.org             │
│     omnigent-server           Omnigent-*.dmg     omniagent          │
│       :main :sha-xxx (dev)    Omnigent-*.exe     omniagent-client   │
│       :v0.9.0 :latest (rel)   *.AppImage         omniagent-ui-sdk   │
│     omnigent-host                                                   │
└───────────┬───────────────────────┬───────────────────┬─────────────┘
            │ docker pull           │ 浏览器下载        │ uv tool install
            ▼                       ▼                   ▼
┌───────────────────────────┐   ┌─────────────────────────────────────┐
│  阿里云 ECS（2核4G, x86） │   │  本地 Mac（Apple Silicon）          │
│  ┌─────────────────────┐  │   │                                     │
│  │ caddy   :443 :80    │◄─┼───┼── ① 桌面端 Omnigent.app             │
│  │  Let's Encrypt 自动 │  │HTTPS│    未签名，首次需去隔离属性        │
│  │  签发/续期证书      │  │   │                                     │
│  └──────────┬──────────┘  │   │  ② host 进程                        │
│             ▼ :8000       │   │     uv tool install omniagent       │
│  ┌─────────────────────┐  │   │     omniagent host --server https://…│
│  │ omnigent server     │◄─┼───┼──   ▲ 出站连接                      │
│  │  ghcr:latest        │  │WSS│     │ 无需公网 IP / 不开端口        │
│  └──────────┬──────────┘  │出站│     │                              │
│             ▼             │   │     └─ 在本机执行 agent：读写代码、 │
│  ┌─────────────────────┐  │   │        跑 shell、调 claude/codex    │
│  │ postgres 16         │  │   └─────────────────────────────────────┘
│  │  volume: pgdata     │  │
│  └─────────────────────┘  │   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│  volume: artifact-data    │     云端 host（本期不部署，链路已就绪）
│  安全组：22(限IP) 80 443  │   │  ghcr.io/…/omnigent-host          │
└───────────────────────────┘     已含 node/git/agent CLI，起容器即用
                                └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

### 三条关键设计线

**server 与 host 是同一份代码的两个子命令。** 不是两个项目。`omniagent server` 和 `omniagent host` 来自同一个 Python 包，所以 wheel 和镜像共用一条构建链，版本天然对齐——不会出现 server v0.9 配 host v0.7 的错配。

**host 走出站连接，这是本地 Mac 能用的前提。** host 主动连 server 的 WebSocket，不监听任何端口。所以 Mac 在 NAT / 防火墙后面也能注册成执行节点：不需要公网 IP、不需要端口映射、不需要内网穿透。ECS 安全组只开 80/443（外加限来源 IP 的 22）就够。

**代码和密钥留在 host 侧。** server 只做协调——存会话、路由消息、提供 Web UI。真正读写代码、跑命令、调用模型 API 的是 host。ECS 上那台机器不存源码，模型 key 配在本地 Mac 上。这也是将来开云端 host 时建议用独立机器的原因：它是唯一有执行权的角色。

### server 与 host 的关系

| | server | host |
|---|---|---|
| 职责 | 协调：存会话、路由消息、提供 Web UI | 执行：跑 agent、读写代码、调 shell 和 CLI |
| 网络 | **监听** 8000 端口，被动接受连接 | **主动出站**连 server，不监听端口 |
| 状态 | 有，连 Postgres | 无，挂了重启即可 |
| 依赖 | Python + 数据库 | Python + git + node + agent CLI + 代码 + 模型 key |
| 数量 | 1 个 | 任意多个，可同时注册 |

多对一关系：一个 server 上可同时挂本地 Mac、同事的 Mac、云端容器，在 Web UI 里选任务在哪台机器上跑。

镜像层面是同一个 `deploy/docker/Dockerfile` 的两个构建目标：

```
deploy/docker/Dockerfile
├── target: runtime  → omnigent-server 镜像（python:slim + curl，很瘦）
└── target: host     → omnigent-host   镜像（+ node/npm/git/agent CLI，很厚）
```

server 镜像里虽然有 `host` 子命令，但缺 git/node/CLI，跑不动实际任务。镜像不同不是因为代码不同，是因为运行环境的依赖不同。

---

## 2. 命名与版本约定

### 包改名

上游已占用 PyPI 上的 `omnigent` / `omnigent-client` / `omnigent-ui-sdk` 三个名字，fork 要发 PyPI 必须改名。改后：

| 层 | 现在 | 改成 | 说明 |
|---|---|---|---|
| **分发名**（`pip install` 用） | `omnigent` | `omniagent` | 三个包统一改 |
| | `omnigent-client` | `omniagent-client` | |
| | `omnigent-ui-sdk` | `omniagent-ui-sdk` | |
| **命令名**（终端里敲） | `omnigent` / `omni` | `omniagent` / `omni` | 见下方兼容别名 |
| **导入名**（`import` 用） | `omnigent` | **不改** | 目录名和所有 `import omnigent` 保持原样 |

> `omni-agent`（带连字符）在 PyPI 已被他人占用，所以用无连字符的 `omniagent`。PyPI 的名称归一化只把 `-` `_` `.` 视作等价，`omniagent` 与 `omni-agent` 是两个独立的名字。

导入名坚决不动：改它要重命名目录并修改上千处 import，且每次合并上游必然大面积冲突，而这一层对使用者完全不可见。

### 命令别名：保留 `omnigent`

`[project.scripts]` 里同时装三个入口，全部指向同一个 CLI：

```toml
[project.scripts]
omniagent = "omnigent.cli:main"    # 新的主命令
omni      = "omnigent.cli:main"    # 短别名（原有）
omnigent  = "omnigent.cli:main"    # 兼容别名 — 见下
```

**保留 `omnigent` 是有意为之。** 仓库里 90 多个 workflow、几十份文档、`.claude/skills/` 下的技能定义里全是 `omnigent xxx` 的命令示例。不保留别名，这些会集体失效。多一行入口点的成本可以忽略，换来的是仓库现有内容不用动。

> 如果确认不需要向后兼容，删掉第三行即可，其余方案不受影响。

### 镜像名不改

ghcr 镜像保持 `omnigent-server` / `omnigent-host`。命名空间 `stephenhuo-code` 已经和上游隔离，不存在冲突；改名只会增加 workflow 的改动量和与上游的合并摩擦。

### 版本

三个包**版本锁死联动**——`release-omnigent.yml` 的校验脚本强制要求三者版本都等于 tag，且交叉依赖是精确 `==tag` 的 pin。发版前必须同步改三个 `pyproject.toml`：

```
pyproject.toml                    version = "0.9.0"  + 依赖 omniagent-client==0.9.0, omniagent-ui-sdk==0.9.0
sdks/python-client/pyproject.toml version = "0.9.0"  + 依赖 omniagent==0.9.0
sdks/ui/pyproject.toml            version = "0.9.0"  + 依赖 omniagent-client==0.9.0
```

当前是 `0.9.0.dev0`，首个正式版为 `v0.9.0`。

---

## 3. 构建与发布

### 两个通道

| | dev 通道 | release 通道 |
|---|---|---|
| 触发 | push 到 `main` | 打 `v*` tag |
| 镜像标签 | `:main`、`:sha-abc1234` | `:v0.9.0`、`:latest` |
| 构建范围 | 只 server + host，只 amd64 | 全部 4 个镜像，amd64 + arm64 |
| 桌面端 | 不自动构建（手动指定 ref 触发） | 自动构建三平台，传 Releases |
| PyPI | 不发布 | 发布三个包 |
| 单次耗时 | ~10-15 分钟 | ~40-60 分钟 |
| ECS 用哪个 | 想尝鲜时临时切 `:main` | 常态跑 `:latest` |

**dev 通道为什么收窄。** 上游把 per-commit 构建改成了每日定时（`oss-publish-images.yml` 注释：*Per-commit main builds were retired in favour of the nightly rebuild*），原因是 4 镜像 × 2 架构太慢。这里恢复 per-commit 但只构建实际会用到的部分：ECS 是 x86，所以 amd64 足够；本地 Mac 的 host 是 wheel 装的原生进程，不用镜像，所以 dev 通道不需要 arm64。

**桌面端 dev 通道为什么不自动构建。** macOS runner 单价是 Linux 的 10 倍，每次 push 构建三平台会快速烧掉 CI 额度。需要验证时从 Actions 页面手动触发并指定 ref 即可。

### 需要改的文件

| # | 文件 | 改动 |
|---|---|---|
| 1 | `pyproject.toml` | 分发名 → `omniagent`；两个交叉 pin 改名；`[project.scripts]` 加 `omniagent` 入口 |
| 2 | `sdks/python-client/pyproject.toml` | 分发名 → `omniagent-client`；对主包的 pin 改名 |
| 3 | `sdks/ui/pyproject.toml` | 分发名 → `omniagent-ui-sdk`；对 client 的 pin 改名 |
| 4 | `.github/workflows/release-omnigent.yml` | 校验脚本里的 `packages` 字典同步改名 |
| 5 | `.github/workflows/oss-publish-images.yml` | 镜像名参数化；加 `push: branches:[main]`；dev 通道收窄 |
| 6 | `.github/workflows/electron-build.yml` | 加 macOS 矩阵项 + 未签名覆盖 + dmg 产物上传 |
| 7 | `.github/workflows/github-release.yml` | tag 时把桌面端安装包挂成 Release 附件 |

### 改动 5：镜像命名空间

`oss-publish-images.yml` 第 114-117 行硬编码了上游命名空间，fork 没有推送权限：

```diff
- IMAGE="ghcr.io/omnigent-ai/omnigent-server"
- HOST_IMAGE="ghcr.io/omnigent-ai/omnigent-host"
- OPENSHELL_IMAGE="ghcr.io/omnigent-ai/omnigent-server-openshell"
- KUBERNETES_IMAGE="ghcr.io/omnigent-ai/omnigent-server-kubernetes"
+ OWNER="${{ github.repository_owner }}"          # → stephenhuo-code
+ IMAGE="ghcr.io/${OWNER}/omnigent-server"
+ HOST_IMAGE="ghcr.io/${OWNER}/omnigent-host"
+ OPENSHELL_IMAGE="ghcr.io/${OWNER}/omnigent-server-openshell"
+ KUBERNETES_IMAGE="ghcr.io/${OWNER}/omnigent-server-kubernetes"
```

用 `github.repository_owner` 而非硬编码用户名：合并上游时不冲突，fork 给别人也能直接用。ghcr 要求命名空间全小写，`stephenhuo-code` 本身就是小写。

同时加上 dev 通道触发：

```yaml
on:
  push:
    branches: ['main']      # ← 新增：dev 通道
    tags: ['v*']            # 原有：release 通道
```

并在构建步骤里按触发类型收窄范围——`main` 分支只构建 server + host、只出 `linux/amd64`；tag 走原有的全量多架构构建。

### 改动 6：macOS 桌面端

`electron-build.yml` 第 13 行明确写着 `macOS is intentionally omitted — its signed/notarized build lives elsewhere`，矩阵里只有 Linux 和 Windows。这条链路当前是断的，必须补上：

```yaml
matrix:
  include:
    - os: macos-latest        # ← 新增。runner 是 Apple Silicon，产出 arm64
      platform: mac
      build-script: build:mac
    - os: ubuntu-latest
      platform: linux
      build-script: build:linux
    - os: windows-latest
      platform: win
      build-script: build:win
```

构建步骤要覆盖掉写死的签名身份——`web/electron/package.json` 第 80 行是 `"identity": "Databricks, Inc. (8RMX4WU6F8)"`，未签名构建会因为找不到这张证书而失败：

```yaml
- name: Build ${{ matrix.platform }} app
  env:
    CSC_IDENTITY_AUTO_DISCOVERY: false     # 别去钥匙串找证书
  run: |
    pnpm run ${{ matrix.build-script }} -- \
      --publish never \
      -c.mac.identity=null                 # 覆盖 package.json 里的 Databricks identity
```

**只在 CI 命令行覆盖，不改 `package.json`。** 那个 identity 是上游配置，改了以后每次合并上游都会冲突。命令行 `-c.` 参数是 electron-builder 官方的覆盖机制，优先级更高。

产物：`Omnigent-0.9.0-arm64-mac.dmg` 加自动更新清单 `latest-mac.yml`。

---

## 4. 一次性准备

### 4.1 PyPI 可信发布

现有 workflow 用的是 **OIDC Trusted Publishing**——不用生成 API token 存 Secrets，而是在 PyPI 上登记一条信任规则，GitHub 与 PyPI 之间靠短期令牌握手。比 token 安全，也少一份要轮换的密钥。

1. 注册 pypi.org 账号并**开启 2FA**（发布包强制要求）
2. Publishing → Add a pending publisher，对三个包各做一遍：

   ```
   PyPI Project Name:  omniagent          （另两次：omniagent-client / omniagent-ui-sdk）
   Owner:              stephenhuo-code
   Repository name:    omnigent
   Workflow name:      release-omnigent.yml
   Environment name:   pypi
   ```

3. GitHub 仓库 Settings → Environments → 新建名为 `pypi` 的环境

### 4.2 ghcr 包可见性

首次推送后镜像默认是 private，ECS 拉取需要登录。改成 public 更省事：

GitHub 个人页 → Packages → `omnigent-server` → Package settings → Change visibility → Public。`omnigent-host` 同理。

保持 private 也可以，届时 ECS 上需要先 `docker login ghcr.io`（token 需要 `read:packages` 权限）。

### 4.3 阿里云 ECS

| 项 | 建议值 |
|---|---|
| 规格 | 2 vCPU / 4 GB 起（共享型 s6 或计算型 c6 均可） |
| 架构 | **x86_64**（对应镜像的 `linux/amd64`） |
| 系统 | Ubuntu 22.04 LTS 或 24.04 LTS |
| 磁盘 | 40 GB 以上（镜像 + Postgres + artifacts） |
| 带宽 | 按量计费，1-5 Mbps 够用 |

安全组入方向规则：

| 端口 | 来源 | 用途 |
|---|---|---|
| 22 | **仅你的固定 IP** | SSH，不要开 0.0.0.0/0 |
| 80 | 0.0.0.0/0 | Let's Encrypt HTTP-01 验证 + HTTP 跳转 |
| 443 | 0.0.0.0/0 | HTTPS（含 WebSocket） |

**8000 端口不要开放。** Caddy 从 docker 内网代理进去，server 容器不直接暴露到宿主机。

### 4.4 域名

买个域名，加一条 A 记录指向 ECS 公网 IP：

```
omni.example.com.  A  <ECS 公网 IP>
```

**必须有域名**，不能用裸 IP：Let's Encrypt 不给 IP 签证书，而桌面端和 host 走 HTTPS/WSS 需要有效证书。

> 国内 ECS 绑域名做 80/443 服务需要**ICP 备案**。没备案的话，可以把 server 放在境外区域的 ECS（如香港、新加坡），或改用阿里云 SLB + 已备案域名。

---

## 5. 阿里云 ECS 部署 server

### 5.1 装 Docker

```bash
ssh root@<ECS 公网 IP>

curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version        # 确认 compose 插件可用
```

### 5.2 创建部署目录与配置

以下三个文件全部内联，直接复制创建即可。**不需要 clone 整个仓库**——这些是从 `deploy/docker/` 精简出来的自包含版本，只保留 accounts 认证模式所需的部分。

```bash
mkdir -p /opt/omniagent && cd /opt/omniagent
```

#### `docker-compose.yaml`

```yaml
name: omniagent

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: omnigent
      POSTGRES_USER: omnigent
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U omnigent -d omnigent"]
      interval: 10s
      timeout: 5s
      retries: 5

  omnigent:
    image: ${OMNIGENT_IMAGE:-ghcr.io/stephenhuo-code/omnigent-server}:${OMNIGENT_IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+psycopg://omnigent:${POSTGRES_PASSWORD}@postgres:5432/omnigent
      ARTIFACT_DIR: /data/artifacts
      HOST: 0.0.0.0
      PORT: "8000"
      # 把 server 的数据目录锚在持久卷上：管理员名单 (/data/admins)、
      # 允许域名文件 (/data/allowed_domains) 都在这里，容器重启不丢。
      OMNIGENT_ADMIN_CREDENTIALS_PATH: /data/admin-credentials
      # 内置账号模式：用户名 + 密码，不需要外部 IdP
      OMNIGENT_AUTH_ENABLED: "1"
      OMNIGENT_ACCOUNTS_COOKIE_SECRET: ${OMNIGENT_ACCOUNTS_COOKIE_SECRET:?run the openssl command in the doc}
      OMNIGENT_ACCOUNTS_BASE_URL: https://${OMNIGENT_DOMAIN}
      OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD: ${OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD:?set an admin password in .env}
      OMNIGENT_ACCOUNTS_AUTO_OPEN: "0"
      OMNIGENT_DOMAIN: ${OMNIGENT_DOMAIN}
    volumes:
      - artifact-data:/data
    # 不发布端口：Caddy 从 docker 内网代理进来

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    depends_on:
      - omnigent
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      OMNIGENT_DOMAIN: ${OMNIGENT_DOMAIN:?set OMNIGENT_DOMAIN in .env}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config

volumes:
  postgres-data:
  artifact-data:
  caddy-data:
  caddy-config:
```

#### `Caddyfile`

```
{$OMNIGENT_DOMAIN} {
	encode zstd gzip
	reverse_proxy omnigent:8000
}
```

Caddy 自动通过 HTTP-01 挑战申请并续期 Let's Encrypt 证书，无需填邮箱（匿名注册）。它同时带来 HTTP/2——这点很重要：Web UI 里每个打开的会话都持有一条长连接，HTTP/1.1 每源约 6 条连接的上限会让多开标签页时界面卡住，HTTP/2 的多路复用正是解法。

#### `.env`

先生成两个密钥：

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
echo "OMNIGENT_ACCOUNTS_COOKIE_SECRET=$(openssl rand -hex 32)"
```

把输出填进 `.env`：

```bash
# ── 域名（换成你的）──────────────────────────────
OMNIGENT_DOMAIN=omni.example.com

# ── 镜像 ────────────────────────────────────────
OMNIGENT_IMAGE=ghcr.io/stephenhuo-code/omnigent-server
OMNIGENT_IMAGE_TAG=latest
#   latest        = 最新正式版（推荐）
#   v0.9.0        = 钉死某个版本，可复现
#   main          = dev 通道滚动版
#   sha-abc1234   = 钉死某个 commit

# ── 数据库 ──────────────────────────────────────
POSTGRES_PASSWORD=<上面生成的 hex 16>

# ── 账号认证 ────────────────────────────────────
OMNIGENT_ACCOUNTS_COOKIE_SECRET=<上面生成的 hex 32>
OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD=<你自己设一个强密码>
```

> ⚠️ **`OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD` 必须设。**
> 首个管理员尚未创建时，`POST /auth/setup` 是**故意不鉴权**的——设计上让运维能通过网页表单创建管理员。但公网实例一旦在你填表之前被人访问到，**第一个访问者就能把实例占为己有**。预置这个密码可以让首次启动直接建好管理员，关掉这个窗口。

```bash
chmod 600 .env      # 里面有密码
```

### 5.3 启动

```bash
cd /opt/omniagent
docker compose pull
docker compose up -d
docker compose logs -f omnigent      # 看到监听日志后 Ctrl-C
```

浏览器打开 `https://omni.example.com`，用 `admin` 和 `.env` 里设的密码登录。首次访问 Caddy 要签证书，可能慢几十秒。

> **ghcr 拉取慢或超时的兜底**（国内 ECS 常见）：
>
> 1. **重试**——ghcr 偶发超时，`docker compose pull` 多跑两次往往就过了
> 2. **本地中转**：在能正常访问 ghcr 的机器上拉下来打包，scp 到 ECS 导入
>    ```bash
>    # 本地 Mac（注意指定 amd64，Mac 默认拉 arm64）
>    docker pull --platform linux/amd64 ghcr.io/stephenhuo-code/omnigent-server:latest
>    docker save ghcr.io/stephenhuo-code/omnigent-server:latest | gzip > server.tar.gz
>    scp server.tar.gz root@<ECS IP>:/opt/omniagent/
>    # ECS 上
>    gunzip -c server.tar.gz | docker load
>    ```
> 3. **ECS 上配代理**：给 docker daemon 设 `HTTPS_PROXY`（`/etc/systemd/system/docker.service.d/proxy.conf`）
>
> 如果长期受困于此，把镜像改推阿里云 ACR 是根治方案——CI 里加一个 push 步骤即可，ECS 从 ACR 内网拉取是秒级。

---

## 6. 本地 Mac 跑 host

### 6.1 安装

```bash
uv tool install omniagent
omniagent --version
```

装完得到三个命令，都指向同一个 CLI：`omniagent`、`omni`、`omnigent`（兼容别名）。

> 还没发首个正式版时，可以直接从仓库装：
> ```bash
> uv tool install git+https://github.com/stephenhuo-code/omnigent@main
> ```

### 6.2 启动 host

```bash
omniagent host --server https://omni.example.com
```

首次运行会走登录流程，浏览器打开 server 的登录页，认证后凭据存在 `~/.omnigent/auth_tokens.json`。

host 是**出站连接**，所以 Mac 在 NAT 后面、换 WiFi、连热点都能用，不需要任何网络配置。

### 6.3 后台常驻

```bash
# 前台跑，关终端就停（适合临时用）
omniagent host --server https://omni.example.com

# 后台跑（tmux）
tmux new -s host -d 'omniagent host --server https://omni.example.com'
tmux attach -t host        # 查看
```

需要开机自启的话用 launchd，把上面的命令包进一个 `~/Library/LaunchAgents/*.plist`。

### 6.4 本地数据目录

```
~/.omnigent/
├── auth_tokens.json    登录凭据
├── config.yaml         配置
├── artifacts/          产物
├── logs/               日志
└── daemons/            host 进程注册信息
```

模型 API key 和你的源码都在这台机器上，不会上传到 server。

### 6.5 升级

```bash
uv tool upgrade omniagent
```

升级前先停掉 host 进程。**server 和 host 的版本应保持一致**——跨版本可能有协议不兼容。

---

## 7. 桌面端

### 7.1 下载

GitHub 仓库 → Releases → 最新版本 → 下载 `Omnigent-<版本>-arm64-mac.dmg`（Intel Mac 选 `x64`）。

### 7.2 安装与首次打开

安装包**未签名**，macOS Gatekeeper 会拦截。两种解法任选：

```bash
# 方法一：装好后去掉隔离属性（推荐，一劳永逸）
sudo xattr -dr com.apple.quarantine /Applications/Omnigent.app
```

方法二：在「访达」里右键点 Omnigent.app → 打开 → 在弹窗里再点「打开」。只需做一次。

> 直接双击会提示「已损坏，无法打开」——这不是文件真的损坏，是未签名的标准表现。

### 7.3 连接云端 server

首次启动在设置里填 server 地址：

```
https://omni.example.com
```

用与 Web UI 相同的账号登录。桌面端本身**不执行任何 agent 任务**，它只是个客户端——任务仍然跑在注册上去的 host 上（也就是你本地 Mac 的 host 进程）。

### 7.4 桌面端数据目录

```
~/Library/Application Support/Omnigent/
```

Electron 的缓存、Cookie、窗口设置都在这里。和 `~/.omnigent/`（host 的数据）是两回事，删掉只会丢登录状态和窗口位置。

---

## 8. 发版、升级与回滚

### 8.1 发布正式版

```bash
# 1. 三个 pyproject.toml 的 version 同步改成 0.9.0，交叉 pin 也改成 ==0.9.0
# 2. 提交、推送
git commit -am "release: v0.9.0"
git push

# 3. 打 tag 并推送 —— 这一步触发全部构建
git tag v0.9.0
git push origin v0.9.0
```

推 tag 后 GitHub Actions 自动完成：构建 4 个镜像（amd64 + arm64）推 ghcr、构建三平台桌面端传 Releases、构建三个 wheel 发 PyPI。约 40-60 分钟。

在仓库的 Actions 页面看进度。任一步失败都不会污染已发布的产物——PyPI 那步遇到版本冲突会直接失败，不会覆盖。

### 8.2 升级 ECS 上的 server

```bash
cd /opt/omniagent
docker compose pull          # 拉 .env 里 OMNIGENT_IMAGE_TAG 指定的版本
docker compose up -d         # 只重建有变化的容器
docker compose logs -f omnigent
```

数据库和 artifacts 都在 volume 上，不受影响。**升级后同步升级本地 host**（`uv tool upgrade omniagent`），保持版本一致。

### 8.3 回滚

```bash
cd /opt/omniagent
sed -i 's/^OMNIGENT_IMAGE_TAG=.*/OMNIGENT_IMAGE_TAG=v0.8.2/' .env
docker compose up -d
```

> ⚠️ **回滚只对镜像有效，对数据库不一定。** 新版本如果做过 schema 迁移，回退到旧版本可能读不了库。生产环境升级前先备份：
> ```bash
> docker compose exec postgres pg_dump -U omnigent omnigent | gzip > /root/backup-$(date +%Y%m%d).sql.gz
> ```

### 8.4 备份

```bash
# 数据库
docker compose exec postgres pg_dump -U omnigent omnigent | gzip > db-$(date +%Y%m%d).sql.gz

# artifacts 卷
docker run --rm -v omniagent_artifact-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/artifacts-$(date +%Y%m%d).tar.gz -C /data .
```

建议加进 crontab 每日跑一次，并把备份同步到 OSS。

---

## 9. 验证清单

部署完按顺序过一遍，每步都能独立确认：

| # | 检查 | 命令 / 操作 | 期望结果 |
|---|---|---|---|
| 1 | 容器都起来了 | ECS: `docker compose ps` | 三个服务都是 `running`，postgres 是 `healthy` |
| 2 | server 健康 | ECS: `docker compose exec omnigent curl -s localhost:8000/health` | `{"status":"ok"}` |
| 3 | HTTPS 通 | 本地: `curl -sI https://omni.example.com` | HTTP 200，证书有效不报警 |
| 4 | 证书正确 | 浏览器打开，点地址栏锁图标 | 颁发者 Let's Encrypt，域名匹配 |
| 5 | 能登录 | 浏览器访问，用 admin + 密码 | 进入 Web UI |
| 6 | host 能连上 | Mac: `omniagent host --server https://omni.example.com` | 日志显示已注册，无报错 |
| 7 | host 在 UI 里可见 | Web UI 的 hosts / runners 页面 | 看到你的 Mac |
| 8 | 端到端跑通 | Web UI 里发起一个会话，让 agent 读一个本地文件 | 返回本地文件内容 |
| 9 | 桌面端可用 | 打开 Omnigent.app，填 server 地址登录 | 能看到与 Web UI 相同的会话 |
| 10 | 重启不丢数据 | ECS: `docker compose restart`，刷新 UI | 会话历史还在 |

第 8 步是真正的端到端验证——它同时证明了 server 路由正常、host 注册成功、双向通信通畅。前面 7 步都过了但第 8 步不通，问题一定在 host 与 server 的 WebSocket 上。

---

## 10. 故障排查

**Caddy 签不到证书**

```bash
docker compose logs caddy
```

按顺序查：域名 A 记录是否指向这台 ECS（`dig omni.example.com`）；安全组 80 端口是否对 0.0.0.0/0 开放（HTTP-01 挑战必须走 80）；国内 ECS 是否因未备案被拦截 80 端口。

**host 连不上 server**

先确认 server 在公网可达：`curl -I https://omni.example.com`。再看 host 日志里的具体错误——401 是凭据问题（删掉 `~/.omnigent/auth_tokens.json` 重新登录），连接超时通常是本地网络出站被限制。

**host 注册上了但任务跑不动**

多半是 host 机器缺工具。host 需要 git、node，以及你实际用到的 agent CLI（claude / codex / pi 等）。检查：`which git node claude`。

**Web UI 多开标签页后卡住**

确认走的是 HTTPS 而非直连 8000 端口——HTTP/2 是解决长连接数量上限的关键，只有经 Caddy 才有。

**桌面端提示「已损坏」**

未签名的标准表现，执行 `sudo xattr -dr com.apple.quarantine /Applications/Omnigent.app`。

**PyPI 发布失败：`non-user identity` 或 403**

信任发布规则没配对。检查 PyPI 上登记的 Owner / Repository / Workflow / Environment 四项与实际是否**完全一致**——workflow 名要写文件名 `release-omnigent.yml`，environment 要和 workflow 里的 `environment:` 值一致。

**镜像推送失败：`denied: permission_denied`**

workflow 的 job 缺 `packages: write` 权限，或镜像命名空间与仓库 owner 不匹配（ghcr 只允许推到自己的命名空间）。

---

## 11. 落地顺序

改动之间有依赖，按这个顺序做，每步都能独立验证：

1. **改包名与命令名**（`pyproject.toml` × 3 + `release-omnigent.yml` 校验脚本）
   验证：本地 `uv build` 成功，产物文件名是 `omniagent-0.9.0.dev0-*.whl`
2. **改镜像命名空间 + dev 通道**（`oss-publish-images.yml`）
   验证：push 到 main，Actions 跑通，ghcr 上出现 `:main` 标签
3. **加 macOS 桌面端构建**（`electron-build.yml`）
   验证：手动触发 workflow，产物里有 `.dmg`
4. **挂 Release 附件**（`github-release.yml`）
   验证：随下一步 tag 一起验
5. **配置 PyPI 可信发布**（PyPI 网站 + GitHub Environment）
6. **发首个正式版** `v0.9.0`
   验证：ghcr 有 `:v0.9.0` 和 `:latest`；Releases 有三平台安装包；PyPI 有三个包
7. **部署 ECS**（第 5 节）
8. **本地起 host + 装桌面端**（第 6、7 节），跑完第 9 节的验证清单

第 1-4 步是纯 CI 改动，不影响任何现有功能，可以放心先做。第 5-6 步是不可逆的——PyPI 上的版本号发出去就不能重发同一个号，所以发版前务必确认三个 `pyproject.toml` 的版本号一致。
