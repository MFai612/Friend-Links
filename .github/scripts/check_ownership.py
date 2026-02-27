#!/usr/bin/env python3
"""
Check if a website contains a link back to waterspo.top.

Usage: python check_ownership.py <uri>

The script fetches the HTML at <uri> and checks whether the source contains
either 'https://waterspo.top' or 'https://www.waterspo.top'.

Exit codes:
  0 - Ownership verification passed (link found)
  1 - Ownership verification failed (link not found or fetch error)
"""

import sys
import requests


# The URLs that must appear in the target website to prove ownership.
OWNERSHIP_URLS = [
    "https://waterspo.top",
    "https://www.waterspo.top",
]


def check_ownership(uri: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Fetch the website at `uri` and look for ownership links.

    Returns (passed, message).
    """
    try:
        response = requests.get(
            uri,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; FriendLinkBot/1.0; "
                    "+https://github.com/MFJip612/Friend-Links)"
                )
            },
        )
        html = response.text
    except requests.exceptions.Timeout:
        return False, f"请求超时 ({timeout}s)，无法获取页面内容"
    except requests.exceptions.ConnectionError as e:
        return False, f"连接失败: {e}"
    except Exception as e:
        return False, f"获取页面时出错: {e}"

    for ownership_url in OWNERSHIP_URLS:
        if ownership_url in html:
            return True, f"在页面源码中检测到链接: {ownership_url}"

    return False, (
        "未在页面 HTML 源码中检测到指向 "
        + " 或 ".join(OWNERSHIP_URLS)
        + " 的链接"
    )


def main():
    if len(sys.argv) < 2:
        print("用法: python check_ownership.py <uri>", file=sys.stderr)
        sys.exit(2)

    uri = sys.argv[1]
    passed, message = check_ownership(uri)

    print(message)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
