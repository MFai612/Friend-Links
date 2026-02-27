#!/usr/bin/env python3
"""
Check if a URL is reachable (returns 2xx status code).

Usage: python check_url.py <url>

Exit codes:
  0 - URL is reachable (2xx response)
  1 - URL is unreachable (non-2xx, timeout, or error)
"""

import sys
import requests


def check_url(url: str, timeout: int = 10, max_redirects: int = 10) -> tuple[bool, str]:
    """
    Check URL reachability.

    Returns (is_reachable, message).
    """
    try:
        session = requests.Session()
        session.max_redirects = max_redirects
        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; FriendLinkBot/1.0; "
                    "+https://github.com/MFJip612/Friend-Links)"
                )
            },
        )
        if 200 <= response.status_code < 300:
            return True, f"可达 (HTTP {response.status_code})"
        else:
            return False, f"不可达 (HTTP {response.status_code})"
    except requests.exceptions.TooManyRedirects:
        return False, f"重定向次数超过 {max_redirects} 次"
    except requests.exceptions.Timeout:
        return False, f"请求超时 ({timeout}s)"
    except requests.exceptions.ConnectionError as e:
        return False, f"连接失败: {e}"
    except Exception as e:
        return False, f"未知错误: {e}"


def main():
    if len(sys.argv) < 2:
        print("用法: python check_url.py <url>", file=sys.stderr)
        sys.exit(2)

    url = sys.argv[1]
    is_reachable, message = check_url(url)

    print(f"{url}: {message}")
    sys.exit(0 if is_reachable else 1)


if __name__ == "__main__":
    main()
