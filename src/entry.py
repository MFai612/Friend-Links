from workers import Response, WorkerEntrypoint
from urllib.parse import urlparse
import json
from data import load_json_data

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)

        if url.path == '/':
            merged_data = load_json_data()
            return Response(
                json.dumps(merged_data, indent=2, ensure_ascii=False),
                headers={"Content-Type": "application/json; charset=utf-8"}
            )

        return Response('Not Found', status=404)