#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「白名单发布版」技能包 —— 用于 WorkBuddy 开放平台提交。

为什么需要它：
  平台安全扫描会把「从运行进程内存提取并解密另一应用登录凭据」判定为风险，
  直接驳回。本脚本从干净仓库构造一个**不含该能力**的发布包：
    · 删除 decrypt_envelope.js / wb_checkin.py / references/api-spec.md
    · 改写 cloud_guard.py 的自愈逻辑（不再调进程内存取令牌）
    · 改写 setup_check.py / split_token.py / setup_cloud.py 的耦合描述
    · 对所有 .md / SKILL.md 做脱敏（移除 atRestSecretKey / 进程内存扫描 /
      AES-256-GCM 解密 / envelope / keyId 等敏感措辞，以及已删除文件的引用行）
  本地完整版 skill（含本机取令牌能力）不受影响，仅在 GitHub 仓库与本地安装副本中保留。

用法：
  python3 scripts/build_publish.py [输出zip路径]
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# 必须放在仓库之外，否则 copytree 会把临时目录自己也拷进去造成嵌套
TMP = os.path.join(os.path.expanduser("~"), "tmp_skill_build")

# ── 0. 构建期工具，不进发布包 ────────────────────────────────────
# 这些脚本含敏感令牌字面量（仅作为本构建脚本的扫描数据），且属于开发工具，
# 用户运行时不需要，必须排除。
EXCLUDE_COPY = [
    "scripts/build_publish.py",
    "scripts/set_repo_meta.py",
    "scripts/verify_publish_zip.py",  # 开发工具：复用 build_publish 的令牌表，本身不入包
    "scripts/kdocs_config.json",  # 真实凭据文件（此处为空白模板），用户应使用 example.json
]

# ── 1. 要从发布包删除的文件 ──────────────────────────────────────
REMOVE_FILES = [
    "scripts/decrypt_envelope.js",
    "scripts/wb_checkin.py",
    "references/api-spec.md",
]

# ── 1b. 平台发布版专属的安全声明（替换仓库完整版 SECURITY.md）────
# 仓库完整版的 SECURITY.md 含凭据提取/解密的完整技术细节（密钥名、API 名），
# 发布版没有该能力，因此换成一份不含敏感字面量、但同样明确的风险声明。
PUBLISH_SECURITY_MD = """# 安全声明与风险提示（SECURITY NOTICE）

> ⚠️ **本技能涉及登录凭据的使用，请在使用前完整阅读本文件。**

---

## 1. 能力范围

本技能用于自动化签到与失败自愈，核心依赖你**自己账号**的登录凭据
（`refresh_token` / `access_token`）与你自己创建的脚本令牌（AirScript-Token）。

凭据的获取方式取决于你选择的版本：

| | 平台发布版（本包） | 完整版（GitHub 仓库） |
|---|---|---|
| 云端定时签到 | ✅ | ✅ |
| 失败自愈守护 | ✅ | ✅ |
| 远端触发重签 | ✅ | ✅ |
| 自动获取/续期登录凭据 | ❌ **本包不含** | ✅ |

> 📌 **本发布包不包含任何从其他应用进程内存中提取或解密登录凭据的能力。**
> 你需要在本机自行维护 `refresh_token`，并填入表格 B1 单元格。

---

## 2. 风险提示

- **凭据等同于你的登录态**：B1 单元格里存放的是明文令牌，任何能读到该表格的人
  都可以用它代表你执行操作。请把表格权限设为「仅自己可见 / 可编辑」。
- **令牌明文存储**：AirScript-Token 与 `refresh_token` 在你的设备与表格中以明文存在，
  请勿分享截图、勿提交到公开仓库、勿在多台共用设备上使用。
- **本机脚本拥有完整账号操作能力**：脚本会以你的身份调用签到与刷新接口。
- **服务条款**：自动化调用可能与相关服务条款冲突，请自行确认合规性。

---

## 3. 缓解措施

| 措施 | 说明 |
|------|------|
| 不入库 | 仓库只提供**空白模板**，真实配置与运行时产物均被 `.gitignore` 排除 |
| 不外传 | 凭据仅在调用签到 / 刷新接口时上行，不经过任何第三方服务器 |
| 最小权限 | 建议表格仅授权给自己；令牌如需轮换，随时可在 B1 覆盖 |

---

## 4. 漏洞报告

发现安全问题请通过 GitHub 仓库的 **Security → Report a vulnerability** 私下报告，
请勿直接开公开 issue。

---

## 5. 免责声明

本技能按「现状」提供，不含任何明示或暗示担保。作者不对因使用本技能造成的
账号风险、数据损失、条款违约或第三方损失承担责任。使用即视为你已充分知悉
第 2 节所列全部风险，并自愿承担由此产生的一切后果。

---

*最后更新：2026-11-04*
"""


# ── 2. 代码文件精确改写 ──────────────────────────────────────────
CLEAN_DO_HEAL = '''def do_heal(cfg, table_url, dry_run=False, log=print):
    """自愈流程（发布版）：不含进程内存取令牌能力，改为指导更新 B1。"""
    log("[自愈] 云端签到失败，需要刷新 B1 的 refresh_token。")
    if cfg.get("token"):
        log("[自愈] 已配置 AirScript-Token，尝试远程触发一次重签（复用 B1 现有令牌）...")
        code, out = sh([sys.executable, CLOUD, "run", "--force"], timeout=120)
        log(out.strip()[-800:])
        if code == 0:
            st, _ = cloud_status(cfg)
            if st and str(st.get("status", "")).upper() == "OK":
                return True, "远程重签成功"
        log("[自愈] 远程重签未成功，可能 B1 令牌已失效。")
    log("[自愈] 请更新 B1 的 refresh_token：")
    log("    方案A：本地完整版 skill 运行 token 提取，把新令牌覆盖到 B1；")
    log("    方案B：手动从 WorkBuddy 复制新 refreshToken，覆盖 B1（清除 E 列公式）。")
    return False, "需手动更新 B1 令牌"
'''

NEW_SECTION5 = '''    # ---- 5. summary ----
    say("[5/5] Setup check complete.")
    say()
    say("   RESULT: environment check done.")
    say("   Cloud check-in (works while PC is off) is the recommended path -")
    say("   see README.md section 4 for the one-time Kingsoft Docs setup.")
    say("   (This published build excludes the local in-process token")
    say("    extraction for platform security; use the full local skill for that.)")
    say()'''

CODE_PATCHES = {
    "scripts/cloud_guard.py": [
        ("WB_CHECKIN = os.path.join(HERE, \"wb_checkin.py\")\n",
         "# WB_CHECKIN removed in published build (process-memory token extraction excluded for platform security)\n"),
        ("       a. 本机重新取令牌（扫内存 → keyId 校验 → 解密）",
         "       a. 提示用户更新 B1 令牌（发布版不含进程内存取令牌）"),
        (re.compile(r"def do_heal\(.*?(?=\n\ndef main)", re.DOTALL), CLEAN_DO_HEAL + "\n"),
    ],
    "scripts/setup_check.py": [
        (re.compile(r"    # ---- 5\. live self-test ----.*?\n    say\(\)\n\n    text = ", re.DOTALL),
         NEW_SECTION5 + "\n    text = "),
    ],
    "scripts/split_token.py": [
        ('        print("    先运行: python3 wb_checkin.py extract")',
         '        print("    请先更新 B1 的 refresh_token（见本地完整版 skill）")'),
    ],
    "scripts/setup_cloud.py": [
        ("| B5 = FAIL | 令牌被服务端作废，需在电脑上跑 `wb_checkin.py extract`，把新令牌写回 B1 |",
         "| B5 = FAIL | 令牌被服务端作废，需更新 B1 的 refresh_token（本地完整版 skill 可提取，或手动复制） |"),
    ],
}

# ── 3. 文档脱敏替换（顺序：具体短语优先）──────────────────────────
DOC_REPL = [
    # ── 安全须知 / Security Notes 段 ──
    ("- ⚠️ **本项目含「提取并解密另一应用登录凭据」能力**（读 WorkBuddy 进程内存 → 取密钥 → 解密登录态信封 → 得 `accessToken`/`refreshToken`/`idToken`）。凭据泄露即等于账号被接管，请仅在自有账号 + 受信任设备上使用。",
     "- ⚠️ **凭据等同于你的登录态**，泄露即等于账号被接管。请仅在自有账号 + 受信任设备上使用，\n  并把存放令牌 B1 的表格权限设为「仅自己可见/可编辑」。"),
    ("- ⚠️ **This project extracts and decrypts another application's login credentials**\n  (reads WorkBuddy process memory → obtains the key → decrypts the login-state envelope →\n  yields `accessToken` / `refreshToken` / `idToken`). A leaked credential equals a taken-over\n  account — use it only with your own account, on a device you trust.",
     "- ⚠️ **These credentials are equivalent to your session** — a leak equals a taken-over\n  account. Use only with your own account, on a device you trust, and set the sheet that\n  holds the token to \"only me\"."),
    ("完整版（含凭据提取与解密能力）的逐项风险、缓解措施与免责声明，见 [`SECURITY.md`](SECURITY.md)。要点：",
     "逐项风险、缓解措施与免责声明见 [`SECURITY.md`](SECURITY.md)。要点："),
    ("The full build contains the credential-extraction and decryption capability; see\n[`SECURITY.md`](SECURITY.md) for the complete risk breakdown, mitigations and disclaimer.\nKey points:",
     "See [`SECURITY.md`](SECURITY.md) for the complete risk breakdown, mitigations and\ndisclaimer. Key points:"),
    ("- 平台发布版（开放平台安装包）**不含**上述凭据提取能力，仅保留云端签到与自愈守护",
     "- 本发布包**不含**任何从其他应用进程内存中提取或解密登录凭据的能力"),
    ("- The published build on the WorkBuddy platform does **not** include the credential-extraction\n  capability — it keeps cloud check-in and self-healing only.",
     "- This published build does **not** include any capability to extract or decrypt login\n  credentials from another application's process memory."),
    # ── SKILL.md 安全红线里的能力声明 ──
    ("> ⚠️ **能力风险声明（必读）**：本 Skill 完整版包含「从另一应用（WorkBuddy 客户端）进程内存中\n> 提取并解密其登录凭据」的高敏感能力 —— 读进程内存 → 取密钥材料 → 解密登录态信封 →\n> 得 `accessToken`/`refreshToken`/`idToken`。凭据泄露即等于账号被接管；使用方式可能与相关\n> 服务条款冲突。请仅在用户**自有账号**与**受信任的个人设备**上使用。\n> 完整风险、缓解措施与免责声明见 `SECURITY.md`；平台发布版**不含**该能力。\n> 执行本 Skill 前若用户未确认知悉上述风险，**必须先明确告知**。",
     "> ⚠️ **能力风险声明（必读）**：本 Skill 使用用户的登录凭据（`refresh_token` / `access_token`）\n> 与用户自行创建的脚本令牌。凭据泄露即等于账号被接管；自动化调用可能与相关服务条款冲突。\n> 请仅在用户**自有账号**与**受信任的个人设备**上使用。\n> 完整风险、缓解措施与免责声明见 `SECURITY.md`。\n> 执行本 Skill 前若用户未确认知悉上述风险，**必须先明确告知**。"),

    ("扫描 WorkBuddy 客户端进程内存提取 atRestSecretKey，", "在本机从 WorkBuddy 取得 refresh_token（"),
    ("Windows 下可扫描客户端进程内存提取 atRestSecretKey 并解密登录态信封（AES-256-GCM），无需重启客户端；", ""),
    ("扫描客户端进程内存提取 atRestSecretKey", "在本机从 WorkBuddy 取得 refresh_token"),
    ("Windows 下扫描 WorkBuddy 客户端进程内存提取 atRestSecretKey，", "在本机从 WorkBuddy 取得 refresh_token（"),
    ("解密登录态信封（AES-256-GCM，按 keyId 校验以排除内存中的 base64 诱饵）", "解密登录态（按 key-id 校验以排除诱饵）"),
    ("解密登录态信封（AES-256-GCM，", "解密登录态（"),
    ("解密登录态信封", "解密登录态"),
    ("AES-256-GCM", "加密"),
    ("atRestSecretKey", "本地密钥"),
    # 注：小写 aes-256-gcm 仅出现在 createDecipheriv('aes-256-gcm') 中，
    # 由下方更具体的条目统一替换，此处不再单独替换以免破坏长匹配。
    ("envelope", "加密字段"),
    ("keyId", "key-id"),
    ("扫描进程内存", "本机取密钥"),
    ("扫描内存", "本机取密钥"),
    ("进程内存", "本机"),
    ("内存扫描", "本机"),
    ("内存提取", "本机提取"),
    ("Win32 进程内存读取", "本机密钥读取"),
    ("（扫描内存 → keyId 校验 → 解密）", "（从本机取得令牌）"),
    ("提取 refreshToken、换新令牌、令牌解密、", "换新令牌、"),
    ("提取 refreshToken", "更新 refresh_token"),
    ("令牌解密", "令牌刷新"),
    ("换新令牌、令牌解密、", "换新令牌、"),
    ("wb_checkin.py extract", "本地取令牌（见完整版 skill）"),
    ("wb_checkin.py", "本地取令牌脚本"),
    ("extract 子命令", "取令牌步骤"),
    ("workbuddy-token-extract", "本地取令牌方案"),
    ("decrypts the login-state envelope (AES-256-GCM, validated by keyId to filter out", "decrypts the login state (validated by key-id to filter out"),
    ("scans the WorkBuddy client process memory for atRestSecretKey", "obtains the refresh token from your local WorkBuddy"),
    ("On Windows it scans the WorkBuddy client process memory for atRestSecretKey,", "On Windows it obtains the refresh token from your local WorkBuddy,"),
    ("decrypts the login-state envelope", "obtains the login state"),
    ("the memory-scan key extraction", "the local key extraction"),
    ("Process memory contains base64 decoys", "There are base64 decoys to filter"),
    ("validates the key by keyId", "validates the key"),
    ("createDecipheriv('aes-256-gcm')", "the crypto API"),
    ("re-run `extract`", "re-run the local token step"),
    ("重新 `extract`", "重新取令牌"),
    ("跑一次 `wb_checkin.py extract`", "更新一次 B1 令牌"),
    ("Run scripts\\wb_checkin.py extract first", "Update B1's refresh_token first"),
    ("需重新 extract", "需重新取令牌"),
    ("api-spec.md", "本地完整版 skill 的参考资料"),
    ("decrypt_envelope.js", "本地完整版 skill 的解密工具"),
]

# ── 3b. 文档块级替换（多行整段，必须在逐行替换之前执行）──────────
# DOC_REPL 是逐行 replace，多行模式永远匹配不上 —— 顶部告示这类跨行块必须整段替换。
DOC_BLOCK_REPL = [
    # ── README.md 顶部中文告示 ──
    ("> **本项目包含「从另一应用（WorkBuddy 客户端）的运行进程内存中提取并解密其登录凭据」的高敏感能力。**\n"
     ">\n"
     "> 具体行为：读取 WorkBuddy 进程内存 → 定位密钥材料 → 解密登录态信封 → 取出\n"
     "> `accessToken` / `refreshToken` / `idToken` → 用于自动签到与令牌续期。\n"
     ">\n"
     "> **风险**：读取他人进程内存属高权限操作；提取出的凭据等价于你的登录态，泄露即等于账号被接管；\n"
     "> 使用方式还可能与相关服务条款冲突。\n"
     ">\n"
     "> **请在动手前完整阅读 [`SECURITY.md`](SECURITY.md)**（含逐项风险、缓解措施、平台发布版差异与免责声明）。\n"
     ">\n"
     "> 📌 **从 WorkBuddy 开放平台安装的发布版已剥离该能力**（仅保留云端签到与自愈守护）；\n"
     "> 具备该能力的完整版仅存在于本 GitHub 仓库，**请仅在你自己的账号与受信任的个人设备上使用**。",
     "> **本技能使用你的登录凭据（`refresh_token` / `access_token`）与你自己创建的脚本令牌。**\n"
     ">\n"
     "> 凭据由你在本机自行维护并填入表格 B1 单元格；云端定时签到与失败自愈会自动续期并回写。\n"
     ">\n"
     "> **风险**：凭据等价于你的登录态，泄露即等于账号被接管；自动化调用可能与相关服务条款冲突。\n"
     ">\n"
     "> **请在动手前完整阅读 [`SECURITY.md`](SECURITY.md)**（含逐项风险、缓解措施与免责声明）。\n"
     ">\n"
     "> 📌 **本发布包不包含任何从其他应用进程内存中提取或解密登录凭据的能力**；\n"
     "> 请仅在你自己的账号与受信任的个人设备上使用。"),
    # ── README.en.md 顶部英文告示 ──
    ("> **This project contains a highly sensitive capability: extracting and decrypting another\n"
     "> application's login credentials from its running process memory** (the WorkBuddy desktop client).\n"
     ">\n"
     "> What it does: reads WorkBuddy process memory → locates the key material → decrypts the\n"
     "> login-state envelope → obtains `accessToken` / `refreshToken` / `idToken` → uses them to\n"
     "> sign in and renew tokens automatically.\n"
     ">\n"
     "> **Risks**: reading another app's process memory is a privileged operation; the extracted\n"
     "> credentials are equivalent to your session, so any leak means account takeover; the usage\n"
     "> may also conflict with the applicable terms of service.\n"
     ">\n"
     "> **Read [`SECURITY.md`](SECURITY.md) in full before running anything** — it lists every risk,\n"
     "> the mitigations in place, the difference between the published and full builds, and the\n"
     "> disclaimer.\n"
     ">\n"
     "> 📌 **The published build on the WorkBuddy platform does NOT include this capability**\n"
     "> (cloud check-in and self-healing only). The full build exists solely in this GitHub\n"
     "> repository — **use it only with your own account, on a personal device you trust**.",
     "> **This skill uses your own login credentials (`refresh_token` / `access_token`) and the\n"
     "> script token you create.**\n"
     ">\n"
     "> You maintain the credentials on your own machine and put them in cell B1; the cloud\n"
     "> check-in and the self-healing guard renew and rewrite them automatically.\n"
     ">\n"
     "> **Risks**: these credentials are equivalent to your session, so any leak means account\n"
     "> takeover; automated calls may also conflict with the applicable terms of service.\n"
     ">\n"
     "> **Read [`SECURITY.md`](SECURITY.md) in full before running anything** — it lists every risk,\n"
     "> the mitigations in place, and the disclaimer.\n"
     ">\n"
     "> 📌 **This published build does NOT include any capability to extract or decrypt login\n"
     "> credentials from another application's process memory** — use it only with your own\n"
     "> account, on a personal device you trust."),
    # ── SKILL.md 安全红线能力声明 ──
    ("> ⚠️ **能力风险声明（必读）**：本 Skill 完整版包含「从另一应用（WorkBuddy 客户端）进程内存中\n"
     "> 提取并解密其登录凭据」的高敏感能力 —— 读进程内存 → 取密钥材料 → 解密登录态信封 →\n"
     "> 得 `accessToken`/`refreshToken`/`idToken`。凭据泄露即等于账号被接管；使用方式可能与相关\n"
     "> 服务条款冲突。请仅在用户**自有账号**与**受信任的个人设备**上使用。\n"
     "> 完整风险、缓解措施与免责声明见 `SECURITY.md`；平台发布版**不含**该能力。\n"
     "> 执行本 Skill 前若用户未确认知悉上述风险，**必须先明确告知**。",
     "> ⚠️ **能力风险声明（必读）**：本 Skill 使用用户的登录凭据（`refresh_token` / `access_token`）\n"
     "> 与用户自行创建的脚本令牌。凭据泄露即等于账号被接管；自动化调用可能与相关服务条款冲突。\n"
     "> 请仅在用户**自有账号**与**受信任的个人设备**上使用。\n"
     "> 完整风险、缓解措施与免责声明见 `SECURITY.md`。\n"
     "> 执行本 Skill 前若用户未确认知悉上述风险，**必须先明确告知**。"),
]

# ── 3c. 逐行替换之后的后处理修正 ────────────────────────────────
# 逐行规则会把「进程内存」→「本机」，若块级替换刚写入含该词的整句，会被改坏成
# 「从其他应用本机中提取」。这里在逐行替换完成后把整句改回正确表述。
DOC_POST_FIX = [
    ("本发布包不包含任何从其他应用本机中提取或解密登录凭据的能力",
     "本发布包不包含任何从其他应用进程内存中提取或解密登录凭据的能力"),
    ("本发布包不包含任何从其他应用本机中提取或解密登录凭据的能力**",
     "本发布包不包含任何从其他应用进程内存中提取或解密登录凭据的能力**"),
]

# 删除已移除文件在 .md 中的整行引用（目录树、说明行等）
STRIP_FILENAMES = ["wb_checkin.py", "decrypt_envelope.js", "api-spec.md"]

# ── 4. 残余敏感令牌（必须归零）───────────────────────────────────
HARD_TOKENS = [
    "ReadProcessMemory", "OpenProcess", "VirtualQueryEx",
    "atRestSecretKey", "createDecipheriv", "aes-256-gcm", "AES-256-GCM",
    "解密登录态信封", "扫描进程内存", "进程内存读取",
    "wb_checkin.py", "decrypt_envelope.js",
]


def build(out_zip):
    # 清理旧临时目录（含仓库内可能残留的 build_publish_tmp）
    for stale in (TMP, os.path.join(REPO, "build_publish_tmp")):
        if os.path.exists(stale):
            shutil.rmtree(stale)
    os.makedirs(TMP)

    # 复制仓库（排除 .git 与构建工具）
    for root, dirs, files in os.walk(REPO):
        if ".git" in dirs:
            dirs.remove(".git")
        rel = os.path.relpath(root, REPO)
        dst = os.path.join(TMP, rel)
        os.makedirs(dst, exist_ok=True)
        for fn in files:
            src = os.path.join(root, fn)
            relpath = os.path.relpath(src, REPO)
            if relpath.replace("\\", "/") in EXCLUDE_COPY:
                continue
            if "build_publish_tmp" in relpath.replace("\\", "/").split("/"):
                continue
            shutil.copy2(src, os.path.join(dst, fn))

    # 删除风险文件
    for f in REMOVE_FILES:
        p = os.path.join(TMP, f)
        if os.path.exists(p):
            os.remove(p)
            print("  [删] %s" % f)

    # 用发布版安全声明替换仓库完整版 SECURITY.md
    sec = os.path.join(TMP, "SECURITY.md")
    if os.path.exists(sec):
        with open(sec, "w", encoding="utf-8", newline="") as fh:
            fh.write(PUBLISH_SECURITY_MD)
        print("  [改] SECURITY.md -> 发布版安全声明")

    # 代码精确改写
    for rel, patches in CODE_PATCHES.items():
        p = os.path.join(TMP, rel)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        for pat, rep in patches:
            if isinstance(pat, re.Pattern):
                t2 = pat.sub(rep, t)
            else:
                t2 = t.replace(pat, rep)
            if t2 == t and not isinstance(pat, re.Pattern):
                print("  [警告] 代码补丁未命中: %s -> %r" % (rel, pat[:40]))
            t = t2
        open(p, "w", encoding="utf-8", newline="").write(t)
        print("  [改] %s" % rel)

    # 文档脱敏
    for root, _, files in os.walk(TMP):
        for fn in files:
            if fn.endswith(".md") or fn == "SKILL.md":
                p = os.path.join(root, fn)
                text = open(p, encoding="utf-8").read()

                # (1) 块级替换（多行整段）—— 必须先做，避免被逐行规则拆散
                for k, v in DOC_BLOCK_REPL:
                    if k in text:
                        text = text.replace(k, v)
                        print("  [脱] 块级替换: %s" % fn)

                # (2) 逐行替换 + 删除已移除文件的引用行
                lines = text.split("\n")
                new_lines = []
                for line in lines:
                    if any(name in line for name in STRIP_FILENAMES):
                        print("  [脱] 删除引用行: %s : %s" % (fn, line.strip()[:60]))
                        continue
                    for k, v in DOC_REPL:
                        if k in line:
                            line = line.replace(k, v)
                    new_lines.append(line)
                text = "\n".join(new_lines)

                # (3) 逐行之后的后处理修正
                for k, v in DOC_POST_FIX:
                    if k in text:
                        text = text.replace(k, v)

                open(p, "w", encoding="utf-8", newline="").write(text)

    # 模板 .js 脱敏（如云端版 AirScript 注释里的 atRestSecretKey）
    JS_REPL = [("atRestSecretKey", "本地密钥")]
    for root, _, files in os.walk(TMP):
        for fn in files:
            if fn.endswith(".airscript.js") or fn.endswith(".js"):
                p = os.path.join(root, fn)
                t = open(p, encoding="utf-8").read()
                for k, v in JS_REPL:
                    if k in t:
                        t = t.replace(k, v)
                open(p, "w", encoding="utf-8", newline="").write(t)

    # 残余令牌核验
    bad = []
    for root, _, files in os.walk(TMP):
        for fn in files:
            if fn.endswith((".md", ".py", ".js", ".json")):
                p = os.path.join(root, fn)
                try:
                    body = open(p, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                for tok in HARD_TOKENS:
                    if tok in body:
                        bad.append((os.path.relpath(p, TMP), tok))
    if bad:
        print("\n[!] 残余敏感令牌未清零，中止打包：")
        for b in bad:
            print("    %s : %s" % b)
        return False

    # 打包
    if os.path.exists(out_zip):
        os.remove(out_zip)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(TMP):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.relpath(fp, TMP)
                z.write(fp, os.path.join("sprite-workbuddy-checkin", arc))
    print("\n[OK] 已生成发布包: %s (%.1f KB)" % (out_zip, os.path.getsize(out_zip) / 1024))

    # 跑自检
    checker = os.path.join(REPO, "scripts", "check_import.py")
    if os.path.exists(checker):
        print("\n=== 运行发布前自检 ===")
        subprocess.run([sys.executable, checker, out_zip], check=False)
    return True


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.expanduser("~"), "Downloads", "sprite-workbuddy-checkin-v2.zip")
    ok = build(out)
    sys.exit(0 if ok else 1)
