# -*- coding: utf-8 -*-
"""SnapTool 离线授权签发工具（V53）。

这个脚本不要打包进 exe、不要发给用户，由签发方离线保管。

用法：
  python license_tool.py machine
      显示本机机器码（让用户发给你）。

  python license_tool.py activate XXXX-XXXX-XXXX-XXXX
      按用户的机器码生成永久激活码，发回给用户。

  python license_tool.py invite
      生成邀请码，有效期截止 2026-11-28 23:59:59（INVITE_DEADLINE）。

  python license_tool.py verify ST-....
      校验一串码是否有效（含签名、到期检查）。
"""
from __future__ import annotations

import sys

from license_core import (
    INVITE_DEADLINE,
    _deadline_passed,
    activate,
    machine_code,
    make_activation_code,
    make_invite_code,
    parse_code,
)


def _usage() -> None:
    print(__doc__)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in ("-h", "--help"):
        _usage()
        return 0

    cmd = args[0].lower()
    if cmd == "machine":
        print("本机机器码: " + machine_code())
        return 0

    if cmd == "activate":
        if len(args) < 2:
            print("用法: license_tool.py activate XXXX-XXXX-XXXX-XXXX")
            return 2
        code = make_activation_code(args[1])
        if not code:
            print("机器码格式不对，应为 16 位十六进制（可带横杠）。")
            return 2
        print("激活码: " + code)
        return 0

    if cmd == "invite":
        deadline = args[1] if len(args) > 1 else INVITE_DEADLINE
        code = make_invite_code(deadline)
        if not code:
            print("截止时间格式不对，应为 YYYYMMDDHHMMSS。")
            return 2
        print("邀请码: " + code)
        print(f"有效期至: {deadline[:4]}-{deadline[4:6]}-{deadline[6:8]} "
              f"{deadline[8:10]}:{deadline[10:12]}:{deadline[12:14]}")
        return 0

    if cmd == "verify":
        if len(args) < 2:
            print("用法: license_tool.py verify ST-....")
            return 2
        kind, data = parse_code(args[1])
        if not kind:
            print("无效：签名不对或格式错误。")
            return 1
        if kind == "PERM":
            print(f"有效永久激活码，绑定机器 {data['machine']}。")
        else:
            expired = _deadline_passed(data["deadline"])
            print(f"邀请码，截止 {data['deadline']}，"
                  + ("已过期。" if expired else "未过期。"))
        return 0

    print("未知命令: " + cmd)
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
