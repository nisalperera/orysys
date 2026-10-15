"""Loads .env into os.environ. Import this module before anything that reads environment variables.

pydantic-settings fills the Settings object from .env but does not export the values. LangSmith and LangChain read
os.environ, so LANGSMITH_* set only in .env would leave tracing off. Variables already set in the shell win over .env.
"""
from dotenv import load_dotenv

load_dotenv()
