#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 仓库元信息一键设置（description / topics / homepage）

为什么要设：
  - description 是仓库卡片、搜索结果、分享链接里最先被看到的一句话；
  - topics 是 GitHub 仓库搜索的主要索引维度 —— 不设就很难被人搜到。

前置：需要一个带 `repo` 权限的 Personal Access Token。
  获取：https://github.com/settings/tokens/new
    · Scopes 勾选 `public_repo`（公有仓库）或 `repo`
    · Generate token → 复制（只显示一次）

用法：
  python3 set_repo_meta.py --token <PAT>
  python3 set_repo_meta.py --token <PAT> --dry-run   # 只看要改什么
  python3 set_repo_meta.py --token <PAT> --repo-owner sprite1670 --repo-name sprite1670
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"

DESCRIPTION = (
    "WorkBuddy 云端签到自愈守护 —— 电脑关机也能按时签到，签到失败自动修复，全程无需人工干预。"
    "云端 AirScript 跑在金山文档云端引擎，令牌自动续期；失败自愈守护自动取新令牌并重签。"
)

HOMEPAGE = "https://github.com/sprite1670/sprite1670#readme"

TOPICS = [
    "workbuddy",
    "automation",
    "checkin",
    "self-healing",
    "kdocs",
    "airscript",
    "kingsoft-docs",
    "skills",
    "python",
    "claude-skills",
]


def api_call(method, path, token, body=None):
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "workbuddy-skill-setup",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.getcode(), (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}
    except Exception as e:
        return 0, {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True, help="GitHub PAT（不会写入磁盘）")
    ap.add_argument("--repo-owner", default="sprite1670")
    ap.add_argument("--repo-name", default="sprite1670")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    owner, name = args.repo_owner, args.repo_name
    repo_path = "/repos/%s/%s" % (owner, name)

    code, cur = api_call("GET", repo_path, args.token)
    if code != 200:
        print("[X] 读取仓库失败 (HTTP %s): %s" % (code, str(cur)[:200]))
        print("    检查 PAT 是否有效、是否勾选了 repo/public_repo 权限。")
        return 1

    print("════ 当前 ════")
    print("  description: %s" % (cur.get("description") or "(空)"))
    print("  homepage   : %s" % (cur.get("homepage") or "(空)"))
    print("  topics     : %s" % (cur.get("topics") or "(空)"))
    print("  license    : %s" % ((cur.get("license") or {}).get("spdx_id")))

    payload = {
        "description": DESCRIPTION,
        "homepage": HOMEPAGE,
        "topics": TOPICS,
    }
    print("\n════ 将要设置 ════")
    print("  description: %s" % DESCRIPTION)
    print("  homepage   : %s" % HOMEPAGE)
    print("  topics     : %s" % ", ".join(TOPICS))

    if args.dry_run:
        print("\n(dry-run，未实际修改)")
        return 0

    code, res = api_call("PATCH", repo_path, args.token, payload)
    if code not in (200, 201):
        print("\n[X] 设置失败 (HTTP %s): %s" % (code, str(res)[:300]))
        return 1

    # topics 需要单独的 PUT
    code2, res2 = api_call("PUT", repo_path + "/topics",
                            args.token, {"names": TOPICS})
    print("\n  主体信息: %s" % ("已更新" if code in (200, 201) else "失败 HTTP %s" % code))
    print("  topics   : %s" % ("已设置 %d 个" % len(TOPICS) if code2 == 200 else "失败 HTTP %s" % code2))

    code3, cur2 = api_call("GET", repo_path, args.token)
    if code3 == 200:
        print("\n════ 校验 ════")
        print("  description: %s" % (cur2.get("description") or "(空)"))
        print("  topics     : %s" % (", ".join(cur2.get("topics") or []) or "(空)"))
        print("  license    : %s" % ((cur2.get("license") or {}).get("spdx_id")))
    print("\n仓库地址: https://github.com/%s/%s" % (owner, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
