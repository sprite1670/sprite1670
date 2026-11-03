# WorkBuddy Skill 上架 · 表单填写清单

> **本文档的读者是「想把 skill 发布到市场的人」。**
> 如果你只是想**使用**这个 skill（装到自己电脑、跑签到），请看 [`README.md`](README.md)，
> 那里有从导入到日常运维的完整路径，不需要管上架流程。
>
> 本文档仅在你决定「发布给所有人」时才需要。

## 一、两个渠道选一个

| 渠道 | 地址 | 特点 | 适合 |
|---|---|---|---|
| **A. 开放平台** | `open.workbuddy.cn` | 腾讯官方，全网可见，**约 7 个工作日**审核 | 正式发布、长期维护 |
| **B. SkillHub** | `skillhub.cn` | 腾讯 SkillHub 市场，审核较快 | 快速上架、试水 |

> 本机安装无需审核：直接把 `workbuddy-checkin/` 放进 `~/.workbuddy/skills/` 即可，已在你机器上生效。

---

## 二、需要准备的东西（都准备好了）

| 项 | 值 | 状态 |
|---|---|---|
| 技能包 | `C:\Users\Administrator\Downloads\workbuddy-checkin.zip` | ✅ 59.9 KB（限 3MB） |
| 顶层目录 | `workbuddy-checkin/` | ✅ 与 SKILL.md 的 `name` 一致 |
| 文件数 | 17 | ✅ |
| 图标 | 512×512 PNG，≤500 KB | 见下方「图标」一节 |
| 名称（中文） | `WorkBuddy 每日签到助手` | 建议 |
| 名称（英文） | `WorkBuddy Daily Check-in` | 建议 |
| 版本 | `2.0.0` | 与 SKILL.md 一致 |
| Slug | `workbuddy-checkin` | 小写 + 短横线 |

---

## 三、开放平台表单（open.workbuddy.cn）

### 第 0 步 · 前置
1. 浏览器打开 `open.workbuddy.cn`
2. **微信扫码登录**
3. 首次进入需完成**个人或企业认证**（未认证无法发布）
4. 补充「开发者信息」（发布前必须补全，否则点发布会失败）

### 第 1 步 · 配置技能
路径：左侧「**发布管理**」→「**技能**」→ 右上角「**创建**」

| 表单项 | 填写内容 |
|---|---|
| 类型 | 技能 |
| 上传压缩包 | 拖入 `workbuddy-checkin.zip`（≤3MB，仅 .zip） |
| 展示名称 | `WorkBuddy 每日签到助手` |
| 版本 | `2.0.0` |
| 头像 | 512×512 PNG，≤500KB（**独立上传项**，平台不从 zip 里读） |
| 市场分类 | 效率工具 |
| 服务类目 | 至少选 1 个，最多 5 个。建议：`效率工具` / `数据统计` |
| 技能介绍 | 见下方文案 |

**服务类目**如果可选范围不同，按实际可选项挑最贴近的（自动化 / 办公效率 / 效率工具）。

### 第 2 步 · 确认信息
- 右侧预览卡片确认无误
- 平台会自动解析出技能 ID

### 第 3 步 · 提交审核
- 点「提交审核」
- ⚠️ **官方口径约 7 个工作日**
- 审核结果通过「通知」告知
- 企业账号可能还有管理员审核环节

### 第 4 步 · 发布上架（**最容易漏的一步**）
审核通过后，资产状态变成「待发布」：
1. 在「**技能列表**」找到该技能
2. 点「**发布**」
3. 弹窗里选「**公开发布**」
4. 确定

> 不做这一步，资产会一直躺在后台，别人搜不到。

### 第 5 步 · 验证
在 WorkBuddy 客户端的技能入口搜索 `WorkBuddy 每日签到` / `workbuddy-checkin`，确认能搜到并可安装。

---

## 四、SkillHub 表单（skillhub.cn）

1. 打开 `skillhub.cn` → 登录 → 右上角「**发布团队 skill**」
2. 选择发布类型（免费版）
3. 上传 `workbuddy-checkin.zip`，填基本信息
4. 提交审核 → 平台安全检测通过后自动上架

> 也有 CLI 方式（适合经常迭代）：
> ```bash
> skillhub login        # 浏览器 OAuth，凭证存 ~/.skillhub/auth.json
> skillhub init --name workbuddy-checkin --category 办公效率
> skillhub push
> skillhub publish --visibility public
> ```

---

## 五、表单文案（直接复制）

### 中文介绍（市场展示用）
```
WorkBuddy「Buddy 加油站」每日签到全自动化。电脑关机、客户端没开也能按时签到——
脚本跑在金山文档云端引擎，令牌自动续期，不用手工更新；某天签到失败会自动
取新令牌、更新部署并立即重签。也可在本机一条命令完成取密钥→解密→签到→查连签。
```

### 英文介绍
```
Fully automate the WorkBuddy "Buddy Station" daily check-in — it signs in even
with your PC powered off. The script runs on Kingsoft Docs' cloud engine and
renews its own token, so there is nothing to update by hand. When a check-in
fails, it fetches a fresh token, redeploys and re-signs automatically.
```

### 触发词（写进 description，命中率靠它）
```
WorkBuddy 签到、Buddy 加油站、每日签到、自动签到、领积分、连签、提取 refreshToken、
换新令牌、令牌解密、写入金山文档、B1、AirScript 签到、云端签到、电脑关机签到、
定时签到、签到失败 code=12153、invalid_grant、刷新失败、WorkBuddy 打卡、派猫猫旅行
```

### 「试试这样问我」示例（至少 3 条，建议 5 条）
```
帮我 WorkBuddy 签到一下
我的连签多少天了？还剩几天拿满奖励
提取一份新的 refreshToken 给我
为什么签到报 code=12153 invalid_grant
把签到令牌写进金山文档表格的 B1
```

### 边界与红线（建议写进 SKILL.md 或介绍里）
```
· 仅支持 Windows（本机取密钥依赖 Win32 进程内存读取）
· 需要 WorkBuddy 客户端已登录并运行中
· 云端签到需使用金山文档「智能表格」，脚本令牌只在 .ksheet 提供
· 令牌与 AirScript-Token 属个人隐私凭证，切勿外传；表格请设为「仅自己可见」
· 本 Skill 逆向自客户端实现，接口可能随版本变动；请遵守相关服务条款
```

---

## 六、图标

开放平台的图标是**独立上传项**，要求 512×512 PNG、≤500KB。

三种获取方式：
1. **AI 生成**（消耗 5-10 积分，可指定 1024x1024 后缩放）
2. **自己画**：任何 512×512 PNG 都行，建议深色底 + 简洁符号
3. **先跳过**：上传表单时若图标非强制，可先用默认，之后再补

参考视觉方向：深蓝底 + 加油站/日历/签到勾选意象，避免用品牌 Logo 与官方混淆。

---

## 七、发布前自检清单

- [x] YAML `冒号后有空格`（`name: xxx`，不是 `name:xxx`）
- [x] 中英文名与描述齐全
- [ ] 头像 512×512、≤500KB
- [x] 触发词已写进 description
- [x] ≥3 条「试试这样问我」示例
- [x] 边界与红线写清
- [ ] 新对话里实测 5 个问题都能触发
- [ ] 开发者信息已补全（否则发布失败）
- [x] 包内**无任何令牌/凭据/实例 ID**（已逐文件 grep 复检）
- [x] 目录名与 `name` 字段一致
- [ ] 审核通过后**记得点「发布」**

---

## 八、迭代建议

发布后 → 收集真实使用反馈 → 改 `SKILL.md` 的 description（影响触发命中）
→ 改版本号 → 重新打包上传。

改完记得重跑脱敏扫描（见 `CONTRIBUTING.md` 的「发布前强制脱敏扫描」），
`package_skill.py` **不认 `.gitignore`**，务必先清 `scripts/out/` 和 `scripts/plan.json`。
