#!/usr/bin/env python3
import base64
import hashlib
import os
import sys


def main() -> int:
    if len(sys.argv) != 2 or len(sys.argv[1]) < 12:
        print("Usage: python generate_password_hash.py 'MatKhauToiThieu12KyTu'", file=sys.stderr)
        return 2

    password = sys.argv[1].encode("utf-8")
    iterations = 210_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password, salt, iterations, dklen=32)
    print(
        "pbkdf2-sha256$"
        f"{iterations}$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(digest).decode()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
