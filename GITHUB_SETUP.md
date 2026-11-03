# GitHub 仓库设置清单（一次性，2 分钟）

仓库：https://github.com/sprite1670/sprite1670

## ✅ 已自动完成（不用管）

| 项 | 状态 |
|---|---|
| 推送到 GitHub | ✅ 21 个文件，8 次提交 |
| 内容脱敏 | ✅ 逐文件 grep 复检，无令牌/凭据/实例ID |
| License 识别 | ✅ GitHub 已正确识别为 MIT |
| README 双语 + 目录结构 | ✅ |
| 提交历史干净 | ✅ filter-branch 清过一次误入的 token |

## ⬜ 需要你在网页改（3 项，各 30 秒）

打开仓库首页 → 右侧栏或顶部 **⚙ Settings**，逐项填：

### 1. Description（仓库卡片、搜索结果里最先看到的一句）

```
WorkBuddy 云端签到自愈守护 —— 电脑关机也能按时签到，签到失败自动修复，全程无需人工干预。云端 AirScript 跑在金山文档云端引擎，令牌自动续期；失败自愈守护自动取新令牌并重签。
```

> ⚠️ GitHub 的 Description 上限 **350 字符**，上面这句约 100 字，可以直接贴。

### 2. Topics（GitHub 仓库搜索的主要索引维度，不设就很难被搜到）

Settings → 左侧 **Topics** → 添加（每个点一下 Add）：

```
workbuddy
automation
checkin
self-healing
kdocs
airscript
kingsoft-docs
skills
python
```

### 3. 可选 · Homepage

Settings → 左侧 **Website** → 填：
```
https://github.com/sprite1670/sprite1670#readme
```

---

## 或者：用脚本一次改完（需要 PAT）

如果你想要我全包，生成一个 PAT 即可：

1. 打开 https://github.com/settings/tokens/new
2. **Note** 填 `workbuddy-repo-setup`
3. **Expiration** 选 30 天
4. **Scopes** 勾选 `public_repo`
5. Generate token → 复制（只显示一次）
6. 把 token 发我，我跑：
   ```bash
   python3 scripts/set_repo_meta.py --token <PAT>
   ```
   脚本会自动设置 description + topics + homepage 并回读校验。

> PAT 等同于你的账号密码，**用完建议立刻去 Settings → Developer settings 撤销**。
> 脚本只写 stdout 不落盘。

---

## 改完的效果

仓库卡片会变成：

```
sprite1670 / sprite1670
WorkBuddy 云端签到自愈守护 —— 电脑关机也能按时签到，签到失败自动修复…

workbuddy  automation  checkin  self-healing  kdocs  airscript  …
MIT License          ★ 0  Fork 0
```

别人在 GitHub 搜 `workbuddy checkin`、`self-healing automation`、
`kdocs airscript` 都能搜到，直接拖 zip 就能用。
