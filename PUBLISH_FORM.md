# WorkBuddy 开放平台 · 上架表单文案（直接复制）

> 配合 `workbuddy-checkin.zip` 与 `icon_512.png` 使用。
> 平台：https://open.workbuddy.cn → 发布管理 → 技能 → 创建

---

## ① 技能包

| 项 | 值 |
|---|---|
| 文件 | `workbuddy-checkin.zip`（20 文件，约 64 KB，≤3MB ✓） |
| 顶层目录 | `workbuddy-checkin/`（与 SKILL.md 的 `name` 一致 ✓） |

## ② 展示信息

### 市场展示名称（中文）
```
WorkBuddy 云端签到自愈守护
```

### 市场展示名称（英文）
```
WorkBuddy Cloud Check-in with Self-Healing
```

### 版本号
```
2.1.0
```

### 头像
`icon_512.png` —— 512×512 PNG，139.7 KB（≤500KB ✓）
（平台表单**独立上传**图标，不会从 zip 里读）

### 市场展示分类
```
效率工具
```

### 服务类目（至少选 1 个，最多 5 个）
```
效率工具
数据统计
办公自动化
```
> 按平台实际可选项挑最贴近的。

---

## ③ 技能介绍（市场卡片上显示的长文）

### 中文版
```
WorkBuddy「Buddy 加油站」每日签到全自动化。

【核心能力：云端签到自愈守护】
· 云端定时签到 —— 脚本跑在金山文档云端引擎，由平台自己的定时任务触发。
  电脑关机、客户端没开、WorkBuddy 退出，照样按时签到。
· 令牌自动续期 —— 每次运行自动换新令牌并回写表格，令牌长期自我维持，
  不需要手工更新，也不用担心过期。
· 失败自动自愈 —— 守护程序每天检查状态，失败时自动取新令牌、更新部署、
  远程立即重签，并回读校验。

【本机签到】
Windows 下扫描 WorkBuddy 客户端进程内存提取 atRestSecretKey，
解密登录态信封（AES-256-GCM，按 keyId 校验以排除内存中的 base64 诱饵），
无需重启客户端即可完成刷新、签到与连签查询。

【上手】
路径 A（本机签到）：双击 scripts\install.bat —— 自动体检环境并跑一次真实签到。
路径 B（云端签到）：需一次性配置金山文档智能表格 + AirScript 定时任务，
之后永久免维护。

【环境要求】
Windows 10/11；已登录并运行中的 WorkBuddy 客户端；Python 3 与 Node.js 18+
（脚本会自动探测 WorkBuddy 自带的 Node）。云端签到需使用金山文档「智能表格」。

【隐私】
解密仅在本机进行，密钥与令牌不外传（仅在调用签到/刷新接口时上行，这是功能必需的）。
表格内 B1 为明文令牌，请将表格权限设为「仅自己可见」。
```

### 英文版
```
Fully automate the WorkBuddy "Buddy Station" daily check-in.

[Core: cloud check-in with self-healing]
· Cloud scheduled check-in — the script runs on Kingsoft Docs' cloud JS engine and
  is fired by the platform's own scheduler. Your PC may be off, the client closed,
  WorkBuddy exited — it still signs in on time.
· Automatic token renewal — every run exchanges the refresh token and writes it
  back, so the token stays fresh indefinitely. No manual updates, no expiry worries.
· Failure self-healing — a daily guard checks the status; on failure it fetches a
  new token, redeploys, re-signs remotely and verifies the result.

[Local check-in]
On Windows it scans the WorkBuddy client process memory for atRestSecretKey,
decrypts the login-state envelope (AES-256-GCM, validated by keyId to filter out
base64 decoys), and completes refresh / check-in / streak query without needing
a client restart.

[Getting started]
Path A (local): double-click scripts\install.bat — it checks the environment and
runs a real check-in.
Path B (cloud): one-time setup of a Kingsoft Docs Smart Sheet + AirScript
scheduled task, then hands-off forever.

[Requirements]
Windows 10/11; a logged-in WorkBuddy client that is running; Python 3 and
Node.js 18+ (the bundled Node is auto-detected). Cloud mode requires a
Kingsoft Docs Smart Sheet (.ksheet).

[Privacy]
Decryption happens entirely on your machine; keys and tokens are never uploaded
except to the check-in/refresh endpoints themselves, which is inherent to the
feature. Cell B1 holds a plaintext token — set the sheet to "only me".
```

---

## ④ 「试试这样问我」示例（建议 5 条，平台要求至少 3 条）

```
帮我 WorkBuddy 签到一下
我的连签多少天了？还差几天拿满奖励
提取一份新的 refreshToken 给我
为什么签到报 code=12153 invalid_grant
把签到令牌写进金山文档表格的 B1
```

---

## ⑤ 边界与红线（建议写进介绍或备注）

```
· 仅支持 Windows（本机取密钥依赖 Win32 进程内存读取）；macOS/Linux 需改用
  workbuddy-token-extract（CDP 方案）。
· 需要 WorkBuddy 客户端已登录并处于运行状态，否则取不到解密密钥。
· 云端签到必须使用金山文档「智能表格」（.ksheet）—— 外部调用所需的
  「脚本令牌」只在智能表格提供，普通表格（.xlsx）没有。
· AirScript-Token 与 refresh_token 属个人隐私凭证，脚本只写表格、不外传；
  请把存放令牌的表格设为「仅自己可见」，切勿提交到任何仓库。
· 本 Skill 的接口逆向自客户端实现，非官方文档，客户端更新可能导致接口变动；
  请自行确保遵守相关服务条款。
· 签到结果以服务端返回为准，积分规则由官方决定。
```

---

## ⑥ 发布流程（照着点）

1. 打开 https://open.workbuddy.cn → **微信扫码登录**
2. 首次进入按提示完成 **个人或企业认证**（未认证无法发布）
3. 左侧「**发布管理**」→「**技能**」→ 右上角「**创建**」
4. **第 1 步 配置技能**
   - 类型：技能
   - 上传压缩包：拖入 `workbuddy-checkin.zip`
   - 展示名称 / 版本 / 头像 / 市场分类 / 服务类目：按上面表格填
   - 点「继续」
5. **第 2 步 确认信息**
   - 右侧预览卡片核对无误
   - 点「继续」
6. **第 3 步 提交审核**
   - 点「提交审核」
   - ⚠️ 官方口径 **约 7 个工作日**
7. **审核通过后**
   - 状态变为「待发布」
   - 回到「技能列表」→ 点「**发布**」→ 选「**公开发布**」→ 确定
   - ⚠️ **不做这步资产会一直躺在后台，别人搜不到**（最常见的漏步）
8. **补全开发者信息**（发布前必填，否则发布失败）
9. 发布后在 WorkBuddy 客户端的技能入口搜「云端签到自愈守护」验证能搜到

---

## ⑦ 发布前自检

- [x] 包内每个 .md 都有 YAML frontmatter（name + description）
- [x] 顶层目录 `workbuddy-checkin/` 与 `name` 一致
- [x] 目录名与 SKILL.md 的 name 字段一致
- [x] 包内无令牌 / 凭据 / 实例 ID（逐文件 grep 复检）
- [x] 包内无 `scripts/out/`、`plan.json`、`deploy/` 等运行时产物
- [x] 图标 512×512、≤500KB、无水印
- [x] 描述含「谁用 / 解决什么具体问题」
- [x] 触发词已写进 SKILL.md 的 description
- [x] ≥3 条「试试这样问我」示例
- [x] 边界与红线写清
- [ ] 开发者信息已补全
- [ ] 审核通过后记得点「发布」
