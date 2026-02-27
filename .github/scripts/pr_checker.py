#!/usr/bin/env python3
"""PR validation and auto-merge script for Friend-Links.

This script is invoked by the GitHub Actions workflow on `pull_request` and
`issue_comment` events. It implements the multi-stage validation described in
the project README: file-change check, structure validation, title update,
URL reachability, website ownership verification, and auto-merge.
"""

import os
import sys
import json
import time
import ast
import requests

GITHUB_API = "https://api.github.com"
# Prefer a user-provided PAT environment variable; fall back to GITHUB_TOKEN
TOKEN = os.environ.get("PAT") or os.environ.get("GITHUB_TOKEN")
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME")
EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH")
REPO = os.environ.get("GITHUB_REPOSITORY")

if not TOKEN or not EVENT_PATH or not REPO:
    print("Missing required environment variables (PAT or GITHUB_TOKEN / GITHUB_EVENT_PATH / GITHUB_REPOSITORY)")
    sys.exit(1)

HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}


def api(method, path, params=None, data=None, json_data=None):
    url = path if path.startswith("http") else f"{GITHUB_API}{path}"
    resp = requests.request(method, url, headers=HEADERS, params=params, data=data, json=json_data, timeout=20)
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    if resp.status_code >= 400:
        print(f"GitHub API error {resp.status_code} for {url}: {body}")
    return resp.status_code, body


def get_pr_from_event():
    with open(EVENT_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if EVENT_NAME == "pull_request":
        return payload.get("pull_request"), payload
    elif EVENT_NAME == "issue_comment":
        # comments can be on PRs (issues api) — ensure it's a PR
        issue = payload.get("issue")
        comment = payload.get("comment")
        if issue and issue.get("pull_request"):
            # fetch PR object
            pr_number = issue.get("number")
            status, pr = api("GET", f"/repos/{REPO}/pulls/{pr_number}")
            if status == 200:
                return pr, payload
    return None, payload


def list_pr_files(pr_number):
    files = []
    page = 1
    while True:
        status, body = api("GET", f"/repos/{REPO}/pulls/{pr_number}/files", params={"page": page, "per_page": 100})
        if status != 200:
            break
        if not body:
            break
        files.extend(body)
        if len(body) < 100:
            break
        page += 1
    return files


def add_labels(issue_number, labels):
    if not labels:
        return
    api("POST", f"/repos/{REPO}/issues/{issue_number}/labels", json_data={"labels": labels})


def remove_label(issue_number, label):
    api("DELETE", f"/repos/{REPO}/issues/{issue_number}/labels/{label}")


def get_issue_labels(issue_number):
    status, body = api("GET", f"/repos/{REPO}/issues/{issue_number}")
    if status == 200 and isinstance(body, dict):
        return [l["name"] for l in body.get("labels", [])]
    return []


def comment(issue_number, body):
    api("POST", f"/repos/{REPO}/issues/{issue_number}/comments", json_data={"body": body})


def update_pr_title(pr_number, title):
    api("PATCH", f"/repos/{REPO}/pulls/{pr_number}", json_data={"title": title})


def merge_pr(pr_number):
    status, body = api("PUT", f"/repos/{REPO}/pulls/{pr_number}/merge", json_data={"merge_method": "merge"})
    return status == 200


def download_raw(url):
    try:
        r = requests.get(url, headers={"Authorization": f"token {TOKEN}"}, timeout=15)
        return r.status_code, r.text
    except Exception as e:
        print("Download error:", e)
        return None, None


def parse_DATA_from_source(src):
    try:
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "DATA":
                        # get source segment for the value
                        try:
                            val_src = ast.get_source_segment(src, node.value)
                            data = ast.literal_eval(val_src)
                            if isinstance(data, dict):
                                return data
                        except Exception as e:
                            print("AST eval error:", e)
        return None
    except Exception as e:
        print("Parse error:", e)
        return None


def check_structure_and_extract(pr_number, files):
    valid_files = []
    failures = []
    data_objs = {}
    for f in files:
        filename = f.get("filename")
        if not filename.endswith(".py"):
            failures.append((filename, "not a .py file"))
            continue
        raw_url = f.get("raw_url")
        status, content = download_raw(raw_url)
        if status != 200 or content is None:
            failures.append((filename, "cannot download"))
            continue
        data = parse_DATA_from_source(content)
        if not data or not isinstance(data, dict):
            failures.append((filename, "no DATA dict found or unparsable"))
            continue
        # ensure required fields
        if not all(k in data for k in ("name", "description", "uri")):
            failures.append((filename, "missing required keys (name/description/uri)"))
            continue
        data_objs[filename] = data
        valid_files.append(filename)
    return valid_files, failures, data_objs


def urls_reachability_check(urls):
    ok = []
    bad = []
    for u in urls:
        u = u.strip()
        if not u:
            bad.append(u)
            continue
        try:
            r = requests.get(u, timeout=10, allow_redirects=True)
            if 200 <= r.status_code < 400:
                ok.append(u)
            else:
                bad.append(u)
        except Exception:
            bad.append(u)
    return ok, bad


def check_website_ownership(uri):
    try:
        r = requests.get(uri, timeout=10)
        if r.status_code >= 400:
            return False
        text = r.text
        if "https://waterspo.top" in text or "https://www.waterspo.top" in text:
            return True
        return False
    except Exception:
        return False


def ensure_label(issue_number, label):
    labels = get_issue_labels(issue_number)
    if label not in labels:
        add_labels(issue_number, [label])


def remove_labels_if_present(issue_number, labels_to_remove):
    labels = get_issue_labels(issue_number)
    for l in labels_to_remove:
        if l in labels:
            remove_label(issue_number, l)


def process_pull_request(pr):
    pr_number = pr.get("number")
    head = pr.get("head", {})
    print(f"Processing PR #{pr_number}")

    # 2. Check changed files under src/data/ (exclude __init__.py)
    files = list_pr_files(pr_number)
    data_files = [f for f in files if f.get("filename", "").startswith("src/data/") and os.path.basename(f.get("filename")) != "__init__.py"]
    if not data_files:
        print("No src/data/ changes found — terminating workflow")
        return

    ensure_label(pr_number, "友链申请中")

    # 3. File structure validation
    valid_files, failures, data_objs = check_structure_and_extract(pr_number, data_files)
    if failures:
        # add failure label and comment
        add_labels(pr_number, ["文件结构不一致"])
        comment(pr_number, "检测到文件结构不一致，请参考模板调整：\n\n```python\nDATA = {\n\n\"name\":\"Name\",\n\"description\":\"Desc\",\n\"uri\": \"https://github.com/MFJip612/Friend-Links\",\n\"avatar_uri\": \"https://github.com/favicon.ico\"\n\n}\n```\n\n修改完成后请在评论区回复：已修改")
        return
    else:
        add_labels(pr_number, ["文件结构符合"])
        remove_labels_if_present(pr_number, ["文件结构不一致"]) 

    # 4. Update PR title from DATA.name (use first file's name)
    # pick first data object
    first_name = None
    if data_objs:
        first_name = next(iter(data_objs.values())).get("name")
    if first_name:
        new_title = f"友链：{first_name}"
        update_pr_title(pr_number, new_title)

    # 5. URL reachability
    urls = []
    for d in data_objs.values():
        uri = d.get("uri")
        if uri:
            urls.append(uri)
        avatar = d.get("avatar_uri")
        if avatar:
            urls.append(avatar)

    ok, bad = urls_reachability_check(urls)
    if len(ok) == len(urls) and urls:
        add_labels(pr_number, ["URL全部可达"]) 
        remove_labels_if_present(pr_number, ["部分URL不可达", "URL全部不可达"]) 
    elif len(ok) == 0 and urls:
        add_labels(pr_number, ["URL全部不可达"]) 
        comment(pr_number, "检测到所有提供的 URL 均不可达，请检查并修改后在评论区回复：准备完毕")
    else:
        add_labels(pr_number, ["部分URL不可达"]) 
        comment(pr_number, "检测到部分 URL 不可达，请检查并修改后在评论区回复：准备完毕")

    # 6. Website ownership verification: prompt user to add link and reply
    ensure_label(pr_number, "验证网站所有权")
    comment(pr_number, "请在你的网站页面中添加指向下列任一链接以完成网站所有权验证：\n- https://waterspo.top\n- https://www.waterspo.top\n\n完成后在评论区回复：准备完毕")

    # 7. Attempt auto-merge if all pass
    labels = get_issue_labels(pr_number)
    reqs = {"文件结构符合", "URL全部可达", "所有权已验证"}
    if reqs.issubset(set(labels)):
        merged = merge_pr(pr_number)
        if merged:
            comment(pr_number, "所有验证通过，已自动合并。谢谢！")


def handle_issue_comment(pr, payload):
    pr_number = pr.get("number")
    comment_body = payload.get("comment", {}).get("body", "").strip()
    print(f"Handling comment on PR #{pr_number}: {comment_body}")
    if comment_body == "已修改":
        # re-run structure validation stage
        files = list_pr_files(pr_number)
        data_files = [f for f in files if f.get("filename", "").startswith("src/data/") and os.path.basename(f.get("filename")) != "__init__.py"]
        valid_files, failures, data_objs = check_structure_and_extract(pr_number, data_files)
        if failures:
            add_labels(pr_number, ["文件结构不一致"]) 
            comment(pr_number, "仍检测到文件结构问题，请根据模板修改后再次回复：已修改")
        else:
            add_labels(pr_number, ["文件结构符合"]) 
            remove_labels_if_present(pr_number, ["文件结构不一致"]) 
            # update title
            if data_objs:
                first_name = next(iter(data_objs.values())).get("name")
                if first_name:
                    update_pr_title(pr_number, f"友链：{first_name}")

    elif comment_body == "准备完毕":
        # determine whether to re-run URL check or ownership check based on labels present
        labels = get_issue_labels(pr_number)
        # priority: if '验证网站所有权' present -> run ownership
        if "验证网站所有权" in labels:
            # fetch DATA uri
            files = list_pr_files(pr_number)
            data_files = [f for f in files if f.get("filename", "").startswith("src/data/") and os.path.basename(f.get("filename")) != "__init__.py"]
            _, failures, data_objs = check_structure_and_extract(pr_number, data_files)
            if failures:
                comment(pr_number, "文件结构有问题，无法进行网站所有权验证，请先处理文件结构并回复：已修改")
                return
            # use first data obj
            uri = None
            if data_objs:
                uri = next(iter(data_objs.values())).get("uri")
            ok = False
            if uri:
                ok = check_website_ownership(uri)
            if ok:
                remove_label(pr_number, "验证网站所有权")
                add_labels(pr_number, ["所有权已验证"]) 
                comment(pr_number, "网站所有权验证通过。")
            else:
                comment(pr_number, "验证未通过：请确保页面包含指向 https://waterspo.top 或 https://www.waterspo.top 的链接，修改后再次回复：准备完毕")
            # after ownership pass, attempt merge
            labels = get_issue_labels(pr_number)
            reqs = {"文件结构符合", "URL全部可达", "所有权已验证"}
            if reqs.issubset(set(labels)):
                merged = merge_pr(pr_number)
                if merged:
                    comment(pr_number, "所有验证通过，已自动合并。谢谢！")
        else:
            # run URL checks
            files = list_pr_files(pr_number)
            data_files = [f for f in files if f.get("filename", "").startswith("src/data/") and os.path.basename(f.get("filename")) != "__init__.py"]
            _, failures, data_objs = check_structure_and_extract(pr_number, data_files)
            if failures:
                comment(pr_number, "文件结构有问题，无法进行 URL 验证，请先处理文件结构并回复：已修改")
                return
            urls = []
            for d in data_objs.values():
                uri = d.get("uri")
                if uri:
                    urls.append(uri)
                avatar = d.get("avatar_uri")
                if avatar:
                    urls.append(avatar)
            ok, bad = urls_reachability_check(urls)
            if len(ok) == len(urls) and urls:
                add_labels(pr_number, ["URL全部可达"]) 
                remove_labels_if_present(pr_number, ["部分URL不可达", "URL全部不可达"]) 
                comment(pr_number, "URL 验证通过。")
            elif len(ok) == 0 and urls:
                add_labels(pr_number, ["URL全部不可达"]) 
                comment(pr_number, "检测到所有提供的 URL 均不可达，请修正后再次回复：准备完毕")
            else:
                add_labels(pr_number, ["部分URL不可达"]) 
                comment(pr_number, "检测到部分 URL 不可达，请修正后再次回复：准备完毕")


def main():
    pr, payload = get_pr_from_event()
    if not pr:
        print("No PR found for this event — exiting")
        return
    if EVENT_NAME == "pull_request":
        process_pull_request(pr)
    elif EVENT_NAME == "issue_comment":
        handle_issue_comment(pr, payload)


if __name__ == "__main__":
    main()
