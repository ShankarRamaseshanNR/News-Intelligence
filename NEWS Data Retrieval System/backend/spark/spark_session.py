"""
spark_session.py
----------------
Singleton SparkSession factory for the News RAG PySpark layer.
Runs in local[*] mode — no Hadoop cluster required.
"""

import os
import logging
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

_spark: SparkSession | None = None

# ── Auto-detect JAVA_HOME if not set ──────────────────────────────────────
_CANDIDATE_JAVA_HOMES = [
    r"C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot",
    r"C:\Program Files\Eclipse Adoptium\jdk-17.0.10.7-hotspot",
    r"C:\Program Files\Java\jdk-17",
    r"C:\Program Files\Microsoft\jdk-17.0.10.17-hotspot",
]


def _ensure_java_home() -> None:
    """Set JAVA_HOME and PATH if Java isn't on the system path already."""
    if os.environ.get("JAVA_HOME"):
        return  # Already configured

    for candidate in _CANDIDATE_JAVA_HOMES:
        if os.path.isdir(candidate):
            os.environ["JAVA_HOME"] = candidate
            java_bin = os.path.join(candidate, "bin")
            os.environ["PATH"] = java_bin + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Auto-set JAVA_HOME to: {candidate}")
            return

    logger.warning(
        "JAVA_HOME not set and no known JDK directory found. "
        "PySpark may fail to start. Install Java 17 and set JAVA_HOME."
    )


def get_spark() -> SparkSession:
    """
    Return a shared SparkSession, creating it on first call.
    Configured for local mode with sensible defaults for a
    small-to-medium news dataset.
    """
    global _spark

    if _spark is not None and not _spark._sc._jsc.sc().isStopped():  # type: ignore[attr-defined]
        return _spark

    _ensure_java_home()
    logger.info("Initialising SparkSession (local[*] mode)...")

    # Suppress noisy Spark/Hadoop logs in development
    os.environ.setdefault("PYSPARK_PYTHON", "python")

    _spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("NewsRAG-PySpark")
        # Memory settings suitable for a dev machine
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        # Silence verbose Spark INFO logs
        .config("spark.ui.showConsoleProgress", "false")
        # SQLite JDBC is unavailable in stock PySpark; we use Pandas as bridge
        .getOrCreate()
    )

    # Reduce log verbosity
    _spark.sparkContext.setLogLevel("WARN")

    logger.info("SparkSession ready.")
    return _spark


def stop_spark() -> None:
    """Gracefully stop the SparkSession."""
    global _spark
    if _spark is not None:
        logger.info("Stopping SparkSession...")
        _spark.stop()
        _spark = None
