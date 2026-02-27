#!/usr/bin/env python3
"""
Validate the structure of a friend-link data file.

Usage: python validate_structure.py <file_path>

Exit codes:
  0 - Validation passed
  1 - Validation failed (error messages printed to stdout)
"""

import ast
import sys
import os


def validate_file(file_path: str) -> list[str]:
    """Validate DATA dict structure in the given Python file.

    Returns a list of error messages. Empty list means validation passed.
    """
    errors = []

    if not os.path.isfile(file_path):
        return [f"文件不存在: {file_path}"]

    if not file_path.endswith(".py"):
        return [f"文件 {file_path} 不是 Python (.py) 文件"]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return [f"无法读取文件 {file_path}: {e}"]

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        return [f"Python 语法错误: {e}"]

    data_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DATA":
                    data_node = node.value
                    break
        if data_node is not None:
            break

    if data_node is None:
        return ["缺少顶层变量 DATA（必须是一个字典）"]

    if not isinstance(data_node, ast.Dict):
        return ["DATA 变量必须是字典类型"]

    # Parse keys/values from the dict
    fields: dict[str, object] = {}
    for key_node, value_node in zip(data_node.keys, data_node.values):
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            if isinstance(value_node, ast.Constant):
                fields[key_node.value] = value_node.value
            else:
                fields[key_node.value] = None  # non-literal value, mark as present but unvalidatable

    # Check required fields
    required = ["name", "description", "uri"]
    for field in required:
        if field not in fields:
            errors.append(f"DATA 字典缺少必填字段: '{field}'")
        elif fields[field] is None:
            errors.append(f"DATA['{field}'] 的值不是字符串字面量，无法验证")
        elif not isinstance(fields[field], str):
            errors.append(f"DATA['{field}'] 必须是字符串类型，当前类型: {type(fields[field]).__name__}")
        elif not str(fields[field]).strip():
            errors.append(f"DATA['{field}'] 不能为空字符串")

    # Check optional avatar_uri field (if present, must be a non-empty string)
    if "avatar_uri" in fields:
        val = fields["avatar_uri"]
        if val is None:
            errors.append("DATA['avatar_uri'] 的值不是字符串字面量，无法验证")
        elif not isinstance(val, str):
            errors.append(f"DATA['avatar_uri'] 必须是字符串类型，当前类型: {type(val).__name__}")
        elif not str(val).strip():
            errors.append("DATA['avatar_uri'] 若存在则不能为空字符串")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_structure.py <file_path>", file=sys.stderr)
        sys.exit(2)

    file_path = sys.argv[1]
    errors = validate_file(file_path)

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        sys.exit(1)
    else:
        print(f"SUCCESS: {file_path} 文件结构验证通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
