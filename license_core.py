# -*- coding: utf-8 -*-
"""SnapTool 离线授权核心（V53）。

设计要点：
1. 机器码取「主板序列号 + 系统盘序列号」规范化后做 SHA-256，格式化为
   XXXX-XXXX-XXXX-XXXX。只在本机计算，不联网、不上传。
2. 激活码绑定机器码：ST-PERM-<机器码短哈希>-<签名>，一机一码。
3. 邀请码不绑机器：ST-INV-<到期时间>-<签名>，任何机器可用，但必须在
   到期时间之前兑换；兑换成功后写入本机 license.dat，等同永久授权。
4. 授权状态存 %APPDATA%/SnapTool/license.dat（或 SNAPTOOL_HOME/license.dat），
   带 HMAC 签名，防手改。
5. 验签只用标准库 hmac/hashlib，不联网、不扣款、不依赖第三方包。

注意：离线方案的密钥必然随程序分发，只能防普通用户误改，不能防逆向。
需要强保护应改用非对称签名 + 服务端，那超出本离线工具的范畴。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 签发/验签共用密钥。签发工具 license_tool.py 必须保管好，不要随 exe 发出去。
_SECRET = b"SnapTool-Offline-License-V53-20261128-DoNotShare"

# 邀请码默认截止时间（用户指定：11/28/2026 晚上最晚时间）
INVITE_DEADLINE = "20261128235959"

CODE_PREFIX = "ST-"
LICENSE_VERSION = 1


# ---------------------------------------------------------------- 路径
def config_dir() -> Path:
    override = os.environ.get("SNAPTOOL_HOME")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "SnapTool"


def license_path() -> Path:
    return config_dir() / "license.dat"


# ---------------------------------------------------------------- 机器码
def _hardware_raw() -> str:
    """读取主板序列号 + 系统盘序列号；失败时逐项降级，不抛异常。"""
    parts: list[str] = []
    if sys.platform != "win32":
        return "NONWIN-MACHINE"
    ps = (
        "$b=(Get-CimInstance Win32_BaseBoard).SerialNumber; "
        "$d=(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).SerialNumber; "
        "Write-Output (\"B=\" + $b + \";D=\" + $d)"
    )
    try:
        startup = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        startup.wShowWindow = 0
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20, startupinfo=startup,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (cp.stdout or "").strip()
        if out:
            parts.append(out)
    except Exception:  # noqa: BLE001
        pass
    if not parts:
        # 兜底：机器名 + 用户名，保证同一台机器稳定
        parts.append("FALLBACK=" + os.environ.get("COMPUTERNAME", "")
                     + ":" + os.environ.get("USERNAME", ""))
    return "|".join(parts)


_MACHINE_DIGEST: str | None = None
_PRO_OVERRIDE: bool | None = None  # 仅自测注入用；None 表示按真实授权判断


def set_pro_override(value: bool | None) -> None:
    """测试专用：强制授权态；None 恢复真实判断。"""
    global _PRO_OVERRIDE
    _PRO_OVERRIDE = value


def machine_digest() -> str:
    """机器码的 16 位十六进制摘要（用于绑定与验签）。硬件只采集一次。"""
    global _MACHINE_DIGEST
    if _MACHINE_DIGEST is None:
        _MACHINE_DIGEST = hashlib.sha256(
            _hardware_raw().encode("utf-8")).hexdigest()[:16]
    return _MACHINE_DIGEST


def machine_code() -> str:
    """展示给用户的机器码：XXXX-XXXX-XXXX-XXXX。"""
    d = machine_digest()
    return "-".join(d[i:i + 4].upper() for i in range(0, 16, 4))


def normalize_machine_code(text: str) -> str:
    """把用户粘贴的机器码归一成 16 位小写十六进制；非法返回空串。"""
    s = re.sub(r"[^0-9a-fA-F]", "", text or "")
    return s.lower() if len(s) == 16 else ""


# ---------------------------------------------------------------- 签名
def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _verify(payload: str, sig: str) -> bool:
    return hmac.compare_digest(_sign(payload), (sig or "").lower())


# ---------------------------------------------------------------- 激活码
def make_activation_code(machine: str) -> str:
    """按机器码生成永久激活码（签发工具调用）。machine 为 16 位 hex 或带横杠展示码。"""
    d = normalize_machine_code(machine)
    if not d:
        return ""
    payload = f"PERM.{d}"
    return CODE_PREFIX + payload + "-" + _sign(payload)


def make_invite_code(deadline: str = INVITE_DEADLINE) -> str:
    """生成邀请码（签发工具调用）。deadline 格式 YYYYMMDDHHMMSS。"""
    if not re.fullmatch(r"\d{14}", deadline or ""):
        return ""
    payload = f"INV.{deadline}"
    return CODE_PREFIX + payload + "-" + _sign(payload)


def parse_code(code: str) -> tuple[str, dict]:
    """解析激活码 / 邀请码，返回 (类型, 数据)；失败返回 ("", {})。"""
    raw = (code or "").strip()
    if not raw.upper().startswith(CODE_PREFIX):
        return "", {}
    # payload 必须保留原始大小写：签名是基于小写机器码hex算的，
    # 若整串 upper 会让验签失败。只有前缀判断才用大写。
    body = raw[len(CODE_PREFIX):]
    # 最后一段是签名，前面是 payload
    if "-" not in body:
        return "", {}
    payload, sig = body.rsplit("-", 1)
    if not _verify(payload, sig):
        return "", {}
    fields = payload.split(".")
    if len(fields) == 2 and fields[0] == "PERM" and normalize_machine_code(fields[1]):
        return "PERM", {"machine": normalize_machine_code(fields[1])}
    if len(fields) == 2 and fields[0] == "INV" and re.fullmatch(r"\d{14}", fields[1]):
        return "INV", {"deadline": fields[1]}
    return "", {}


def _deadline_passed(deadline: str, now: datetime | None = None) -> bool:
    try:
        dt = datetime.strptime(deadline, "%Y%m%d%H%M%S")
    except Exception:  # noqa: BLE001
        return True
    return (now or datetime.now()) > dt


# ---------------------------------------------------------------- license.dat
def _license_text(record: dict) -> str:
    core = "|".join(str(record.get(k, "")) for k in ("v", "type", "machine", "time", "source"))
    data = dict(record)
    data["sig"] = _sign(core)
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def save_license(record: dict) -> bool:
    try:
        path = license_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".dat.tmp")
        tmp.write_text(_license_text(record), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def load_license() -> dict | None:
    try:
        data = json.loads(license_path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        core = "|".join(str(data.get(k, "")) for k in ("v", "type", "machine", "time", "source"))
        if not _verify(core, str(data.get("sig", ""))):
            return None
        if str(data.get("v")) != str(LICENSE_VERSION):
            return None
        return data
    except Exception:  # noqa: BLE001
        return None


def is_pro() -> bool:
    """当前是否拥有专业版授权（只认本机绑定 + 未篡改）。"""
    if _PRO_OVERRIDE is not None:
        return bool(_PRO_OVERRIDE)
    data = load_license()
    if not data or data.get("type") != "PERM":
        return False
    return str(data.get("machine")) == machine_digest()


def license_status() -> str:
    """给界面显示的一行状态。"""
    if is_pro():
        return "permanent"
    return "trial"


def activate(code: str) -> tuple[bool, str]:
    """输入激活码或邀请码；成功写入 license.dat 并返回 (成功, 说明键)。"""
    kind, data = parse_code(code)
    if kind == "PERM":
        if data["machine"] != machine_digest():
            return False, "machine_mismatch"
        ok = save_license({
            "v": LICENSE_VERSION, "type": "PERM",
            "machine": machine_digest(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "code",
        })
        return (True, "ok") if ok else (False, "save_failed")
    if kind == "INV":
        if _deadline_passed(data["deadline"]):
            return False, "invite_expired"
        ok = save_license({
            "v": LICENSE_VERSION, "type": "PERM",
            "machine": machine_digest(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "invite",
        })
        return (True, "ok") if ok else (False, "save_failed")
    return False, "invalid_code"


def import_license_file(path: str) -> tuple[bool, str]:
    """从外部 license.dat 导入（文件内容必须为本机有效授权）。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        core = "|".join(str(data.get(k, "")) for k in ("v", "type", "machine", "time", "source"))
        if not _verify(core, str(data.get("sig", ""))):
            return False, "invalid_code"
        if data.get("type") != "PERM" or str(data.get("machine")) != machine_digest():
            return False, "machine_mismatch"
        ok = save_license(data)
        return (True, "ok") if ok else (False, "save_failed")
    except Exception:  # noqa: BLE001
        return False, "invalid_code"


def export_license_file(path: str) -> bool:
    data = load_license()
    if not data:
        return False
    try:
        Path(path).write_text(_license_text(data), encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False
