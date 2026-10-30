import os

import psycopg
import redis
import requests
from dotenv import load_dotenv

load_dotenv()  # reads the .env file


def check_postgres():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        print("Postgres OK | pgvector:", row[0] if row else "NOT ENABLED")


def check_redis():
    r = redis.from_url(os.environ["REDIS_URL"])
    print("Redis OK:", r.ping())


def check_gemini():
    model = os.environ["GEMINI_MODEL"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": "Say hello in one line"}]}]},
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    print("Gemini OK:", text)


if __name__ == "__main__":
    check_postgres()
    check_redis()
    check_gemini()
