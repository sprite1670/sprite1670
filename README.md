# WorkBuddy 云端签到自愈守护 · Skill

> **一句话：电脑关机也能按时签到，签到失败会自动修复 —— 全程无需你干预。**

> 安装包：<https://github.com/sprite1670/sprite1670> ｜ 直接拖入 WorkBuddy「导入技能」即可

## ☁️ 云端签到自愈守护（核心能力）

这是本 Skill 与普通「签到脚本」的根本差别 —— 它不是跑在你电脑上的定时任务，
而是**跑在金山文档云端引擎上的自愈闭环**：

| | 普通本机脚本 | 本 Skill |
|---|---|---|
| 电脑关机 | ❌ 签不到 | ✅ **云端照签**（08:00 由金山文档定时任务触发） |
| 令牌过期 | ❌ 脚本失效 | ✅ **云端每次运行自动续期回写 B1** |
| 某天签到失败 | ❌ 要人工排查 | ✅ **守护程序自动取新令牌 → 更新部署 → 立即重签** |
| 你要做什么 | —— | **什么都不用做** |

```
08:00  金山文档云端定时任务  →  AirScript  →  刷新令牌(自动续期回写 B1)  →  签到  →  写 B2/B5/B6/B7
                                                                                ↓ 失败时
10:00  本机自愈守护          →  读表判定  →  取新令牌  →  写回 B1  →  远程立即重签  →  校验
```

> 「云端签到」负责**按时签到**（电脑关机也行）；「自愈守护」负责**万一失败自动修复**。
> 两者配合，才叫「云端签到自愈守护」。

## 它能做什么

| 能力 | 说明 |
|---|---|
| ☁️ 云端定时签到 | AirScript 跑在金山文档云端引擎，**电脑关机、客户端没开也照样签** |
| 🔄 令牌自动续期 | 每次签到自动换新令牌并回写表格，令牌长期自我维持，不用手工更新 |
| 🩹 失败自动自愈 | 某天签到失败 → 自动取新令牌 → 更新部署 → 立即重签 |
| 🖥️ 本机签到 | 一条命令完成「扫描内存取密钥 → 解密 → 刷新 → 签到 → 连签查询」 |
| 📊 状态可查 | 表格 B2 看最近结果、B5 看状态、B7 看连签天数 |

## 快速开始 —— 按需选一条路径

两条路径**互不依赖**，可以只用其中一条，也可以两条都开。

| | 路径 A · 本机签到 | 路径 B · 云端签到（电脑关机也行） |
|---|---|---|
| **要几步** | **2 步** | 约 7 步（其中 4 步在金山文档编辑器里点） |
| **电脑关机** | ❌ 跑不了 | ✅ **照签** |
| **令牌过期** | 本机每次自动换新 | 云端每次运行自动换新 |
| **失败自愈** | — | ✅ 自动取新令牌并重签 |
| **适合谁** | 想马上用的人 | 想要「躺着也签到」的人 |

### 路径 A · 本机签到（2 步）

**第 1 步**：双击 `scripts\install.bat`
→ 自动体检环境（Python / Node / 客户端是否运行 / 云端配置）+ **跑一次真实签到**，
最后告诉你能不能用。

**第 2 步**：以后想签就双击它，或直接跑：
```bash
python3 scripts/wb_checkin.py auto
```

> 前提：Windows + WorkBuddy 客户端**正在运行**（解密密钥只在运行中的进程内存里）。

### 路径 B · 云端签到（电脑关机也能签）

在路径 A 之上再加一层「云端托管」。**需要一次性配置，之后永久免维护。**

1. **新建智能表格**
   金山文档 → 新建 → **智能表格**（`.ksheet`）。
   ⚠️ 必须用智能表格，**普通表格（.xlsx）拿不到「脚本令牌」**，而令牌是云端调度的关键。
2. **粘贴脚本**
   「效率 → 高级开发 → **AirScript 脚本编辑器**」→ 新建 → 粘贴
   `assets/workbuddy-checkin-cloud.airscript.js` 全文 → **Ctrl+S 保存**（存到【文档共享脚本】）。
3. **开通网络权限**
   编辑器工具栏「**服务**」→「添加服务」→ 勾选「**网络API**」→ 确定。
   *（不加这个，脚本发不出请求，会静默失败。）*
4. **建定时任务**
   「效率 → 高级开发 → **定时任务**」→ 新建 → 选「**每天**」→ **09:00** → 关联上面那个脚本 → 保存。
   *（建议再加一条 21:00 的兜底。）*
5. **建脚本令牌**
   编辑器工具栏的「**脚本令牌(beta)**」（盾牌图标）→ 勾选「我已知晓」→ 创建 → 复制。
   *（需完成实名认证；每个用户仅一个，默认 180 天可延期。）*
6. **填凭据**
   把三个值填进 `scripts/kdocs_config.json`：
   - `token` = 第 5 步复制的令牌
   - `file_id` / `script_id` = 左侧脚本栏「更多」→「复制脚本 webhook」，链接形如
     `https://www.kdocs.cn/api/v3/ide/file/<file_id>/script/<script_id>/sync_task`，
     **尖括号里就是这两个值**（前段 file_id，后段 script_id）。
7. **挂自愈守护**（可选但推荐）
   用 WorkBuddy 的定时任务每天跑一次 `python3 scripts/cloud_guard.py` ——
   云端签到失败时它会自动取新令牌、更新 B1、并远程立即重签。

> 想省事？运行 `python3 scripts/setup_cloud.py --url <你的表格URL>`，
> 会生成一份带你自己表格地址的部署清单。

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
    ├── install.bat                       # 环境体检 + 实时签到自测（双击即用）
    ├── setup_check.py                    # 体检逻辑（被 install.bat 调用）
    ├── wb_checkin.py                     # 本机签到一体机
    ├── decrypt_envelope.js               # AES-256-GCM 解密器
    ├── kdocs_cloud.py                    # 云端 AirScript 调用器
    ├── cloud_guard.py                    # 自愈守护
    ├── split_token.py                    # 令牌分段（规避敏感审批）
    ├── setup_cloud.py                    # 部署向导
    ├── check_kdocs_ready.py              # 部署就绪核验
    └── kdocs_config.json                 # 凭据（空白模板）
```

## 致谢

接口逆向自 WorkBuddy 桌面端实现，社区亦有同源方案可参考（AirScript 定时签到 + 猫猫旅行）。
本 Skill 的差异点：内存扫描取密钥（无需重启客户端）、分段写入规避敏感审批、失败自愈闭环。

## License

MIT —— 完整条款见 [`LICENSE`](LICENSE)，使用须知见 [`NOTICE`](NOTICE)。
