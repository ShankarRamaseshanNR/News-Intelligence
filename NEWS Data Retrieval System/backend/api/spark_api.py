"""
spark_api.py
------------
FastAPI router exposing PySpark batch jobs via REST endpoints.

Endpoints
---------
GET /api/spark/status        — Check if Spark is available
GET /api/spark/analytics     — Run the full analytics batch job
GET /api/spark/sentiment     — Run the bulk sentiment re-analysis job
GET /api/spark/preprocess    — Run the text preprocessing job
"""

import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spark", tags=["Spark Analytics"])


def _check_spark_available() -> bool:
    """Quick check that PySpark is importable and Java is reachable."""
    try:
        from spark.spark_session import get_spark
        spark = get_spark()
        return not spark._sc._jsc.sc().isStopped()  # type: ignore[attr-defined]
    except Exception as e:
        logger.error(f"Spark not available: {e}")
        return False


@router.get("/status")
async def spark_status():
    """
    Check whether PySpark is available and the SparkSession is healthy.
    """
    available = _check_spark_available()
    if not available:
        return {
            "spark_available": False,
            "message": (
                "PySpark is not available. "
                "Ensure Java 17 is installed and pyspark is in requirements.txt."
            ),
        }

    from spark.spark_session import get_spark
    spark = get_spark()
    return {
        "spark_available": True,
        "master": spark.sparkContext.master,
        "app_name": spark.sparkContext.appName,
        "spark_version": spark.version,
        "message": "SparkSession is running.",
    }


@router.get("/analytics")
async def spark_analytics():
    """
    Run the PySpark analytics batch job over the full article corpus.

    Computes:
    - Total article count
    - Articles per category
    - Sentiment distribution
    - Top 10 sources
    - Daily article trend (last 30 days)
    - Average content length per category
    """
    if not _check_spark_available():
        raise HTTPException(
            status_code=503,
            detail="PySpark is not available. Check Java installation.",
        )
    try:
        from spark.jobs.spark_analytics import run_analytics_job
        result = run_analytics_job()
        return result
    except Exception as e:
        logger.exception("Spark analytics job failed")
        raise HTTPException(status_code=500, detail=f"Spark analytics job error: {e}")


@router.get("/sentiment")
async def spark_sentiment():
    """
    Run the PySpark bulk sentiment re-analysis batch job.

    Re-applies the keyword-based sentiment heuristic across all articles
    using Spark UDFs, and reports mismatches vs stored labels.
    """
    if not _check_spark_available():
        raise HTTPException(
            status_code=503,
            detail="PySpark is not available. Check Java installation.",
        )
    try:
        from spark.jobs.spark_sentiment import run_sentiment_job
        result = run_sentiment_job()
        return result
    except Exception as e:
        logger.exception("Spark sentiment job failed")
        raise HTTPException(status_code=500, detail=f"Spark sentiment job error: {e}")


@router.get("/preprocess")
async def spark_preprocess():
    """
    Run the PySpark text preprocessing batch job.

    Applies HTML stripping, URL removal, keyword extraction, and chunk-count
    estimation across the full article corpus.
    """
    if not _check_spark_available():
        raise HTTPException(
            status_code=503,
            detail="PySpark is not available. Check Java installation.",
        )
    try:
        from spark.jobs.spark_preprocessing import run_preprocessing_job
        result = run_preprocessing_job()
        return result
    except Exception as e:
        logger.exception("Spark preprocessing job failed")
        raise HTTPException(status_code=500, detail=f"Spark preprocessing job error: {e}")
