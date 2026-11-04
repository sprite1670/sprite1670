#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端签到部署向导 —— 生成一次性配置所需的全部物料与分步指引

用法：
  python3 setup_cloud.py --url https://www.kdocs.cn/l/你的表格ID
  python3 setup_cloud.py --url ... --file-id G_xxx --script-id xxx --token xxx   # 凭据已备齐时自检

产出：
  scripts/deploy/cloud/  ├── workbuddy-checkin-cloud.airscript.js  （粘贴到编辑器）
                       ├── DEPLOY.md                              （分步指引）
                       └── kdocs_config.json                     （凭据模板）
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSET = os.path.join(SKILL, "templates", "workbuddy-checkin-cloud.airscript.js")
OUT = os.path.join(HERE, "deploy", "cloud")

DEPLOY_MD = """# 云端签到部署（电脑关机也能签到）

表格：{url}
file_id：{file_id}

## 原理

```
┌─ 金山文档云端 ────────────────────────────┐
│  定时任务（每天 09:00）                    │
│      ↓                                    │
│  AirScript 脚本（云端引擎执行）             │
│      ↓ 读 B1 令牌                        │
│  POST copilot.tencent.com/v2/plugin/auth/token/refresh
│      ↓ 换新令牌 → 回写 B1（令牌自我续期）  │
│  POST copilot.tencent.com/v2/billing/meter/daily-checkin
│      ↓                                    │
│  写回 B2 结果 / B5 状态 / B6 成功日        │
└──────────────────────────────────────────┘
电脑关机、WorkBuddy 没开，都照样跑。
```

## 第 1 步 · 粘贴脚本（一次性）

1. 打开表格 →「效率」→「高级开发」→「**AirScript 脚本编辑器**」
2. 「新建脚本」，粘贴 `workbuddy-checkin-cloud.airscript.js` 全文
3. **保存（Ctrl+S）** —— ※ 必须保存到【**文档共享脚本**】里，建定时任务时要选它

## 第 2 步 · 开通网络权限（一次性）

1. 编辑器工具栏「**服务**」→「添加服务」
2. 勾选「**网络API**」→ 确定
   ※ 不加这个，脚本发不出请求，会静默失败（表现为 B2 一直空）

## 第 3 步 · 试跑（一次性）

点「运行」，确认：
- B2 出现结果文字（如 `11月3日 09:00 今日已签（幂等跳过） | 连签 19 天…`）
- B5 = `OK`
- B6 = 今天日期

## 第 4 步 · 建定时任务（一次性）

1.「效率」→「高级开发」→「**定时任务**」→ 新建任务
2. 触发：**每天** + **09:00**
3. 关联脚本：选刚才那个（文档共享脚本）
4. 保存 → 完事，此后自动运行

> 建议再加一条 21:00 的兜底任务。

## 第 5 步 · 开启远程触发能力（一次性，为自愈做准备）

需要让本机能在需要时**立刻**远程触发云端重签：

1. 编辑器工具栏「**脚本Token**」→ 勾选「我已了解」→「创建脚本Token」→ 复制
   （需完成实名认证；每个用户仅一个 token，默认 180 天，可手动延长）
2. 左侧脚本栏「**更多**」→「复制脚本 webhook」，形如：
   `https://www.kdocs.cn/api/v3/ide/file/<file_id>/script/<script_id>/sync_task`
3. 把 file_id / script_id / token 填入 `kdocs_config.json`：
```json
{{
  "file_id": "<webhook 里的 file_id>",
  "script_id": "<webhook 里的 script_id>",
  "token": "<脚本Token>",
  "table_url": "{url}"
}}
```

填好后自检：
```
python3 kdocs_cloud.py status
```
应输出云端当前状态（B2/B5/B6 的内容），而不是「缺少凭据」。

## 第 6 步 · 配置本机守护（可选，但推荐）

守护程序每天跑一次：查云端状态 → **成功就什么都不做** → 失败才取新令牌并更新部署。
```
python3 cloud_guard.py
```
可交给 WorkBuddy 的定时任务每日调用（见 SKILL.md「四、每日自愈调度」）。

## 日常维护

| 情况 | 处理 |
|---|---|
| B5 一直是 OK | 正常，无需干预。令牌由脚本自动续期 |
| B5 = FAIL | 令牌被服务端作废，需在电脑上跑 `wb_checkin.py extract`，把新令牌写回 B1 |
| B2 一直是空 | 多半是没开「网络API」服务，或定时任务没关联到脚本 |

## 安全提醒

- 令牌在 B1 是**明文**，务必把文档权限设为「仅自己可编辑/可见」；
- AirScript-Token 属个人隐私凭证，勿外传、勿提交到仓库；
- `kdocs_config.json` 含 token，别提交到 git。

## 已知边界

- AirScript 网络请求**只允许域名**（不能带端口/IP），超时上限 60 秒 —— 签到接口满足；
- 解密密钥绑在本机客户端，**令牌彻底作废时必须开电脑**重新取（云端无法自取）；
- AirScript 平台在高峰期可能丢任务，建议加一条 21:00 兜底。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--file-id", default="")
    ap.add_argument("--script-id", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)

    # AirScript 副本
    if os.path.exists(ASSET):
        shutil.copy2(ASSET, os.path.join(OUT, "workbuddy-checkin-cloud.airscript.js"))
    else:
        print("[X] 找不到 AirScript 资产: %s" % ASSET)
        return 1

    # 凭据模板（已填的保留原值）
    cfg_path = os.path.join(HERE, "kdocs_config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    for k, v in (("file_id", args.file_id), ("script_id", args.script_id),
                 ("token", args.token)):
        if v:
            cfg[k] = v
    if args.url:
        cfg["table_url"] = args.url
    cfg.setdefault("file_id", "")
    cfg.setdefault("script_id", "")
    cfg.setdefault("token", "")
    cfg.setdefault("table_url", args.url)
    with open(os.path.join(OUT, "kdocs_config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    md = DEPLOY_MD.format(
        url=args.url or cfg.get("table_url", ""),
        file_id=cfg.get("file_id") or "<待填>",
    )
    with open(os.path.join(OUT, "DEPLOY.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print("[✓] 部署物料已生成: %s" % OUT)
    for fn in sorted(os.listdir(OUT)):
        print("    %s" % fn)

    if args.self_test:
        have = [k for k in ("file_id", "script_id", "token") if cfg.get(k)]
        print()
        if len(have) == 3:
            print("[*] 凭据齐备，运行: python3 kdocs_cloud.py status")
        else:
            print("[!] 凭据未齐（缺 %s）" % ", ".join(
                k for k in ("file_id", "script_id", "token") if not cfg.get(k)))
            print("    按 DEPLOY.md 第 5 步获取后填入 kdocs_config.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
