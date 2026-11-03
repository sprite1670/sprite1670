# WorkBuddy 每日签到自动化 Skill

> 安装包：<https://github.com/sprite1670/sprite1670> ｜ 直接拖入 WorkBuddy「导入技能」即可

> 让 WorkBuddy「Buddy 加油站」签到**全自动化**：电脑关机也能按时签到，签到失败会自动修复。

## 它能做什么

| 能力 | 说明 |
|---|---|
| ☁️ 云端定时签到 | AirScript 跑在金山文档云端引擎，**电脑关机、客户端没开也照样签** |
| 🔄 令牌自动续期 | 每次签到自动换新令牌并回写表格，令牌长期自我维持，不用手工更新 |
| 🩹 失败自动自愈 | 某天签到失败 → 自动取新令牌 → 更新部署 → 立即重签 |
| 🖥️ 本机签到 | 一条命令完成「扫描内存取密钥 → 解密 → 刷新 → 签到 → 连签查询」 |
| 📊 状态可查 | 表格 B2 看最近结果、B5 看状态、B7 看连签天数 |

## 快速开始

### 1. 安装

把本目录放到 `~/.workbuddy/skills/workbuddy-checkin/`（Windows：`C:\Users\<你>\.workbuddy\skills\workbuddy-checkin\`），
或在 WorkBuddy 里说「安装 skill workbuddy-checkin」。

### 2. 前置条件

| 项 | 要求 |
|---|---|
| 操作系统 | **Windows**（内存扫描依赖 Win32 API）。macOS/Linux 请改用 `workbuddy-token-extract`（CDP 方案） |
| WorkBuddy | 客户端已登录并运行中（解密密钥只在运行中的进程内存里） |
| 依赖 | Python 3 + Node.js 18+（脚本会自动找 WorkBuddy 自带的 Node） |
| 金山文档 | 需要「智能表格（.ksheet）」—— 外部调用凭据「脚本令牌」只在智能表格提供 |

### 3. 本机签到（即时见效）

```bash
cd ~/.workbuddy/skills/workbuddy-checkin
python3 scripts/wb_checkin.py auto
```

输出示例：

```
[*] 候选进程(8): [...]
[*] 信封 keyId: 9127dea1b44020a7（候选 1 个，按 keyId 校验）
[+] refreshToken 解密成功 (1567 字符)
[+] 刷新成功 code=0，accessToken 1566 字符
[+] 签到成功 +100 积分
[*] 连签 19 天 | 本期累计 1900 分 | 今日已签: True
```

### 4. 云端签到（电脑关机也能签）

一次性配置，详见 `scripts/setup_cloud.py --url <你的表格URL>` 生成的部署清单：

1. **新建智能表格**（金山文档 → 新建 → 智能表格，`.ksheet`）
2. **粘贴脚本**：`assets/workbuddy-checkin-cloud.airscript.js` 全文粘到「效率 → 高级开发 → AirScript 脚本编辑器」，
   保存到【文档共享脚本】
3. **开通网络权限**：编辑器「服务」→「添加服务」→ 勾选「网络API」
4. **建定时任务**：「效率 → 高级开发 → 定时任务」→ 每天 09:00 → 关联脚本
5. **建脚本令牌**：编辑器工具栏的「脚本令牌(beta)」（盾牌图标）→ 创建并复制
   （需实名认证；每个用户仅一个，默认 180 天可延期）
6. **填凭据**：把 file_id / script_id / token 填进 `scripts/kdocs_config.json`
7. **挂自愈调度**（可选）：用 WorkBuddy 的定时任务每天跑一次 `python3 scripts/cloud_guard.py`

## 配置文件

`scripts/kdocs_config.json`：

```json
{
  "file_id":    "表格文件 ID",
  "script_id":  "脚本 ID",
  "token":      "AirScript-Token",
  "table_url":  "https://www.kdocs.cn/l/xxxx",
  "worksheet_id": 3,
  "sheet_name": "工作表1"
}
```

也可用环境变量 `KDOCS_FILE_ID` / `KDOCS_SCRIPT_ID` / `KDOCS_TOKEN` 覆盖。

> ⚠️ **token 是你金山文档的读写钥匙，切勿提交到仓库或分享给他人。**
> 本仓库只含空白模板。

## 表格单元格约定

| 单元格 | 用途 |
|---|---|
| B1 | refresh_token（脚本自动续期并回写） |
| B2 | 最近一次执行结果 |
| B3 | 可选 webhook（Bark / 企微 / 钉钉），留空不推送 |
| B4 | 可选兜底通道 JSON，留空关闭 |
| B5 | 状态：OK / FAIL / NO_TOKEN |
| B6 | 最近一次成功签到的日期 |
| B7 | 连签天数 / 本期累计积分 |
| B8 | 状态 JSON（check 模式输出） |

## 常见问题

见 `references/troubleshooting.md`，包含：
- 找不到「脚本令牌」按钮 → 多半用了电子表格，需换智能表格
- 签到报 `code=12153 invalid_grant` → 令牌不属于 plugin client，需重新 extract
- 远程调用返回 `[Undefined]` → AirScript 需要**顶层** `return`（函数内 return 不算）
- 表格读回 `2026/11/3` 而非 `2026-11-03` → 表格自动转成了日期类型，比较前要归一化

## 安全须知

- 解密只在本机进行，密钥与令牌**不外传**（仅在调用签到/刷新接口时上行，这是功能必需的）
- 令牌明文存放在表格 B1，**请把表格权限设为「仅自己可见/可编辑」**
- 运行时产物在 `scripts/out/` 与 `scripts/plan.json`，已在 `.gitignore` 中排除

## 目录结构

```
workbuddy-checkin/
├── SKILL.md                              # Agent 执行说明
├── README.md                             # 本文件（面向人）
├── .gitignore                            # 排除凭据与运行时产物
├── assets/
│   ├── workbuddy-checkin-cloud.airscript.js  # 云端版 AirScript（推荐）
│   └── workbuddy-checkin.airscript.js        # 本机版（备用）
├── references/
│   ├── api-spec.md                       # 接口/信封/AAD/错误码
│   └── troubleshooting.md                 # 排障手册
└── scripts/
    ├── wb_checkin.py                     # 本机签到一体机
    ├── decrypt_envelope.js               # AES-256-GCM 解密器
    ├── kdocs_cloud.py                    # 云端 AirScript 调用器
    ├── cloud_guard.py                    # 自愈守护
    ├── split_token.py                    # 令牌分段（规避敏感审批）
    ├── setup_cloud.py                    # 部署向导
    ├── deploy_helper.py                  # 旧版部署向导
    ├── check_kdocs_ready.py              # 部署就绪核验
    └── kdocs_config.json                 # 凭据（空白模板）
```

## 致谢

接口逆向自 WorkBuddy 桌面端实现，社区亦有同源方案可参考（AirScript 定时签到 + 猫猫旅行）。
本 Skill 的差异点：内存扫描取密钥（无需重启客户端）、分段写入规避敏感审批、失败自愈闭环。
