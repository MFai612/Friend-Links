#!/usr/bin/env python3
"""
Extract a field value from the DATA dict in a friend-link data file.

Usage: python extract_field.py <file_path> <field_name>

Prints the field value to stdout.
Exit codes:
  0 - Field found and printed
  1 - Field not found or error
"""

import ast
import sys
import os


def extract_field(file_path: str, field_name: str) -> str | None:
    """Extract a string field from DATA dict. Returns the value or None."""
    if not os.path.isfile(file_path):
        print(f"文件不存在: {file_path}", file=sys.stderr)
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"无法读取文件: {e}", file=sys.stderr)
        return None

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        print(f"Python 语法错误: {e}", file=sys.stderr)
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DATA":
                    if isinstance(node.value, ast.Dict):
                        for key_node, value_node in zip(node.value.keys, node.value.values):
                            if (
                                isinstance(key_node, ast.Constant)
                                and key_node.value == field_name
                                and isinstance(value_node, ast.Constant)
                            ):
                                return str(value_node.value)
    return None


def main():
    if len(sys.argv) < 3:
        print("用法: python extract_field.py <file_path> <field_name>", file=sys.stderr)
        sys.exit(2)

    file_path = sys.argv[1]
    field_name = sys.argv[2]

    value = extract_field(file_path, field_name)
    if value is None:
        print(f"字段 '{field_name}' 不存在或无法提取", file=sys.stderr)
        sys.exit(1)

    print(value)
    sys.exit(0)


if __name__ == "__main__":
    main()
