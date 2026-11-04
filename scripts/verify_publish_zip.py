"""发布包独立核验工具（开发工具，不随发布包分发）。

从 build_publish.py 复用同一份敏感令牌表，避免两处定义不同步。
用法: python3 scripts/verify_publish_zip.py [zip路径]
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_publish import HARD_TOKENS  # noqa: E402

DEFAULT_ZIP = r'C:\Users\Administrator\Downloads\sprite-workbuddy-checkin-v2.zip'


def read(z, names, rel):
    for p in ('sprite-workbuddy-checkin/' + rel, rel):
        if p in names:
            return z.read(p).decode('utf-8', 'ignore')
    return ''


def main():
    zip_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ZIP
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()

    sk = read(z, names, 'SKILL.md')
    m = re.search(r'^version:\s*"?([^"\n]+)', sk, re.M)
    print('包内 version =', m.group(1).strip() if m else '未找到')
    n = re.search(r'^name:\s*(\S+)', sk, re.M)
    print('包内 name    =', n.group(1) if n else '未找到')

    hit = []
    for nm in names:
        if nm.endswith(('.md', '.py', '.js', '.json')):
            try:
                c = z.read(nm).decode('utf-8', 'ignore')
            except Exception:
                continue
            for x in HARD_TOKENS:
                if x in c:
                    hit.append((nm, x))
    print('敏感令牌命中:', hit if hit else '无 ✓')

    bad = [nm for nm in names
           if 'build_publish_tmp' in nm or 'scripts/out/' in nm
           or 'plan.json' in nm or nm.endswith('kdocs_config.json')
           or nm.endswith('build_publish.py') or nm.endswith('verify_publish_zip.py')]
    print('泄漏/嵌套文件:', bad if bad else '无 ✓')

    print('文件数:', len(names), '| 体积: %.1f KB' % (os.path.getsize(zip_path) / 1024))


if __name__ == '__main__':
    main()
