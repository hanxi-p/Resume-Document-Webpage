import argparse
import base64
import getpass
import hashlib
from pathlib import Path
import secrets
import sqlite3

BACKEND_DIR = Path(__file__).resolve().parent
HASH_FILE = BACKEND_DIR / ".resume_access_hash"
LEGACY_FILE = BACKEND_DIR / ".resume_access_code"
SECURITY_DB_FILE = BACKEND_DIR / ".security_state.sqlite3"
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def set_password() -> None:
    password = getpass.getpass("新简历访问密码：").strip()
    confirmation = getpass.getpass("再次输入：").strip()
    if not password:
        raise SystemExit("密码不能为空")
    if password != confirmation:
        raise SystemExit("两次输入不一致")
    temp_path = HASH_FILE.with_suffix(".tmp")
    temp_path.write_text(hash_password(password), encoding="utf-8")
    temp_path.replace(HASH_FILE)
    if LEGACY_FILE.exists():
        LEGACY_FILE.unlink()
    print("密码哈希已更新；未保存明文密码。")


def unblock(ip: str | None, unblock_all: bool) -> None:
    if not SECURITY_DB_FILE.exists():
        print("封禁数据库尚未创建。")
        return
    with sqlite3.connect(SECURITY_DB_FILE, timeout=5) as connection:
        if unblock_all:
            cursor = connection.execute("DELETE FROM auth_failures")
        else:
            cursor = connection.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))
    print(f"已清除 {cursor.rowcount} 条记录。")


def main() -> None:
    parser = argparse.ArgumentParser(description="简历访问安全管理")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("set-password", help="交互式更新密码哈希")
    unblock_parser = subparsers.add_parser("unblock", help="解除IP封禁/失败计数")
    unblock_parser.add_argument("ip", nargs="?", help="要解除的IP")
    unblock_parser.add_argument("--all", action="store_true", help="清除全部记录")
    args = parser.parse_args()

    if args.command == "set-password":
        set_password()
    elif args.command == "unblock":
        if not args.all and not args.ip:
            parser.error("unblock 需要提供IP，或使用 --all")
        unblock(args.ip, args.all)


if __name__ == "__main__":
    main()
