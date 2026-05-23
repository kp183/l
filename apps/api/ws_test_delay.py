import httpx
import time
import uuid
from datetime import datetime, timezone

trace_id = str(uuid.uuid4())
api_key = "al_live_Wo-gqQXlqyjCfFf-lWyYUkC5EAgTp1D8q7norI8rJuw"
headers = {"Authorization": f"Bearer {api_key}"}

print(f"Starting delayed trace ingestion test for trace ID: {trace_id}")

for i in range(5):
    span = {
        "id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "name": f"step_{i}",
        "span_type": "custom",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = httpx.post("http://localhost:8000/v1/ingest",
                      json={"spans": [span]}, headers=headers)
    print(f"Sent span {i}: status_code={resp.status_code}, response={resp.text}")
    time.sleep(1)
