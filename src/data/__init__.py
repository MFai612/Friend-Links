import pkgutil
import importlib

def load_json_data():
    """
    动态发现并加载 src/data/ 下所有数据模块（link_*.py 等）。
    每个模块需包含一个 DATA 变量，值为 dict 或 list[dict]。
    添加新友链只需新建一个 .py 文件并定义 DATA 即可。
    """
    merged_data = []
    seen_uris = set()

    # pkgutil.iter_modules 会枚举当前包下所有子模块，Pyodide/Workers 均支持
    for _, modname, ispkg in sorted(pkgutil.iter_modules(__path__)):
        if ispkg:
            continue
        try:
            module = importlib.import_module(f'data.{modname}')
            data = getattr(module, 'DATA', None)
            if data is None:
                continue

            if isinstance(data, list):
                for item in data:
                    if item.get('uri') and item['uri'] not in seen_uris:
                        seen_uris.add(item['uri'])
                        merged_data.append(item)
            elif isinstance(data, dict):
                if data.get('uri') and data['uri'] not in seen_uris:
                    seen_uris.add(data['uri'])
                    merged_data.append(data)
        except Exception:
            continue

    return merged_data
