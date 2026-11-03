#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金山文档云端签到部署状态检查（只读，零副作用）

检查表格是否具备"云端定时签到"条件：
  1. B1 是有效的 refresh_token（三段式 JWT）—— AirScript 读 B1 取令牌
  2. B1 不是公式（是纯文本）—— AirScript 的 .Text 才拿到值而非公式源串
  3. B2 已有执行结果 —— 说明 AirScript 跑过
  4. E 列分段区已清空 —— 说明自愈逻辑已生效

用法：
  python3 check_kdocs_ready.py --file-id <表格 file_id> [--worksheet-id 1]
  python3 check_kdocs_ready.py --url https://www.kdocs.cn/l/xxxx
  python3 check_kdocs_ready.py --file-id xxx --export-json      # 输出 JSON 供 Agent 解析

说明：
  读取需通过金山文档连接器的 MCP 工具，本脚本负责"算好要查什么 + 解析判定"；
  实际取值请用 mcp__kdocs__sheet.get_range_data（传 url/file_id + worksheet_id）。
"""
import argparse
import json
import re
import sys

# 令牌判定：必须是三段式 JWT
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-+/=]+\.[A-Za-z0-9_\-+/=]+\.[A-Za-z0-9_\-+/=]+$")


def is_token(text):
    """判断是否像一枚 refresh_token（三段、长度合理）。"""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) < 100 or len(t) > 5000:
        return False
    if not TOKEN_RE.match(t):
        return False
    return len(t.split(".")) == 3


def judge(b1_text, b1_formula, b2_text, helper_texts):
    """根据读到的单元格内容给出判定结论。"""
    checks = []

    # 1. B1 有有效令牌
    ok_token = is_token(b1_text)
    checks.append({
        "name": "B1 含有效 refresh_token",
        "ok": ok_token,
        "detail": ("长度 %d，三段结构合法" % len(b1_text.strip())) if ok_token
                  else ("读到的内容不是合法 JWT（长度 %d）" % len((b1_text or "").strip())),
    })

    # 2. B1 是纯文本而非公式
    is_formula = bool(b1_formula) and b1_formula.strip().startswith("=")
    checks.append({
        "name": "B1 为纯文本（非公式）",
        "ok": ok_token and not is_formula,
        "detail": ("B1 是公式：%s —— AirScript 的 .Text 会读到公式源串，"
                   "须让脚本跑一次触发自愈固化，或手动粘贴覆盖"
                   % b1_formula) if is_formula else "B1 是纯文本",
    })

    # 3. B2 有执行结果（AirScript 跑过）
    has_result = bool(b2_text and b2_text.strip())
    checks.append({
        "name": "B2 已有执行结果（AirScript 跑过）",
        "ok": has_result,
        "detail": (b2_text.strip()[:60]) if has_result else "B2 为空，AirScript 尚未成功运行",
    })

    # 4. E 列分段区已清空
    leftover = [t for t in helper_texts if t and t.strip()]
    checks.append({
        "name": "辅助列（E 列）已清空",
        "ok": not leftover,
        "detail": "已清空" if not leftover
                  else ("仍有 %d 个非空分段残留" % len(leftover)),
    })

    ready = all(c["ok"] for c in checks)
    return ready, checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file-id")
    ap.add_argument("--url")
    ap.add_argument("--worksheet-id", type=int, default=1)
    ap.add_argument("--b1", help="B1 的显示值")
    ap.add_argument("--b1-formula", default="", help="B1 的公式（fmlaText）")
    ap.add_argument("--b2", default="", help="B2 的显示值")
    ap.add_argument("--helper", nargs="*", default=[], help="辅助列各格的值")
    ap.add_argument("--export-json", action="store_true")
    args = ap.parse_args()

    # 允许只传读取结果做判定
    if args.b1 is not None:
        ready, checks = judge(args.b1, args.b1_formula, args.b2, args.helper)
        if args.export_json:
            print(json.dumps({"ready": ready, "checks": checks}, ensure_ascii=False, indent=2))
        else:
            print("云端签到部署状态：%s" % ("✅ 已就绪" if ready else "❌ 未就绪"))
            for c in checks:
                print("  [%s] %s" % ("OK" if c["ok"] else "!!", c["name"]))
                print("      %s" % c["detail"])
        return 0 if ready else 1

    # 否则输出"该查什么"的指引
    target = args.url or ("file_id=%s" % args.file_id)
    print("请用金山文档 MCP 工具读取以下区域后，把结果回填给本脚本判定：")
    print("  目标：%s  worksheet_id=%d" % (target, args.worksheet_id))
    print()
    print("  1) mcp__kdocs__sheet.get_range_data")
    print("     url/file_id = %s" % target)
    print("     worksheet_id = %d" % args.worksheet_id)
    print("     range = B1:B2  (取 cellText 与 fmlaText)")
    print("     另读 range = E1:E8 (确认分段区是否已清空)")
    print()
    print("  2) 回填判定：")
    print("     python3 check_kdocs_ready.py --b1 '<B1值>' --b1-formula '<公式>' \\")
    print("         --b2 '<B2值>' --helper '<E1>' '<E2>' ... --export-json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
