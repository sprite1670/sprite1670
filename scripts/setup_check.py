#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境体检 —— 一次跑完全部检查并输出报告。

被 install.bat 调用；也可单独运行：
    python3 setup_check.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = []


def say(s=""):
    OUT.append(s)


def rule(ch="=", n=60):
    say(ch * n)


def main():
    rule()
    say("   WorkBuddy Check-in Skill - Setup Check")
    rule()
    say()

    ok_all = True

    # ---- 1. Python ----
    say("[1/5] Checking Python ...")
    say("      OK  %s %s" % (os.path.basename(sys.executable),
                              sys.version.split()[0]))

    # ---- 2. Node ----
    say("[2/5] Checking Node.js ...")
    node = shutil.which("node")
    if not node:
        home = os.path.expanduser("~")
        base = os.path.join(home, ".workbuddy", "binaries", "node", "versions")
        if os.path.isdir(base):
            vers = sorted(os.listdir(base))
            for v in reversed(vers):
                cand = os.path.join(base, v, "node.exe")
                if os.path.exists(cand):
                    node = cand
                    break
    if node:
        try:
            ver = subprocess.run([node, "--version"], capture_output=True,
                                 text=True, timeout=15).stdout.strip()
        except Exception:
            ver = "?"
        say("      OK  %s" % (ver or node))
    else:
        say("      [X] Node.js not found.")
        say("          Install Node.js 18+ from https://nodejs.org/")
        say("          (WorkBuddy's bundled Node is auto-detected.)")
        ok_all = False

    # ---- 3. WorkBuddy client running ----
    say("[3/5] Checking WorkBuddy client is running ...")
    running = False
    try:
        out = subprocess.run(["tasklist", "/fi", "imagename eq WorkBuddy.exe", "/nh"],
                             capture_output=True, text=True, timeout=30).stdout
        running = "WorkBuddy.exe" in out
    except Exception:
        pass
    if running:
        say("      OK  WorkBuddy.exe is running.")
    else:
        say("      [!] WorkBuddy.exe not detected.")
        say("          The decryption key only lives in a RUNNING client.")
        say("          Launch WorkBuddy, then run this check again.")

    # ---- 4. cloud config ----
    say("[4/5] Checking cloud config ...")
    cfg_path = os.path.join(HERE, "kdocs_config.json")
    example_path = os.path.join(HERE, "kdocs_config.example.json")
    configured = False
    missing = []
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            missing = [k for k in ("file_id", "script_id", "token")
                       if not (cfg.get(k) or "").strip()]
            configured = not missing
        except Exception:
            missing = ["<unreadable>"]
    elif os.path.exists(example_path):
        missing = ["<config file missing: copy kdocs_config.example.json -> kdocs_config.json>"]
    else:
        missing = ["<config file missing>"]

    if configured:
        say("      OK  cloud credentials present.")
    else:
        say("      [!] Cloud not configured yet - optional for local check-in.")
        say("          Missing: %s" % ", ".join(missing))
        say("          To enable cloud check-in (works while your PC is off,")
        say("          auto self-healing): see README.md section 4.")
        say("          It needs a one-time manual setup in the")
        say("          Kingsoft Docs AirScript editor.")

    # ---- 5. live self-test ----
    say("[5/5] Running a live check-in self-test ...")
    say()
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "wb_checkin.py"), "checkin"],
                           capture_output=True, text=True, timeout=240, cwd=HERE)
        for ln in (r.stdout or "").splitlines():
            say("      " + ln)
        rc = r.returncode
    except Exception as e:
        say("      self-test failed to start: %s" % e)
        rc = 1

    say()
    rule()
    if rc == 0:
        say("   RESULT: local check-in works.")
        say("   You are ready to use the skill right now.")
        if not configured:
            say("   (Cloud mode is off - see README.md section 4 to enable it.)")
    else:
        ok_all = False
        say("   RESULT: self-test failed (exit code %s)." % rc)
        say("   Common causes:")
        say("     - WorkBuddy not running, or not logged in")
        say("     - Run scripts\\wb_checkin.py extract first")
        say("     - see references\\troubleshooting.md")
    rule()
    say()
    say("Tip: cloud check-in also works while your PC is powered off.")
    say("     See README.md section 4 for the one-time setup.")
    say()

    text = "\n".join(OUT)
    # 用 utf-8 写文件再由调用方 cat，避免 Windows 控制台 GBK 编码问题
    try:
        with open(os.path.join(HERE, ".setup_report.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("ascii", "replace").decode("ascii"))
        print()
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
