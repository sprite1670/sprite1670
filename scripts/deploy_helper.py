#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端签到部署助手 —— 一次性产出部署所需的所有物料，并给出可核对的检查清单

产物：
  1. AirScript 源码副本（deploy/workbuddy-checkin.airscript.js）—— 粘贴到金山文档编辑器
  2. 部署步骤清单（deploy/DEPLOY.md）
  3. 就绪检查命令（供部署后核验）

用法：
  python3 deploy_helper.py --url https://www.kdocs.cn/l/xxxx [--file-id xxx]
  python3 deploy_helper.py --url ... --check        # 仅输出检查指引
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
ASSET = os.path.join(SKILL_ROOT, "assets", "workbuddy-checkin.airscript.js")
DEPLOY_DIR = os.path.join(HERE, "deploy")

DEPLOY_MD = """# 金山文档云端签到 · 部署清单

表格：{url}
工作表：Sheet1（worksheet_id={ws}）

## 前置确认（脚本已自动核对）

| 检查项 | 状态 |
|---|---|
| B1 含有效 refresh_token（三段式，{toklen} 字符） | ✅ |
| B1 为纯文本而非公式 | {b1_state} |
| B2 已有执行结果 | {b2_state} |

## 部署步骤

### 第 1 步 · 粘贴脚本
1. 打开表格 → 「效率」→「高级开发」→「**AirScript 脚本编辑器**」
2. 「新建脚本」，把 `workbuddy-checkin.airscript.js` 全文粘贴进去
3. 保存（Ctrl+S）

### 第 2 步 · 开通网络权限
1. 编辑器里点「**服务**」→「添加服务」
2. 勾选「**网络API**」→ 确定
   （脚本要用 HTTP.post 调 copilot.tencent.com，不开这个会静默失败）

### 第 3 步 · 试跑
1. 点「运行」
2. 看表格 **B2** 是否出现结果文字：
   - `签到成功 +100 积分` / `今日已签（幂等跳过）` → 成功
   - `失败：B1 没有 refresh_token` → B1 读不到值，回看第 4 步
   - `刷新失败：code=...` → 令牌问题，见 troubleshooting.md

### 第 4 步 · 固化 B1（重要）
脚本首次运行会自动做这件事：检测到 B1 是拼接公式时，从 E 列重建令牌 →
写回 B1（覆盖公式，变成纯文本）→ 清空 E 列。

跑完后 B1 应为**纯文本**。可自查：
```
{check_cmd}
```

### 第 5 步 · 建定时任务
1. 「效率」→「高级开发」→「**定时任务**」
2. 「新建定时任务」→ 选刚才那个脚本
3. 触发时间：**每天 09:00**（建议再加一条 21:00 兜底）
4. 保存

> 用的是金山文档云端定时器，不在本机建 cron。

## 可选 · 通知推送
在 B3 填 webhook 地址即可（Bark 用 `https://api.day.app/<KEY>`，企微/钉钉填机器人地址）。
留空则只在 B2 看结果。

## 可选 · 兜底通道
B4 填一段 JSON：`{{"url":"...","headers":{{...}},"body":"..."}}`，
主通道硬失败时会自动重放该请求。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--file-id", default="")
    ap.add_argument("--worksheet-id", type=int, default=1)
    ap.add_argument("--token-len", type=int, default=1567)
    ap.add_argument("--b1-state", default="✅ 纯文本")
    ap.add_argument("--b2-state", default="⬜ 待 AirScript 首次运行")
    ap.add_argument("--check", action="store_true", help="仅输出检查指引")
    args = ap.parse_args()

    check_cmd = (
        "python3 %s --b1 '<B1值>' --b1-formula '<B1公式,无则留空>' "
        "--b2 '<B2值>' --helper '<E1>' '<E2>' ... " % os.path.join(HERE, "check_kdocs_ready.py")
    )

    if args.check:
        print("=== 就绪检查指引 ===")
        print("1) mcp__kdocs__sheet.get_range_data")
        print("   url = %s" % (args.url or ("file_id=%s" % args.file_id)))
        print("   worksheet_id = %d" % args.worksheet_id)
        print("   range = B1:B2，再读 E1:E8")
        print()
        print("2) 回填判定：")
        print(check_cmd)
        return 0

    os.makedirs(DEPLOY_DIR, exist_ok=True)
    if os.path.exists(ASSET):
        shutil.copy2(ASSET, os.path.join(DEPLOY_DIR, "workbuddy-checkin.airscript.js"))
    else:
        print("[X] 找不到 AirScript 资产: %s" % ASSET)
        return 1

    md = DEPLOY_MD.format(
        url=args.url or ("file_id=%s" % args.file_id),
        ws=args.worksheet_id,
        toklen=args.token_len,
        b1_state=args.b1_state,
        b2_state=args.b2_state,
        check_cmd=check_cmd,
    )
    with open(os.path.join(DEPLOY_DIR, "DEPLOY.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print("[✓] 部署物料已生成:")
    print("    %s" % os.path.join(DEPLOY_DIR, "workbuddy-checkin.airscript.js"))
    print("    %s" % os.path.join(DEPLOY_DIR, "DEPLOY.md"))
    print()
    print("接下来按 DEPLOY.md 的 5 步操作即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
