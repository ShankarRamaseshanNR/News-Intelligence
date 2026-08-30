"""
spark_sentiment.py
------------------
Spark batch job: bulk sentiment re-analysis over the full article corpus.

Uses Spark SQL CASE/INSTR expressions (JVM-only, no Python UDFs).
Data is loaded via CSV temp-file to avoid pickle issues on Python 3.14.

Can be run standalone:
    cd backend
    python -m spark.jobs.spark_sentiment
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

_POSITIVE_WORDS = [
    "good", "great", "positive", "success", "win", "growth", "improve",
    "benefit", "breakthrough", "achievement", "hope", "optimistic", "gain",
    "rise", "boost", "progress", "celebrate", "innovation", "recovery",
]

_NEGATIVE_WORDS = [
    "bad", "crisis", "fail", "loss", "threat", "danger", "decline",
    "conflict", "war", "death", "disaster", "attack", "crash", "fear",
    "scandal", "corruption", "collapse", "violence", "recession", "fraud",
]


def _sqlite_to_csv(csv_path: str) -> int:
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


def _keyword_score_sql(words: list[str], text_expr: str) -> str:
    """Build SQL SUM of CASE WHEN INSTR(...) > 0 THEN 1 ELSE 0 END."""
    parts = [
        f"CASE WHEN INSTR(LOWER({text_expr}), '{w}') > 0 THEN 1 ELSE 0 END"
        for w in words
    ]
    return "(" + " + ".join(parts) + ")"


def run_sentiment_job() -> dict[str, Any]:
    spark = get_spark()

    if not os.path.exists(_DB_PATH):
        return {"error": f"Database not found: {_DB_PATH}"}

    tmp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(tmp_dir, "articles.csv")
    count = _sqlite_to_csv(csv_path)

    if count == 0:
        return {"total_processed": 0, "spark_mode": spark.sparkContext.master}

    sdf = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "false")
        .option("multiLine", "true")
        .option("escape", '"')
        .csv(csv_path)
    )
    sdf.createOrReplaceTempView("articles")

    # Build sentiment SQL using pure JVM INSTR operations
    text_expr = "CONCAT(COALESCE(title,''), ' ', COALESCE(description,''))"
    pos_sql = _keyword_score_sql(_POSITIVE_WORDS, text_expr)
    neg_sql = _keyword_score_sql(_NEGATIVE_WORDS, text_expr)

    recalc_sql = f"""
        SELECT *,
               CASE WHEN {pos_sql} > {neg_sql} THEN 'positive'
                    WHEN {neg_sql} > {pos_sql} THEN 'negative'
                    ELSE 'neutral'
               END AS recalculated_sentiment
        FROM articles
    """
    spark.sql(recalc_sql).createOrReplaceTempView("articles_with_recalc")

    total = spark.sql("SELECT COUNT(*) AS cnt FROM articles_with_recalc").collect()[0]["cnt"]

    dist_rows = spark.sql("""
        SELECT recalculated_sentiment, COUNT(*) AS count
        FROM articles_with_recalc
        GROUP BY recalculated_sentiment ORDER BY count DESC
    """).collect()
    distribution = {r["recalculated_sentiment"]: r["count"] for r in dist_rows}

    mismatch_count = spark.sql("""
        SELECT COUNT(*) AS cnt FROM articles_with_recalc
        WHERE sentiment IS NOT NULL AND sentiment != ''
          AND sentiment != recalculated_sentiment
    """).collect()[0]["cnt"]

    sample_rows = spark.sql("""
        SELECT article_id, title, sentiment, recalculated_sentiment
        FROM articles_with_recalc
        WHERE sentiment IS NOT NULL AND sentiment != ''
          AND sentiment != recalculated_sentiment
        LIMIT 10
    """).collect()
    mismatch_sample = [r.asDict() for r in sample_rows]

    cat_rows = spark.sql("""
        SELECT category, recalculated_sentiment, COUNT(*) AS count
        FROM articles_with_recalc
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category, recalculated_sentiment
        ORDER BY category, count DESC
    """).collect()
    category_sentiment: dict[str, dict] = {}
    for r in cat_rows:
        category_sentiment.setdefault(r["category"], {})[r["recalculated_sentiment"]] = r["count"]

    try:
        os.remove(csv_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    result = {
        "total_processed": total,
        "sentiment_distribution": distribution,
        "mismatch_count": mismatch_count,
        "mismatch_rate_pct": round((mismatch_count / total) * 100, 2) if total else 0,
        "mismatch_sample": mismatch_sample,
        "category_sentiment_breakdown": category_sentiment,
        "spark_mode": spark.sparkContext.master,
    }

    logger.info(f"Sentiment job complete: {total} articles, {mismatch_count} mismatches.")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run_sentiment_job()
    print(json.dumps(result, indent=2, default=str))
    stop_spark()
