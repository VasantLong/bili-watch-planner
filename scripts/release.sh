#!/usr/bin/env bash
# 发版脚本：只改版本号 + 跑测试 + 提交 + 推 main。
# tag 与 GitHub Release 由 .github/workflows/release.yml 在 main 上自动创建，
# 保证「代码里的 __version__」「tag」「Release」三者始终一致，不要手工 git tag。
#
# 用法: scripts/release.sh <x.y.z> [发布说明.md] [--no-push]
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=""
NOTES=""
PUSH=1
for arg in "$@"; do
  case "$arg" in
    --no-push) PUSH=0 ;;
    -*) echo "未知参数: $arg" >&2; exit 2 ;;
    *)
      if [ -z "$VERSION" ]; then VERSION="$arg"
      elif [ -z "$NOTES" ]; then NOTES="$arg"
      else echo "多余的参数: $arg" >&2; exit 2
      fi ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "用法: scripts/release.sh <x.y.z> [发布说明.md] [--no-push]" >&2
  exit 2
fi
case "$VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "版本号要写成 x.y.z：$VERSION" >&2; exit 2 ;;
esac

if [ -n "$(git status --porcelain)" ]; then
  echo "工作区不干净，先提交或清理再发版：" >&2
  git status --short >&2
  exit 1
fi

CURRENT=$(python3 -c 'import bili_planner; print(bili_planner.__version__)')
if [ "$CURRENT" = "$VERSION" ]; then
  echo "版本已经是 $VERSION，没有要发的" >&2
  exit 1
fi
if git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
  echo "tag v$VERSION 已存在，不能复用一个已发布的版本号" >&2
  exit 1
fi

python3 - "$VERSION" <<'PY'
import pathlib
import re
import sys

version = sys.argv[1]
path = pathlib.Path("bili_planner.py")
src = path.read_text(encoding="utf-8")
new, count = re.subn(r'__version__ = "[^"]+"', '__version__ = "%s"' % version, src, count=1)
if count != 1:
    sys.exit("bili_planner.py 里找不到 __version__，发版脚本需要它作为唯一版本来源")
path.write_text(new, encoding="utf-8")
print("__version__ %s -> %s" % (re.search(r'__version__ = "([^"]+)"', src).group(1), version))
PY

python3 -m unittest -q test_planner
python3 scripts/check_ui.py
python3 bili_planner.py --version

if [ -n "$NOTES" ]; then
  mkdir -p release-notes
  if [ ! -f "$NOTES" ]; then
    echo "发布说明文件不存在：$NOTES" >&2
    exit 1
  fi
  cp "$NOTES" "release-notes/v$VERSION.md"
  git add "release-notes/v$VERSION.md"
fi

git add bili_planner.py
git commit -q -m "chore(release): v$VERSION (版本号同步)"
echo "已提交 chore(release): v$VERSION"

if [ "$PUSH" -eq 1 ]; then
  git push origin HEAD:main
  echo "已推送 main；CI 将自动创建 tag v$VERSION 与 Release："
  echo "  https://github.com/VasantLong/bili-watch-planner/actions/workflows/release.yml"
else
  echo "未推送（--no-push）。推送 main 后 CI 会自动打 tag 并发 Release。"
fi
