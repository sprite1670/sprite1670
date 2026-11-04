"""上架前自检 —— 按 WorkBuddy 开放平台官方规范逐项体检。

用法:
    python3 check_import.py <skill 目录 或 zip 路径>

官方规范依据（open.workbuddy.cn/docs/skill）:
  · 目录结构   {skill-name}/ 下必须有 SKILL.md；
               子资源目录为 references/、scripts/、templates/
  · 目录层级   最多两层（根目录 / 二级文件夹 / 文件）
  · 压缩包     仅 .zip，大小不超过 3MB
  · frontmatter 必填 8 项：name、display_name、display_name_en、description、
               description_zh、description_en、version、author
  · name 必须是 hyphen-case（小写字母/数字/连字符，首尾不得为连字符）
  · description 不得出现尖括号
  · 不得硬编码真实凭据

退出码: 0 = 全部通过；1 = 存在问题。
"""
import os
import re
import sys
import zipfile

# ── 官方必填 frontmatter 字段 ──────────────────────────────────
REQUIRED_FIELDS = [
    "name",
    "display_name",
    "display_name_en",
    "description",
    "description_zh",
    "description_en",
    "version",
    "author",
]
# 选填字段（缺失不报错，存在则校验格式）
OPTIONAL_LIST_FIELDS = ["examples_zh", "examples_en"]

# 官方认可的子资源目录
KNOWN_SUBDIRS = {"references", "scripts", "templates"}

MAX_ZIP_BYTES = 3 * 1024 * 1024
MAX_DEPTH = 2  # 根目录 / 二级文件夹 / 文件

# 遍历时跳过的目录：VCS 元数据与编辑器缓存，不属于发布内容
SKIP_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules", ".idea", ".vscode"}


def walk_files(target):
    """遍历技能目录下的文件，跳过 VCS 元数据与缓存目录。"""
    for dp, dns, fns in os.walk(target):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith("__MACOSX")]
        for fn in fns:
            if fn == ".DS_Store":
                continue
            yield dp, fn


def walk_dirs(target):
    """遍历技能目录下的子目录（跳过 VCS 元数据与缓存目录）。"""
    for dp, dns, _ in os.walk(target):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith("__MACOSX")]
        rel = os.path.relpath(dp, target).replace("\\", "/")
        if rel != ".":
            yield rel

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.")
# 凭据字段里出现【非空随机值】才算泄漏。
# 值必须是纯字母数字（无空格/中文）、长度 >= 12、且同时含数字与字母——
# 这样既能抓住真实凭据，又不会把 "your AirScript-Token" 这类说明文字误判。
_SECRET_FIELD_RE = re.compile(
    r'"(?:token|file_id|script_id|api[_-]?key|secret|password|passwd)"\s*:\s*"([A-Za-z0-9]{12,})"',
    re.IGNORECASE,
)


def looks_random(v):
    """是否为随机串形态：纯字母数字 + 同时含数字和字母。"""
    return bool(re.search(r"\d", v)) and bool(re.search(r"[A-Za-z]", v))


def extract_if_zip(path):
    """zip -> 临时解压目录，返回技能根目录。"""
    import tempfile

    if not zipfile.isfile(path):
        return path, None
    if not zipfile.is_zipfile(path):
        return path, None
    tmp = tempfile.mkdtemp(prefix="skillcheck_")
    with zipfile.ZipFile(path) as z:
        z.extractall(tmp)
    entries = [e for e in os.listdir(tmp) if not e.startswith("__MACOSX")]
    if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
        return os.path.join(tmp, entries[0]), path
    return tmp, path


def parse_frontmatter(text):
    """解析 YAML frontmatter，返回 (dict, error)。仅支持官方字段所需的简单 YAML。"""
    if not text.startswith("---"):
        return None, "文件未以 '---' 开头，无 frontmatter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "frontmatter 未正常闭合（缺第二个 '---'）"
    block = parts[1]
    data = {}
    cur_list = None
    for raw in block.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", raw)
        if item and cur_list is not None:
            data[cur_list].append(item.group(1).strip().strip("\"'"))
            continue
        kv = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", raw)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if val == "":
            data[key] = []
            cur_list = key
        else:
            cur_list = None
            data[key] = val.strip("\"'")
    return data, None


def main():
    if len(sys.argv) < 2:
        print("用法: python3 check_import.py <skill 目录 或 zip>")
        return 2

    raw_target = os.path.abspath(sys.argv[1])
    target, zip_path = (raw_target, None) if os.path.isdir(raw_target) else extract_if_zip(raw_target)
    base = os.path.dirname(target)
    root = os.path.basename(target.rstrip("/\\"))

    print("==== 上架前自检（按官方规范）====")
    print("  目标 : %s" % target)
    ok = True

    # ── [1] 压缩包体积 ────────────────────────────────────────
    if zip_path:
        size = os.path.getsize(zip_path)
        good = size <= MAX_ZIP_BYTES
        ok = ok and good
        print("\n  [1] 压缩包大小 ≤ 3MB : %s  (%.2f MB)"
              % ("OK" if good else "FAIL", size / 1024 / 1024))
    else:
        print("\n  [1] 压缩包大小 : 跳过（检查的是目录）")

    # ── [2] 顶层 SKILL.md ────────────────────────────────────
    skill_md = os.path.join(target, "SKILL.md")
    has_skill = os.path.isfile(skill_md)
    ok = ok and has_skill
    print("\n  [2] 顶层含 SKILL.md : %s" % ("OK" if has_skill else "FAIL"))
    if not has_skill:
        print("\n==== 结论: 存在问题（缺 SKILL.md，无法解析）====")
        return 1

    text = open(skill_md, encoding="utf-8").read()
    fm, err = parse_frontmatter(text)
    if err:
        print("\n  [3] frontmatter 解析 : FAIL  %s" % err)
        print("\n==== 结论: 存在问题 ====")
        return 1

    # ── [3] 8 个必填字段 ─────────────────────────────────────
    print("\n  [3] frontmatter 必填字段（官方 8 项）")
    for key in REQUIRED_FIELDS:
        val = fm.get(key)
        good = bool(val) and (not isinstance(val, list) or len(val) > 0)
        ok = ok and good
        shown = str(val)[:52] if val else "(缺失)"
        print("      %s %-16s %s" % ("OK  " if good else "FAIL", key, shown))

    # ── [4] 选填列表字段 ─────────────────────────────────────
    print("\n  [4] 选填字段（示例）")
    for key in OPTIONAL_LIST_FIELDS:
        val = fm.get(key)
        if isinstance(val, list):
            print("      OK   %-12s %d 条" % (key, len(val)))
        else:
            print("      --   %-12s 未填（选填）" % key)

    # ── [5] name 规范 ────────────────────────────────────────
    name = fm.get("name") or ""
    hyphen_ok = bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name))
    ok = ok and hyphen_ok
    print("\n  [5] name 为 hyphen-case : %s  name=%r" % ("OK" if hyphen_ok else "FAIL", name))

    # ── [6] description 规范 ─────────────────────────────────
    desc = fm.get("description") or ""
    no_angle = "<" not in desc and ">" not in desc
    ok = ok and no_angle
    print("\n  [6] description 不含尖括号 : %s  (长度 %d)" % ("OK" if no_angle else "FAIL", len(desc)))
    fuzzy = [w for w in ["可能", "也许", "大概", "或许"] if w in desc]
    if fuzzy:
        print("      WARN 描述含模糊词: %s" % "、".join(fuzzy))

    # ── [7] 目录层级与子目录名 ───────────────────────────────
    print("\n  [7] 目录结构")
    bad_depth = []
    unknown_dirs = set()
    for rel in walk_dirs(target):
        depth = len(rel.split("/")) + 1
        if depth > MAX_DEPTH:
            bad_depth.append(rel)
        base_dir = rel.split("/")[0]
        if base_dir not in KNOWN_SUBDIRS:
            unknown_dirs.add(base_dir)
    good_depth = not bad_depth
    ok = ok and good_depth
    print("      %s 目录层级 ≤ %d 层" % ("OK  " if good_depth else "FAIL", MAX_DEPTH))
    for d in sorted(bad_depth):
        print("           超深: %s" % d)
    if unknown_dirs:
        print("      WARN 非官方子目录: %s（references/scripts/templates 之外）"
              % "、".join(sorted(unknown_dirs)))
    else:
        print("      OK   子目录均在 references/scripts/templates 内")

    # ── [8] SKILL.md 引用的 references 路径是否存在 ─────────
    print("\n  [8] SKILL.md 里 @references/ 引用路径存在性")
    refs = re.findall(r"@((?:references|templates|scripts)/[A-Za-z0-9_./-]+)", text)
    if not refs:
        print("      --   未使用 @路径 引用")
    for r in sorted(set(refs)):
        exists = os.path.exists(os.path.join(target, r))
        ok = ok and exists
        print("      %s %s" % ("OK  " if exists else "FAIL", r))

    # ── [9] 凭据泄漏 ─────────────────────────────────────────
    print("\n  [9] 无令牌 / 凭据 / 实例ID 泄漏")
    bad = []
    for dp, fn in walk_files(target):
        p = os.path.join(dp, fn)
        try:
            body = open(p, "rb").read().decode("utf-8", errors="ignore")
        except Exception:
            continue
        if JWT_RE.search(body):
            bad.append((os.path.relpath(p, base), "JWT"))
        for m in _SECRET_FIELD_RE.finditer(body):
            if looks_random(m.group(1)):
                bad.append((os.path.relpath(p, base), "凭据字段有值: " + m.group(0)[:40]))
                break
    if bad:
        for item, kind in bad:
            print("      FAIL %s -> %s" % (item, kind))
        ok = False
    else:
        print("      OK   无任何泄漏")

    # ── [10] 编码 ────────────────────────────────────────────
    print("\n  [10] 文件编码 UTF-8 无 BOM")
    enc_bad = []
    for dp, fn in walk_files(target):
        if fn.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".zip")):
            continue
        p = os.path.join(dp, fn)
        raw = open(p, "rb").read()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            enc_bad.append(os.path.relpath(p, base))
        if raw[:3] == b"\xef\xbb\xbf":
            enc_bad.append(os.path.relpath(p, base) + " (BOM)")
    ok = ok and not enc_bad
    print("      %s %s" % ("OK  " if not enc_bad else "FAIL",
                          "全部 UTF-8 无 BOM" if not enc_bad else "、".join(enc_bad)))

    total = sum(1 for _ in walk_files(target))
    print("\n  文件总数 : %d" % total)
    print("\n==== 结论: %s ====" % ("全部通过，可提交审核" if ok else "存在问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
