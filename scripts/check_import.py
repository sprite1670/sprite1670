"""导入技能包体检 —— 检查是否符合 WorkBuddy「导入技能」的要求。

用法:
    python3 check_import.py <解压后的 skill 目录 或 zip 路径>
"""
import os
import re
import sys
import zipfile

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
    """zip -> 临时解压目录，返回目录。"""
    import tempfile
    if not zipfile.is_zipfile(path):
        return path
    tmp = tempfile.mkdtemp(prefix="skillcheck_")
    with zipfile.ZipFile(path) as z:
        z.extractall(tmp)
    entries = os.listdir(tmp)
    if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
        return os.path.join(tmp, entries[0])
    return tmp


def has_frontmatter(text):
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    fm = parts[1]
    return bool(re.search(r"^name:\s*\S", fm, re.M)) and \
        bool(re.search(r"^description:\s*\S", fm, re.M))


def main():
    if len(sys.argv) < 2:
        print("用法: python3 check_import.py <skill 目录或 zip>")
        return 2

    target = os.path.abspath(sys.argv[1])
    if os.path.isfile(target):
        target = extract_if_zip(target)
    base = os.path.dirname(target)
    root = os.path.basename(target)

    print("==== 导入技能 · 逐项体检 ====")
    print("  目标 : %s" % target)
    ok = True

    print("\n  [1] 每个 .md 有 YAML frontmatter (name + description)")
    mds = []
    for dp, _, fns in os.walk(target):
        for fn in fns:
            if fn.endswith(".md"):
                mds.append(os.path.join(dp, fn))
    for p in sorted(mds):
        text = open(p, encoding="utf-8").read()
        good = has_frontmatter(text)
        rel = os.path.relpath(p, base).replace("\\", "/")
        print("      %s %s" % ("OK  " if good else "FAIL", rel))
        ok = ok and good

    skill_md = os.path.join(target, "SKILL.md")
    has_skill = os.path.isfile(skill_md)
    print("\n  [2] 顶层含 SKILL.md : %s" % ("OK" if has_skill else "FAIL"))
    ok = ok and has_skill

    name = None
    if has_skill:
        text = open(skill_md, encoding="utf-8").read()
        m = re.search(r"^name:\s*(.+?)\s*$", text, re.M)
        if m:
            name = m.group(1).strip().strip("\"'")
    same = (name == root)
    print("\n  [3] name 与目录名一致 : %s  name=%r 目录=%r"
          % ("OK" if same else "FAIL", name, root))
    ok = ok and same

    print("\n  [4] 无令牌 / 凭据 / 实例ID 泄漏")
    bad = []
    for dp, _, fns in os.walk(target):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if JWT_RE.search(text):
                bad.append((os.path.relpath(p, base), "JWT"))
            for m in _SECRET_FIELD_RE.finditer(text):
                if looks_random(m.group(1)):
                    bad.append((os.path.relpath(p, base), "凭据字段有值: " + m.group(0)[:40]))
                    break
    if bad:
        for item, kind in bad:
            print("      FAIL %s -> %s" % (item, kind))
        ok = False
    else:
        print("      OK   无任何泄漏")

    total = sum(len(f) for _, _, f in os.walk(target))
    print("\n  [5] 总文件数 : %d" % total)
    print("\n==== 结论: %s ====" % ("全部通过，可直接导入" if ok else "存在问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
