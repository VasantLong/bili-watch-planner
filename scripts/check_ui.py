#!/usr/bin/env python3
"""从 static/index.html 抽出内联 <script>，做一次语法自检（需要 node）。

页面没有打包步骤，JS 全是手写在 HTML 里；改完前端最容易犯的错就是模板字符串里的
换行/转义把生成的 JS 弄坏。这个脚本用 node --check 兜住，CI 也跑。
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "static" / "index.html"
SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def extract(html_path=HTML):
    """返回页面里所有内联脚本，按出现顺序。"""
    text = pathlib.Path(html_path).read_text(encoding="utf-8")
    return [m.group(1) for m in SCRIPT_RE.finditer(text)]


def main():
    scripts = extract()
    if not scripts:
        sys.exit("static/index.html 里没找到内联 <script>")
    node = shutil.which("node")
    if not node:
        print("跳过：没装 node，无法做前端语法检查")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        for idx, body in enumerate(scripts):
            path = pathlib.Path(tmp) / ("inline-%d.js" % idx)
            path.write_text(body, encoding="utf-8")
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            if proc.returncode != 0:
                sys.stderr.write(proc.stderr or proc.stdout)
                sys.exit("内联脚本 #%d 语法检查失败" % idx)
    print("前端语法检查通过（%d 段内联脚本）" % len(scripts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
