# 东门子工业设备维护 Web 教学靶场

**仓库：** https://github.com/alen875/AI-security-learning 。靶场源码位于仓库的 `dongmenzi-lab/` 目录。

一个使用**虚构工业设备与维护记录**的本地 Web 安全训练项目。学员可在相同业务数据上比较对象级授权和 SQL 查询的教学状态、修复状态，并记录验证与复测证据。项目不会连接 PLC、SCADA、真实设备或工业协议。

> 项目状态：源码与自动化测试已完成初步本机验证；Windows 虚拟机与 Kali 双机联通、浏览器视觉检查和教师许可仍须在实际教学环境核验。公开漏洞编号只作原理分析，本项目不宣称复现原产品或安装厂商补丁。

## 训练点

| 模式 | 指定教学入口 | 安全状态与训练状态的差别 | 验证边界 |
|---|---|---|---|
| `safe` | 全部入口 | 对象授权及参数绑定开启 | 默认启动状态 |
| `idor` | `GET /api/records/{id}` | 对预置维护记录省略对象归属检查 | 只读；登录仍必需；其他接口继续检查权限 |
| `sqli` | `GET /api/training-search?q=` | 在独立教学索引库中演示 SQL 拼接 | 索引全为虚构、对学员公开的数据；数据库只读；不接主业务记录表 |
| `bp` | `POST /api/training/report-preview` | 错误信任客户端提交的 `preview_role` | 只读虚构报告；可用 Burp Suite 拦截并重放；不改变业务数据 |

四种模式互斥，切换必须停止进程并重启。T1 是自建维护记录的只读对象授权练习；T2 是独立虚构索引上的 SQL 注入原理模拟。T3 用 BP 修改客户端字段来观察授权差异，可参照工控软件 FUXA 的 [CVE-2026-43946 官方公告](https://github.com/frangoteam/FUXA/security/advisories/GHSA-fwcm-rqvw-j3p7)理解请求字段与授权校验的关系；原漏洞涉及 `/api/getTagValue` 和 `sourceScriptName`，本项目使用不同接口与字段，不宣称复现 FUXA 或验证其补丁。

## 使用范围

仅在本人控制且获批准的隔离教学环境运行与测试。默认监听 `127.0.0.1`。禁止公网端口映射，禁止对未授权服务运行测试，禁止导入真实生产数据、凭据或个人敏感信息。若意外发现真实连接或隔离失效，停止服务并按学校流程处理。

## 组件与数据流

```text
浏览器静态页面 + app.js
          │ 异步请求 JSON API
          ▼
Flask 登录/角色/对象授权/审计/重置
          ├── data/range.db      用户、设备、维护记录、会话、审计
          └── data/training.db   仅有虚构教学索引；检索时以只读方式打开
```

前端采用工业服务门户风格，展示虚构品牌“东门子”的设备服务中心。页面包含登录、普通维护员注册、设备列表、设备记录、指定记录详情、教学检索、报告预览、审计和管理员重置，提供加载、空结果、失败与会话过期提示。页面显示模式和构建号；显示数据库文字时使用 `textContent`，不把内容作为 HTML 执行。导航、卡片和页脚的“解决方案”“产品与服务”“技术支持”“联系我们”“最新动态”“资料下载”点击后从 `/api/portal/<feature>` 获取“该功能正在开发中”提示；没有虚构真实联系方式或外链。

## 仓库结构

| 文件 | 作用 |
|---|---|
| `lab.py` | 建表、虚构种子、Flask API、T1/T2/T3、权限、审计与重置 |
| `init_db.py` | 首次建库并生成本地演示凭据 |
| `run_range.py` | 选择一个模式并启动服务 |
| `reset_sandbox.py` | 虚拟机控制台恢复业务基线 |
| `static/` | 动态前端页面、脚本与样式 |
| `tests/test_lab.py` | 自动化功能与边界测试 |
| `scripts/` | Windows PowerShell 启动与测试入口 |
| `docs/test-matrix.md` | 完整检查矩阵及手工验证条件 |
| `docs/verification.md` | 本次实际核验结果与未完成的现场检查 |
| `docs/burp-exercise.md` | T3 的 Burp Suite 课堂练习、预期与复测记录格式 |
| `docs/实验指导手册.md` | 55 个测试点逐项操作步骤和证据要求 |

运行时生成的 `data/`、`evidence/`、`.env`、虚拟环境和数据库由 `.gitignore` 排除。不要把用户自己的课堂日志、截图、凭据或数据库提交到 GitHub。

## Windows 虚拟机安装

先安装 Git 和 Python 3.11 或更新版本。在 PowerShell 中拉取仓库，并进入靶场目录。后续命令都在这个目录运行：

```powershell
git clone https://github.com/alen875/AI-security-learning.git
cd AI-security-learning\dongmenzi-lab
py -3 --version
```

如果已经拉取过仓库，在 `AI-security-learning` 目录运行 `git pull`，再进入 `dongmenzi-lab`。更新前备份自己的 `data/` 和 `evidence/`；Git 不跟踪这些本地实验文件。

准备 Python 3.11 或更高的兼容版本，在**项目根目录**执行：

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe init_db.py
.venv\Scripts\python.exe run_range.py --mode safe
```

浏览器打开 `http://127.0.0.1:5000/`。另开一个 PowerShell 窗口，在同一目录运行下列命令检查当前状态和数据基线：

```powershell
Invoke-RestMethod http://127.0.0.1:5000/healthz
.venv\Scripts\python.exe check_data.py
```

先在本机完成安全状态的登录、设备和记录浏览。要切换训练点，在运行服务的窗口按 `Ctrl+C`，然后**一次只运行一个**模式；每次切换后在浏览器重新登录，并核对页面右上角的模式：

```powershell
.venv\Scripts\python.exe run_range.py --mode idor
# 停止后，按需改为 --mode sqli 或 --mode bp；结束时恢复 --mode safe
```

`idor`、`sqli`、`bp` 分别对应手册中的 T1、T2、T3。验证完成后恢复安全状态，再运行测试和重置：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe reset_sandbox.py --confirm RESET
.venv\Scripts\python.exe check_data.py
```

如果系统没有 `py` 命令，可把第一行换成 `python -m venv .venv`；其余命令继续使用 `.venv\Scripts\python.exe`。如果 5000 端口已被占用，所有启动命令加 `--port 5500`，浏览器和健康检查地址也改为 5500。

在已批准的完全隔离虚拟机里，依赖要先按学校流程获取并离线导入；可用 `pip install --no-index --find-links <批准的本地包目录> -r requirements.txt`。本仓库不自动联网下载包。

初始化会生成 `data/range.db`、`data/training.db` 和 `data/credentials.txt`。演示账号为 `maint_a`、`maint_b`、`admin`、`reviewer`，密码在首次初始化时随机生成，只保存在本机 `credentials.txt`。**该文件不可提交或截图公开。**运行地址默认为 `http://127.0.0.1:5000`。停止服务使用 `Ctrl+C`。

登录页提供“注册普通维护员账号”。账号需 3–32 位并以英文字母开头，密码至少 10 位。服务端固定分配 `maint` 角色，不能自行注册管理员或复核员。新账号没有预置设备或记录，可用于登录、普通教学检索和 T3 普通报告；验证 T1 的本人/他人记录请继续使用预置的 `maint_a`、`maint_b`。业务重置不会删除注册账号。

再次启动不必重新建库。若已存在数据库，`init_db.py` 会拒绝覆盖，避免误删证据或账号。恢复业务种子用下文的重置命令。

## Kali 与 Windows 靶机双机测试

默认回环绑定只允许 Windows 靶机自己访问。要让 Kali 连接，先在虚拟机管理器中配置**仅主机或私有隔离网络**，确认 Kali 与靶机均无通往公网或生产网络的路由，并记录两机的私有 IP。随后只在 Windows 靶机的**当前终端**显式设置批准标记，并绑定该私有网卡地址：

```powershell
$env:LAB_PRIVATE_NETWORK_APPROVED='yes'
.venv\Scripts\python.exe run_range.py --mode safe --host <Windows靶机私有IP> --port 5000
```

Windows 防火墙只允许 Kali 的私有 IP 访问指定端口；具体规则由实验环境管理员按获批网络设置。程序拒绝在缺少批准标记时绑定非回环地址。**批准标记只是防误操作检查，不能代替真实的网络隔离。**Kali 中先访问 `http://<Windows靶机私有IP>:5000/healthz`，核对返回模式，再访问首页。不要使用公网 IP 或把端口转发到互联网。

如果确实采用双虚拟机，Windows 管理员 PowerShell 可用下列**限定来源地址**的规则。将两个占位符换成实际私网 IP，先确认虚拟网卡属于 `Private` 配置，再执行；单机实验无需开放防火墙：

```powershell
$WinIP = '<Windows靶机私有IP>'
$KaliIP = '<Kali私有IP>'
New-NetFirewallRule -DisplayName 'Dongmenzi-Lab-Kali-5000' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000 -LocalAddress $WinIP -RemoteAddress $KaliIP -Profile Private
$env:LAB_PRIVATE_NETWORK_APPROVED = 'yes'
.venv\Scripts\python.exe run_range.py --mode safe --host $WinIP --port 5000
```

Kali 终端只对自己的靶机核验：

```bash
curl --fail --silent --show-error http://<Windows靶机私有IP>:5000/healthz
```

结束双机实验后停止服务；Windows 管理员 PowerShell 运行 `Remove-NetFirewallRule -DisplayName 'Dongmenzi-Lab-Kali-5000'` 删除此实验专用规则。若没有 `Private` 虚拟网络或无法确认地址，不执行双机步骤，继续用默认回环模式完成单机实验。

安全验证顺序：先用 `safe` 模式完成正常业务；保存数据库基线摘要；停止服务；分别以 `idor`、`sqli`、`bp` 模式启动，使用预置虚构账号和预审只读请求；每次切换记录模式、构建号、时间、请求与响应摘要；结束后回到 `safe` 并重置。T1 只用 `GET`；T2 只查询独立教学索引；T3 虽使用 `POST` 请求体，服务端只读取虚构报告并写审计，不修改业务数据。三项均不作数据库枚举、删除或耗时探测。

## API 摘要

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/lab/status`、`/healthz` | 状态、版本和存活检查 |
| POST | `/api/auth/login`、`/api/auth/logout` | 登录与注销 |
| POST | `/api/auth/register` | 注册普通维护员账号；角色由服务端固定 |
| GET | `/api/portal/<feature>` | 门户占位功能；仅允许六个预置入口，返回开发中状态 |
| GET | `/api/auth/me` | 当前身份和本会话的请求校验令牌 |
| GET | `/api/devices`、`/api/devices/{id}`、`/api/devices/{id}/records` | 授权范围内的设备和记录列表 |
| GET | `/api/records/{id}` | T1 只读详情训练点 |
| GET | `/api/training-search?q=` | T2 独立教学索引训练点 |
| POST | `/api/training/report-preview` | T3 请求参数篡改训练点；需要会话和 `X-CSRF-Token` |
| GET | `/api/audit` | 管理员及复核员查看最近审计 |
| POST | `/api/admin/reset` | 管理员恢复业务基线，须带本会话 `X-CSRF-Token` |

接口返回 JSON。状态为 `401` 表示未登录，`403` 表示无权限，`404` 表示对象不存在。教学索引的普通查询使用数字编号 `1` 至 `4`。在 `sqli` 模式中，可由教师审定一条只读的布尔条件输入，比较与 `safe` 模式返回的虚构索引条数；不要把这一教学输入用于其他站点。

## 测试、重置与证据

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe reset_sandbox.py --confirm RESET
```

自动化测试用独立临时数据库，覆盖模式互斥、登录与注销、会话、角色、T1/T2/T3 对照、主业务数据完整性、只读索引、审计、重置和失败回滚。运行结果以你本机输出为准；`docs/test-matrix.md` 区分可自动化项与需要在实际虚拟机手工检查的网络、浏览器和课堂流程项。

重置会恢复设备与维护记录的**内容**，并以内容摘要核对完整基线；保留用户、会话、审计及重置历史。控制台重置属于有权操作虚拟机的管理员行为，命令需要显式 `--confirm RESET`；Web 重置另要求管理员会话和令牌。重置只面向虚构业务数据，不能代替虚拟机快照或学校的实验结束销毁流程。

证据建议记录：代码构建号、模式、种子版本、虚拟机及网络摘要、执行人角色、预置对象、请求时间、响应摘要、审计事件、重置前后摘要和本地证据路径。**代码或 AI 说明不能当成实际运行证据。**未运行的检查请写“未执行”。

## 已知限制和发布检查

- 本项目是教学模拟，未获得真实工控产品的旧版安装包或厂商补丁，不能用于“真实产品补丁复现”的课程要求。
- 目前自动化测试基于 Flask 测试客户端；浏览器视觉效果、Windows/Kali 双机互通和公网不可达需要在获批环境另行核验。
- 单机 SQLite 方案适合小组分时训练，不提供多班次隔离、并发负载或生产级高可用能力。
- 公开 GitHub 前确认六名组员的代码授权、教师对课程材料公开的要求，以及依赖许可。本仓库暂不附软件许可证；不要代替权利人决定开源许可。
- 发布前检查 `git status`，确保 `data/`、`evidence/`、凭据、日志和课堂个人材料均未被追踪。
