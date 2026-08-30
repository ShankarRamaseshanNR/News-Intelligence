"""
spark_preprocessing.py
-----------------------
Spark batch job: corpus-wide text preprocessing.

Uses Spark SQL built-in string functions only (no Python UDFs):
  - REGEXP_REPLACE to strip HTML tags and URLs
  - LOWER for normalisation
  - SPLIT + EXPLODE for word tokenisation
  - Group-by word frequency for keyword ranking
  - LENGTH + arithmetic for chunk estimation

Fully compatible with Python 3.14 + PySpark 4.x (no Python worker processes).

Produces:
  - Normalised text stats per article
  - Top 50 most-frequent words across corpus
  - Chunk count estimates (how many RAG chunks each article produces)
  - Sample normalised output (5 articles)

Can be run standalone:
    cd backend
    python -m spark.jobs.spark_preprocessing
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

# English stop-words for keyword filtering (SQL IN list)
_STOP_WORDS_SQL = ", ".join([
    f"'{w}'" for w in [
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "has", "have", "had", "not", "but", "they", "their", "will", "been",
        "your", "more", "also", "into", "its", "than", "then", "been",
        "can", "which", "who", "what", "when", "where", "how", "all", "one",
        "said", "after", "about", "over", "would", "could", "should", "very",
    ]
])

# Chunk parameters (mirrors rag/vector_store._chunk_text)
_CHUNK_SIZE = 500
_OVERLAP = 50


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


def run_preprocessing_job() -> dict[str, Any]:
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

    # ── Step 1: Normalise text (HTML strip, URL remove, collapse whitespace) ─
    spark.sql("""
        SELECT *,
            TRIM(REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        CONCAT(
                            COALESCE(title, ''), ' ',
                            COALESCE(description, ''), ' ',
                            COALESCE(content, '')
                        ),
                        '<[^>]+>', ' '
                    ),
                    'https?://\\S+|www\\.\\S+', ''
                ),
                '\\s+', ' '
            )) AS normalised_text
        FROM articles
    """).createOrReplaceTempView("articles_normalised")

    total = spark.sql("SELECT COUNT(*) as cnt FROM articles_normalised").collect()[0]["cnt"]

    # ── Step 2: Chunk count estimate ────────────────────────────────────────
    # Estimate: ceil(max(0, len - overlap) / (chunk_size - overlap))
    chunk_stats_row = spark.sql(f"""
        SELECT
            ROUND(AVG(
                CASE
                    WHEN LENGTH(normalised_text) <= 100 THEN 1
                    ELSE CEIL(
                        (LENGTH(normalised_text) - {_OVERLAP}) / CAST({_CHUNK_SIZE - _OVERLAP} AS DOUBLE)
                    )
                END
            ), 2) AS avg_chunks,
            MAX(
                CASE
                    WHEN LENGTH(normalised_text) <= 100 THEN 1
                    ELSE CEIL(
                        (LENGTH(normalised_text) - {_OVERLAP}) / CAST({_CHUNK_SIZE - _OVERLAP} AS DOUBLE)
                    )
                END
            ) AS max_chunks,
            MIN(
                CASE
                    WHEN LENGTH(normalised_text) <= 100 THEN 1
                    ELSE CEIL(
                        (LENGTH(normalised_text) - {_OVERLAP}) / CAST({_CHUNK_SIZE - _OVERLAP} AS DOUBLE)
                    )
                END
            ) AS min_chunks,
            SUM(
                CASE
                    WHEN LENGTH(normalised_text) <= 100 THEN 1
                    ELSE CEIL(
                        (LENGTH(normalised_text) - {_OVERLAP}) / CAST({_CHUNK_SIZE - _OVERLAP} AS DOUBLE)
                    )
                END
            ) AS total_chunks
        FROM articles_normalised
    """).collect()[0]

    chunk_stats = {
        "avg_chunks_per_article": chunk_stats_row["avg_chunks"],
        "max_chunks": chunk_stats_row["max_chunks"],
        "min_chunks": chunk_stats_row["min_chunks"],
        "total_chunks": int(chunk_stats_row["total_chunks"] or 0),
    }

    # ── Step 3: Word frequency leaderboard ─────────────────────────────────
    top_keywords_rows = spark.sql(f"""
        SELECT word, COUNT(*) as freq
        FROM (
            SELECT EXPLODE(SPLIT(LOWER(normalised_text), '[^a-z]+')) AS word
            FROM articles_normalised
        ) words
        WHERE LENGTH(word) >= 4
          AND word NOT IN ({_STOP_WORDS_SQL})
        GROUP BY word
        ORDER BY freq DESC
        LIMIT 50
    """).collect()
    top_keywords = [{"word": r["word"], "freq": r["freq"]} for r in top_keywords_rows]

    # ── Step 4: Sample output ───────────────────────────────────────────────
    sample_rows = spark.sql("""
        SELECT article_id, title,
               SUBSTRING(normalised_text, 1, 300) AS normalised_preview,
               LENGTH(normalised_text) AS text_length
        FROM articles_normalised
        LIMIT 5
    """).collect()
    sample = [r.asDict() for r in sample_rows]

    # Cleanup temp file
    try:
        os.remove(csv_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    result = {
        "total_processed": total,
        "chunk_stats": chunk_stats,
        "top_keywords": top_keywords,
        "sample_output": sample,
        "spark_mode": spark.sparkContext.master,
    }

    logger.info(
        f"Preprocessing job complete: {total} articles, "
        f"{chunk_stats['total_chunks']} total estimated chunks."
    )
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run_preprocessing_job()
    print(json.dumps(result, indent=2, default=str))
    stop_spark()
