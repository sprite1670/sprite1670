#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 令牌解密 + 每日签到 一体化脚本（Windows 优先，零第三方依赖）

子命令：
  extract   扫描 WorkBuddy 进程内存取 atRestSecretKey -> 解密出 refreshToken/accessToken
  checkin   用本地 refreshToken 换 accessToken 并签到（顺带续期并回写令牌文件）
  auto      extract + checkin 全自动串联（最常用）

为什么需要本脚本：
  - WorkBuddy 5.6.2+ 登录态是 AES-256-GCM 加密信封，密钥只在运行中的客户端进程内存里；
  - 内存里常有多个同长 base64 误报，必须按文件信封的 keyId 校验才能锁定真密钥；
  - 本方案【不需要重启客户端】（不同于 CDP 调试端口方案），Agent 可自行执行。

用法：
  python3 wb_checkin.py extract
  python3 wb_checkin.py checkin
  python3 wb_checkin.py auto
  python3 wb_checkin.py auto --info <自定义 info 路径>
"""
import argparse
import base64
import ctypes
import ctypes.wintypes as wintypes
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://copilot.tencent.com"
REFRESH_URL = API + "/v2/plugin/auth/token/refresh"
CHECKIN_URL = API + "/v2/billing/meter/daily-checkin"
STATUS_URL = API + "/v2/billing/meter/checkin-activity-status"

DEFAULT_INFO = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info",
)

# 输出目录：与本脚本同级的 out/
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
STATE_FILE = os.path.join(OUT_DIR, "state.json")


def today_str():
    """本地日期（YYYY-MM-DD）。"""
    import datetime
    return datetime.date.today().isoformat()


def save_state(obj):
    """记录最近一次签到结果，供定时任务判断是否需要取新令牌。"""
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        obj = dict(obj)
        obj["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[!] 写状态文件失败: %s" % e)


def load_state():
    """读取最近一次签到结果；没有则返回 None。"""
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

B64_RE = re.compile(rb"^[A-Za-z0-9+/]{43,44}={0,2}$")


# ────────────────────────── 进程内存读取（Windows）──────────────────────────
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
MEM_COMMIT = 0x1000
READABLE_PROTECTS = (0x04, 0x02, 0x20, 0x40, 0x08, 0x80)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
VirtualQueryEx.restype = ctypes.c_size_t

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def decode_region(buf, idx, utf16):
    """从命中位置起解码字符串（ASCII 或 UTF-16LE）。"""
    try:
        if utf16:
            maxb = min(len(buf) - idx, 120)
            chars = []
            for i in range(0, maxb - 1, 2):
                b1 = buf[idx + i]
                b2 = buf[idx + i + 1]
                chars.append(chr(b1) if b1 != 0 else chr(b2))
            return "".join(chars)
        maxb = min(len(buf) - idx, 60)
        return buf[idx:idx + maxb].decode("latin1")
    except Exception:
        return ""


def scan_process(pid, needles, max_hits=20):
    """扫描单个进程内存，返回所有候选 base64 密钥字符串。"""
    h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        return []
    results = []
    addr = 0
    max_addr = 0x7FFFFFFF0000
    while addr < max_addr and len(results) < max_hits:
        mbi = MEMORY_BASIC_INFORMATION()
        if VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
            break
        size = mbi.RegionSize
        next_addr = (ctypes.c_void_p(addr).value or 0) + size
        if (mbi.State == MEM_COMMIT and 0 < size < 0x8000000
                and mbi.Protect in READABLE_PROTECTS):
            region = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t(0)
            if ReadProcessMemory(h, ctypes.c_void_p(addr), region, size,
                                 ctypes.byref(read)) and read.value > 0:
                data = bytes(region[:read.value])
                for pat, utf16 in needles:
                    plen = len(pat)
                    start = 0
                    while True:
                        i = data.find(pat, start)
                        if i < 0:
                            break
                        val = decode_region(data, i + plen, utf16)
                        q = val.find('"')
                        if q > 0:
                            cand = val[:q].split("\x00")[0]
                            if B64_RE.match(cand.encode("utf-8")):
                                results.append(cand)
                                if len(results) >= max_hits:
                                    break
                        start = i + 1
                        if len(results) >= max_hits:
                            break
                    if len(results) >= max_hits:
                        break
        addr = next_addr
        if size <= 0:
            addr += 0x1000
    CloseHandle(h)
    return results


def list_pids(names):
    """按进程名列出 PID（含 WorkBuddy / Electron / CodeBuddy）。"""
    pids = set()
    try:
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return []
    for line in out.splitlines():
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) < 2:
            continue
        img, low = parts[0], parts[0].lower()
        if any(low == n.lower() or (low.endswith(".exe") and n.lower() in low) for n in names):
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    return sorted(pids)


# ────────────────────────── 信封解密（AES-256-GCM）──────────────────────────
def derive_keyid(secret_b64):
    """key = sha256(secret 的 UTF-8 字节)；keyId = sha256(key).hex[:16]"""
    key = hashlib.sha256(secret_b64.encode("utf-8")).digest()
    return hashlib.sha256(key).hexdigest()[:16]


def expected_keyid(info_path):
    """从登录态文件任一加密信封里取 keyId。"""
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        auth = data.get("auth", {})
        for name in ("accessToken", "refreshToken", "idToken"):
            fld = auth.get(name)
            if isinstance(fld, dict) and fld.get("$wbEncrypted") == 1 and fld.get("envelope"):
                env = json.loads(base64.b64decode(fld["envelope"]).decode("utf-8"))
                if env.get("keyId"):
                    return env["keyId"]
    except Exception:
        pass
    return None


def find_node():
    """定位 Node.js：优先 PATH，其次 WorkBuddy 自带版本。"""
    import glob
    for exe in ("node", "node.exe"):
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return exe
        except Exception:
            pass
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".workbuddy", "binaries", "node", "versions", "*", "node.exe"),
        os.path.join(home, "AppData", "Roaming", "npm", "node.exe"),
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def do_extract(info_path, quiet=False):
    """扫描内存 -> 按 keyId 校验 -> 解密 -> 落盘。返回 (refreshToken, accessToken)。"""
    def say(*a):
        if not quiet:
            print(*a)

    if not os.path.exists(info_path):
        print("[X] 找不到登录态文件: %s" % info_path)
        print("    请确认 WorkBuddy 已登录并运行过。")
        return None, None

    needles = [
        (b'atRestSecretKey":"', False),
        (b'a\x00t\x00R\x00e\x00s\x00t\x00S\x00e\x00c\x00r\x00e\x00t\x00K\x00e\x00y\x00"\x00:\x00"\x00', True),
    ]
    names = ["WorkBuddy", "CodeBuddy", "Electron"]
    pids = list_pids(names)
    say("[*] 候选进程(%d): %s" % (len(pids), pids))
    if not pids:
        print("[X] 没找到 WorkBuddy 进程。请先打开 WorkBuddy 客户端。")
        return None, None

    found, seen = [], set()
    for pid in pids:
        try:
            for r in scan_process(pid, needles):
                if r not in seen:
                    seen.add(r)
                    found.append(r)
        except Exception:
            pass
        if len(found) >= 40:
            break

    if not found:
        print("[X] 未在进程内存中找到 atRestSecretKey。")
        print("    确认 WorkBuddy 已打开；权限不足时以管理员身份重试。")
        return None, None

    exp = expected_keyid(info_path)
    if exp:
        say("[*] 信封 keyId: %s（候选 %d 个，按 keyId 校验）" % (exp, len(found)))
        matched = [c for c in found if derive_keyid(c) == exp]
        if matched:
            found = matched
            say("[*] 校验通过，锁定 %d 个匹配候选" % len(matched))
        else:
            print("[!] 无候选的 keyId 与信封匹配，密钥可能已轮换；请重启 WorkBuddy 后重试。")
            return None, None
    else:
        print("[!] 无法从登录态读取 keyId，无法校验候选，拒绝使用。")
        return None, None

    secret = found[0]
    key_id = derive_keyid(secret)
    say("[*] 派生 keyId: %s" % key_id)

    # 解密交给 Node（crypto 原生 AES-256-GCM，比 ctypes 调 CNG 可靠得多）
    node = find_node()
    if not node:
        print("[X] 找不到 Node.js。请安装 Node 18+ 并加入 PATH。")
        return None, None

    os.makedirs(OUT_DIR, exist_ok=True)
    decrypt_js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "decrypt_envelope.js")
    try:
        proc = subprocess.run(
            [node, decrypt_js, "--info", info_path, "--key", secret, "--out", OUT_DIR],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        print("[X] 调用解密器失败: %s" % e)
        return None, None

    for line in (proc.stderr or "").splitlines():
        if line.strip():
            say(line.strip())

    rt_path = os.path.join(OUT_DIR, "refreshToken.txt")
    if proc.returncode != 0 or not os.path.exists(rt_path):
        print("[X] 解密未成功（退出码 %s）" % proc.returncode)
        return None, None

    tokens = {}
    for name in ("accessToken", "refreshToken", "idToken"):
        p = os.path.join(OUT_DIR, name + ".txt")
        if os.path.exists(p):
            val = open(p, encoding="utf-8").read().strip()
            if val:
                tokens[name] = val

    say("[*] 已保存到 %s" % OUT_DIR)
    return tokens.get("refreshToken"), tokens.get("accessToken")


# ────────────────────────── 签到流程 ──────────────────────────
def post_json(url, headers, body=b"{}"):
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.getcode(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, "ERR %s %s" % (type(e).__name__, str(e)[:150])


def read_rt():
    """读取本地 refreshToken（优先 out/ 下的最新，其次同目录 decrypted_check/）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [
        os.path.join(OUT_DIR, "refreshToken.txt"),
        os.path.join(here, "refreshToken.txt"),
        os.path.join(here, "decrypted_check", "refreshToken.txt"),
        os.path.join(here, "decrypted", "refreshToken.txt"),
    ]:
        if os.path.exists(p):
            val = open(p, encoding="utf-8").read().strip()
            if val:
                return val, p
    return None, None


def do_checkin(quiet=False):
    """刷新令牌 -> 签到 -> 连签状态；成功后把新令牌回写到本地文件。"""
    def say(*a):
        if not quiet:
            print(*a)

    rt, src = read_rt()
    if not rt:
        print("[X] 本地没有 refreshToken。先跑 extract 子命令。")
        save_state({"ok": False, "date": today_str(), "error": "本地无 refreshToken"})
        return 1

    say("[*] 使用令牌: %s（%d 字符）" % (src, len(rt)))

    code, body = post_json(REFRESH_URL, {
        "Content-Type": "application/json",
        "X-Refresh-Token": rt,
        "X-Auth-Refresh-Source": "plugin",
        "X-Domain": "copilot.tencent.com",
    })
    try:
        j = json.loads(body)
    except Exception:
        print("[X] 刷新返回非 JSON (HTTP %s): %s" % (code, body[:200]))
        save_state({"ok": False, "date": today_str(),
                    "error": "刷新返回非JSON", "http": code})
        return 1

    if j.get("code") != 0:
        msg = str(j.get("msg") or "")[:200]
        print("[X] 刷新失败: code=%s msg=%s" % (j.get("code"), msg))
        print("    常见原因 code=12153 invalid_grant: Session doesn't have required client")
        print("    -> 令牌不属于 plugin client，需重新 extract。")
        save_state({"ok": False, "date": today_str(),
                    "error": "刷新失败", "code": j.get("code"), "msg": msg})
        return 1

    data = j.get("data") or {}
    at = data.get("accessToken")
    new_rt = data.get("refreshToken")
    say("[+] 刷新成功 code=0，accessToken %d 字符" % len(at or ""))

    # 回写续期后的新令牌
    if new_rt and new_rt != rt:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, "refreshToken.txt"), "w", encoding="utf-8") as f:
            f.write(new_rt)
        say("[*] 新令牌已回写 %s" % os.path.join(OUT_DIR, "refreshToken.txt"))

    # 签到
    auth_headers = {"Content-Type": "application/json", "Authorization": "Bearer " + at}
    code, body = post_json(CHECKIN_URL, auth_headers)
    try:
        c = json.loads(body)
    except Exception:
        print("[!] 签到返回非 JSON (HTTP %s): %s" % (code, body[:200]))
        save_state({"ok": False, "date": today_str(),
                    "error": "签到返回非JSON", "http": code})
        return 1

    credit = None
    checkin_ok = False
    if c.get("code") == 0:
        credit = ((c.get("data") or {}).get("credit")) or 100
        checkin_ok = True
        print("[+] 签到成功 +%s 积分" % credit)
    elif c.get("code") == 10001:
        checkin_ok = True          # 今日已签 = 幂等成功
        print("[+] 今日已签（幂等跳过）")
    else:
        print("[!] 签到异常 code=%s %s" % (c.get("code"), str(c.get("msg"))[:120]))

    # 连签状态
    streak = {}
    try:
        code, body = post_json(STATUS_URL, auth_headers)
        s = json.loads(body)
        if s.get("code") == 0 and s.get("data"):
            d = s["data"]
            streak = {"streak_days": d.get("streak_days"),
                      "total_credits": d.get("total_credits"),
                      "today_checked_in": d.get("today_checked_in")}
            print("[*] 连签 %s 天 | 本期累计 %s 分 | 今日已签: %s"
                  % (d.get("streak_days"), d.get("total_credits"), d.get("today_checked_in")))
    except Exception:
        pass

    save_state({
        "ok": checkin_ok,
        "date": today_str(),
        "credit": credit,
        "code": c.get("code"),
        "msg": str(c.get("msg") or "")[:120],
        **streak
    })
    return 0 if checkin_ok else 1


def main():
    ap = argparse.ArgumentParser(description="WorkBuddy 令牌解密 + 每日签到")
    ap.add_argument("cmd", choices=["extract", "checkin", "auto"],
                    help="extract=只解密；checkin=只签到；auto=解密+签到")
    ap.add_argument("--info", default=DEFAULT_INFO, help="登录态文件路径")
    ap.add_argument("--quiet", action="store_true", help="减少输出")
    args = ap.parse_args()

    if os.name != "nt":
        print("[X] 本脚本的内存扫描依赖 Windows API，仅支持 Windows。")
        print("    macOS/Linux 请用 skill: workbuddy-token-extract（CDP 方案）。")
        return 2

    if args.cmd in ("extract", "auto"):
        rt, _ = do_extract(args.info, args.quiet)
        if not rt:
            return 1
        if args.cmd == "extract":
            print("\n完成。令牌已保存到 %s（勿外传）" % OUT_DIR)
            return 0

    if args.cmd in ("checkin", "auto"):
        return do_checkin(args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
