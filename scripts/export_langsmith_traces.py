import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

project = os.environ["LANGSMITH_PROJECT"]
client = Client()

output = Path("output/langsmith_runs.jsonl")
output.parent.mkdir(parents=True, exist_ok=True)

count = 0

with output.open("w", encoding="utf-8") as file:
    for run in client.list_runs(project_name=project):
        file.write(json.dumps(run.dict(), default=str) + "\n")
        count += 1

print(f"Exported {count} runs to {output}")