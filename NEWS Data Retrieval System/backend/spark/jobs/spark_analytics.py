"""
spark_analytics.py
------------------
Spark batch job: aggregate analytics over the full news corpus.

Strategy for Python 3.14 compatibility:
  SQLite → Pandas → CSV temp file → spark.read.csv → Spark SQL

By reading from disk (CSV) rather than using createDataFrame() with pickle,
we avoid all Python worker process issues.

Can be run standalone:
    cd backend
    python -m spark.jobs.spark_analytics
"""

import sys
import os
import json
import logging
import sqlite3
import tempfile
import csv
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from spark.spark_session import get_spark, stop_spark

logger = logging.getLogger(__name__)

_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "news.db")
)


def _sqlite_to_csv(csv_path: str) -> int:
    """Dump the articles table from SQLite directly to CSV."""
    con = sqlite3.connect(_DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT * FROM articles")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    con.close()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    return len(rows)


def run_analytics_job() -> dict[str, Any]:
    spark = get_spark()

    if not os.path.exists(_DB_PATH):
        return {"error": f"Database not found: {_DB_PATH}", "total_articles": 0}

    # Write SQLite → CSV temp file
    tmp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(tmp_dir, "articles.csv")
    row_count = _sqlite_to_csv(csv_path)

    if row_count == 0:
        return {
            "total_articles": 0,
            "categories": [],
            "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
            "top_sources": [],
            "daily_trend": [],
            "avg_content_length_by_category": [],
            "spark_mode": spark.sparkContext.master,
        }

    logger.info(f"Exported {row_count} rows to temp CSV: {csv_path}")

    # Read CSV natively into Spark (no pickle, no Python workers for schema inference)
    sdf = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "false")   # keep everything as strings
        .option("multiLine", "true")
        .option("escape", '"')
        .csv(csv_path)
    )
    sdf.createOrReplaceTempView("articles")
    logger.info("Spark temp view 'articles' ready. Running SQL aggregations...")

    def safe_sql(query: str, default):
        try:
            return spark.sql(query).collect()
        except Exception as e:
            logger.warning(f"SQL failed ({e}): {query[:80]}")
            return default

    # ── 1. Total count ──────────────────────────────────────────────────────
    r = safe_sql("SELECT COUNT(*) AS cnt FROM articles", [])
    total = r[0]["cnt"] if r else row_count

    # ── 2. Articles per category ────────────────────────────────────────────
    cats = safe_sql("""
        SELECT category, COUNT(*) AS count FROM articles
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY count DESC
    """, [])
    categories = [{"category": r["category"], "count": r["count"]} for r in cats if r["category"]]

    # ── 3. Sentiment distribution ───────────────────────────────────────────
    sents = safe_sql("""
        SELECT sentiment, COUNT(*) AS count FROM articles
        WHERE sentiment IS NOT NULL AND sentiment != ''
        GROUP BY sentiment
    """, [])
    sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    for r in sents:
        if r["sentiment"] in sentiment:
            sentiment[r["sentiment"]] = r["count"]

    # ── 4. Top sources ──────────────────────────────────────────────────────
    srcs = safe_sql("""
        SELECT source_name, COUNT(*) AS count FROM articles
        WHERE source_name IS NOT NULL AND source_name != ''
        GROUP BY source_name ORDER BY count DESC LIMIT 10
    """, [])
    top_sources = [{"source": r["source_name"], "count": r["count"]} for r in srcs if r["source_name"]]

    # ── 5. Daily trend ──────────────────────────────────────────────────────
    daily = safe_sql("""
        SELECT SUBSTR(created_at, 1, 10) AS date, COUNT(*) AS count FROM articles
        WHERE created_at IS NOT NULL AND created_at != ''
        GROUP BY SUBSTR(created_at, 1, 10)
        ORDER BY date ASC
        LIMIT 30
    """, [])
    daily_trend = [{"date": r["date"], "count": r["count"]} for r in daily if r["date"]]

    # ── 6. Average content length per category ──────────────────────────────
    avg_len = safe_sql("""
        SELECT category, ROUND(AVG(LENGTH(content)), 1) AS avg_length FROM articles
        WHERE content IS NOT NULL AND content != ''
          AND category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY avg_length DESC
    """, [])
    avg_content_length = [
        {"category": r["category"], "avg_length": r["avg_length"]}
        for r in avg_len if r["category"]
    ]

    # Cleanup temp file
    try:
        os.remove(csv_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    result = {
        "total_articles": total,
        "categories": categories,
        "sentiment_distribution": sentiment,
        "top_sources": top_sources,
        "daily_trend": daily_trend,
        "avg_content_length_by_category": avg_content_length,
        "spark_mode": spark.sparkContext.master,
    }

    logger.info(f"Analytics job complete: {total} articles processed via Spark SQL.")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run_analytics_job()
    print(json.dumps(result, indent=2, default=str))
    stop_spark()
