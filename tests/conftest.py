"""Tests must never send traces to LangSmith (slow, flaky, pollutes the project). Set before any app import:
app.env uses load_dotenv, which does not override variables that already exist."""
import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
