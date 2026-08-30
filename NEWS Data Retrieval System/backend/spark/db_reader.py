"""
db_reader.py
------------
Bridge utilities: SQLite → CSV temp file → Spark DataFrame.

Python 3.14 + PySpark 4.x incompatibility note:
    spark.createDataFrame(pandas_df) uses pickle between the JVM and Python,
    which is broken on Python 3.14/Windows (WinError 10038).
    We work around this by dumping SQLite → CSV then using spark.read.csv,
    which reads the file directly in the JVM without pickle calls.
"""

import os
import csv
import sqlite3
import logging
import tempfile
from typing import Tuple

from pyspark.sql import SparkSession, DataFrame

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "news.db")


def _resolve_db_path() -> str:
    path = os.path.abspath(_DB_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"SQLite database not found at: {path}\n"
            "Start the backend at least once so the DB is created."
        )
    return path


def sqlite_to_csv(csv_path: str) -> Tuple[list[str], int]:
    """
    Dump the articles table from SQLite to a CSV file.

    Returns (column_names, row_count).
    """
    db_path = _resolve_db_path()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT * FROM articles")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    con.close()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    logger.info(f"Exported {len(rows)} rows to CSV: {csv_path}")
    return cols, len(rows)


def load_articles_df(spark: SparkSession) -> Tuple[DataFrame, int]:
    """
    Load articles from SQLite into a Spark DataFrame via a CSV temp file.

    Returns (spark_dataframe, row_count).
    Registers the DataFrame as 'articles' temp view automatically.
    """
    tmp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(tmp_dir, "articles.csv")

    try:
        cols, count = sqlite_to_csv(csv_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        return spark.createDataFrame([], "article_id STRING"), 0

    if count == 0:
        logger.warning("No articles found in database.")
        return spark.createDataFrame([], "article_id STRING"), 0

    logger.info(f"Reading {count} rows into Spark via CSV...")
    sdf = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "false")
        .option("multiLine", "true")
        .option("escape", '"')
        .csv(csv_path)
    )
    sdf.createOrReplaceTempView("articles")
    logger.info("Spark temp view 'articles' registered.")

    # Schedule cleanup (best effort — Spark may still need the file briefly)
    try:
        os.remove(csv_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    return sdf, count
