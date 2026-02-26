from workers import WorkerEntrypoint, Response
import json
import os

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # 动态读取 src/data 目录下的所有 JSON 文件
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        merged_data = []
        seen_uris = set()

        for file_name in os.listdir(data_dir):
            if file_name.endswith(".json"):
                file_path = os.path.join(data_dir, file_name)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if item.get("uri") not in seen_uris:
                                    seen_uris.add(item["uri"])
                                    merged_data.append(item)
                        elif isinstance(data, dict):
                            if data.get("uri") not in seen_uris:
                                seen_uris.add(data["uri"])
                                merged_data.append(data)
                    except json.JSONDecodeError:
                        continue

        # 返回合并后的 JSON 数据
        return Response(json.dumps(merged_data, indent=2), content_type="application/json")