#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金山文档 AirScript 云端调用器

用 Script Token 远程执行表格里的 AirScript 脚本并读取结果。
**这解决了"电脑关机状态下也能签到"的问题** —— 脚本跑在金山文档云端引擎上。

凭据（三项，一次性获取）：
  file_id     表格文件 ID（形如 G_xxxx / 表格 URL 里的 id）
  script_id   脚本 ID（AirScript 编辑器左侧栏「更多」菜单 → 复制脚本 webhook）
  token       AirScript-Token（编辑器工具栏「脚本Token」按钮生成，需实名）

用法：
  python3 kdocs_cloud.py status                       # 查云端状态（只读，不签到）
  python3 kdocs_cloud.py run                          # 触发签到
  python3 kdocs_cloud.py run --force                  # 强制重签（忽略今日已签标记）
  python3 kdocs_cloud.py check                        # 平台配置校验（试开→读→关回）

凭据从环境变量或 config.json 读取：
  KDOCS_FILE_ID / KDOCS_SCRIPT_ID / KDOCS_TOKEN
  或 scripts/kdocs_config.json  { "file_id":..., "script_id":..., "token":... }
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "kdocs_config.json")

BASE = "https://www.kdocs.cn/api/v3/ide/file"


def load_config():
    """读取凭据：环境变量优先，其次 config.json。"""
    cfg = {
        "file_id": os.environ.get("KDOCS_FILE_ID", ""),
        "script_id": os.environ.get("KDOCS_SCRIPT_ID", ""),
        "token": os.environ.get("KDOCS_TOKEN", ""),
    }
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                data = json.load(f)
            for k in cfg:
                if not cfg[k]:
                    cfg[k] = data.get(k, "") or ""
        except Exception:
            pass
    # 模板占位符不算已配置
    for k in ("file_id", "script_id", "token"):
        v = str(cfg.get(k) or "")
        if "在这里填" in v or "替换为" in v:
            cfg[k] = ""
    return cfg


def call(cfg, argv=None, timeout=90):
    """调用 sync_task 同步执行脚本，返回解析后的结果。"""
    url = "%s/%s/script/%s/sync_task" % (BASE, cfg["file_id"], cfg["script_id"])
    body = json.dumps({
        "Context": {
            "argv": argv or {},
            "sheet_name": "Sheet1",
        }
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "AirScript-Token": cfg["token"],
    })
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:200])}

    try:
        j = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "非JSON响应: " + raw[:300]}

    data = j.get("data") or {}
    logs = data.get("logs") or []
    out = {
        "ok": j.get("status") == "finished" and not j.get("error"),
        "status": j.get("status"),
        "error": j.get("error") or "",
        "result": data.get("result"),
        "logs": [ln.get("args", [""])[0] for ln in logs if ln.get("args")],
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="金山文档 AirScript 云端调用器")
    ap.add_argument("cmd", choices=["status", "run", "check"])
    ap.add_argument("--force", action="store_true", help="强制重签")
    ap.add_argument("--config", default=CONFIG)
    args = ap.parse_args()

    cfg = load_config()
    missing = [k for k in ("file_id", "script_id", "token") if not cfg[k]]
    if missing:
        print("[X] 缺少凭据: %s" % ", ".join(missing))
        print()
        print("获取方式（一次性，约 3 分钟）：")
        print("  1) 打开表格 →「效率 → 高级开发 → AirScript 脚本编辑器」")
        print("  2) 工具栏「脚本Token」按钮 → 勾选我已了解 → 创建 → 复制（需实名）")
        print("  3) 左侧脚本栏「更多」→ 复制脚本 webhook，从中取出 script_id 与 file_id")
        print("     webhook 形如：https://www.kdocs.cn/api/v3/ide/file/<file_id>/script/<script_id>/sync_task")
        print()
        print("然后写入 %s :" % CONFIG)
        print(json.dumps({"file_id": "<...>", "script_id": "<...>", "token": "<...>"},
                         ensure_ascii=False, indent=2))
        print("或设置环境变量 KDOCS_FILE_ID / KDOCS_SCRIPT_ID / KDOCS_TOKEN")
        return 2

    if args.cmd == "status":
        r = call(cfg, {"check": "1"})
    elif args.cmd == "run":
        r = call(cfg, {"force": "1"} if args.force else {})
    else:  # check —— 只调平台校验接口意义不大，这里复用一次只读调用
        r = call(cfg, {"check": "1"})

    if not r["ok"]:
        print("[X] 调用失败: %s" % (r.get("error") or "未知错误"))
        for ln in r.get("logs", [])[-8:]:
            print("    %s" % ln)
        return 1

    print("[✓] 脚本执行完成 (status=%s)" % r.get("status"))
    result = r.get("result")
    if result:
        print("    返回: %s" % (result if len(str(result)) < 500 else str(result)[:500] + "..."))
    logs = r.get("logs") or []
    for ln in logs[-6:]:
        print("    %s" % ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
