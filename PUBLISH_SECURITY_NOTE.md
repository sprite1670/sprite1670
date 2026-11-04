# 平台「加密提示 / 安全说明」字段填写文本

> 用途：平台第 3 次驳回要求「请填写加密提示信息」。
> 下面三段分别是**推荐粘贴版**、**精简版**、**英文版**，按平台字段长度限制选一个。

---

## 一、推荐版（中文，约 480 字）

本技能涉及登录凭据的使用，已在 GitHub 仓库公开披露完整安全声明：
**https://github.com/sprite1670/sprite1670/blob/main/SECURITY.md**

能力与风险说明：

1. **能力范围**：本技能用于自动化签到与失败自愈，核心依赖用户本人账号的登录凭据
   （refresh_token / access_token）与用户自行创建的脚本令牌（AirScript-Token）。
   所有凭据均由用户在本机自行维护并填入表格 B1 单元格。

2. **版本差异**：本次提交的发布包**不包含**任何从其他应用进程内存中提取或解密登录凭据的能力。
   该能力仅存在于 GitHub 仓库的完整版本中，供用户在自有账号、受信任的个人设备上自行使用，
   并已在仓库 README、NOTICE、SKILL.md 与 SECURITY.md 中显式标注其风险。
   GitHub 仓库中不含任何真实凭据，仅含空白配置模板。

3. **已采取的安全措施**：
   - 全程本地执行，凭据仅在调用签到/刷新接口时上行，不经过任何第三方服务器；
   - 真实配置文件与运行时产物（scripts/kdocs_config.json、scripts/out/、scripts/plan.json）
     均已通过 .gitignore 排除，仓库与发布包仅含空白模板；
   - 建议用户将存放令牌的表格权限设置为「仅自己可见/可编辑」；
   - 敏感凭据扫描自检（10 项）与残留令牌扫描在打包时自动执行并全部通过。

4. **风险提示**：登录凭据等价于用户登录态，一旦泄露即等同于账号被接管；
   自动化调用可能与相关服务条款冲突。请使用者自行确认合规性并承担相应责任。

---

## 二、精简版（约 120 字，适合字段较短时）

本技能使用用户本人账号的登录凭据（refresh_token / access_token）与用户自行创建的脚本令牌，
凭据由用户本机维护并存入表格 B1。本次发布包**不包含**从其他应用进程内存提取或解密登录凭据的能力；
该能力仅存在于 GitHub 完整版仓库，已在 SECURITY.md 中显式披露风险。
仓库与发布包仅含空白配置模板，不含任何真实凭据。凭据泄露即等同于账号被接管，
自动化调用可能与相关服务条款冲突。详见：
**https://github.com/sprite1670/sprite1670/blob/main/SECURITY.md**

---

## 三、英文版（English, ~450 words)

This skill uses the user's own login credentials (`refresh_token` / `access_token`) and the
script token the user creates. Credentials are maintained by the user on their own machine
and placed in cell B1 of their sheet.

**This published build does NOT contain any capability to extract or decrypt login
credentials from another application's process memory.** That capability exists only in the
full version on GitHub, where it is explicitly disclosed — in README, NOTICE, SKILL.md and
SECURITY.md — together with its risks. Users must only run it with their own account, on a
personal device they trust. The repository and the published package contain **empty
configuration templates only**; no real credentials are ever committed.

Security measures in place:
- Everything runs locally; credentials are only sent to the check-in/refresh endpoints
  themselves and never pass through a third-party server.
- Real config files and runtime artifacts (`scripts/kdocs_config.json`, `scripts/out/`,
  `scripts/plan.json`) are excluded via `.gitignore`.
- Users are advised to set the sheet holding the token to "only me" permissions.
- An automated 10-item self-check plus a sensitive-token residue scan runs at package time
  and passes completely.

Risk notice: login credentials are equivalent to the user's session, so any leak means account
takeover; automated calls may conflict with the applicable terms of service. Users are
responsible for verifying compliance and accepting the risk.

Full disclosure: **https://github.com/sprite1670/sprite1670/blob/main/SECURITY.md**

---

## 四、填写要点提醒

| 项 | 填写内容 |
|---|---|
| 版本号 | `2.0.2`（必须大于上次的 2.0.1，否则会被拒） |
| 上传包 | `sprite-workbuddy-checkin-v2.zip`（209.5 KB / 24 文件） |
| 加密提示/安全说明 | 从上面三段中选一段粘贴；字段较紧就用「精简版」 |
| 如平台提供"安全检测报告"上传位 | 可上传 `SECURITY.md` 的 PDF/截图，或直接贴 GitHub 链接 |
| 头像 | `icon_512.png`（512×512 PNG） |

> ⚠️ 如果平台的「加密提示」字段实际要求填写**文件加密/密码保护**相关说明（例如要求包体加密或
> 校验值），而不是安全风险声明，请告诉我该字段的原文提示，我按它的语义另出一份文案。
