"""
Metric service for managing hippocampal volumetric measurements.

This service provides business logic for creating and retrieving
hippocampal asymmetry metrics.
"""

import json
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.models import Metric
from backend.schemas import MetricCreate

logger = get_logger(__name__)


class MetricService:
    """
    Service class for metric-related operations.
    
    Handles CRUD operations for hippocampal volumetric metrics.
    """
    
    @staticmethod
    def create_metric(db: Session, metric_data: MetricCreate) -> Metric:
        """
        Create a new metric.
        
        Args:
            db: Database session
            metric_data: Metric creation data
        
        Returns:
            Created metric instance
        """
        metric = Metric(
            job_id=str(metric_data.job_id),  # Convert UUID to string for SQLite
            region=metric_data.region,
            left_volume=metric_data.left_volume,
            right_volume=metric_data.right_volume,
            asymmetry_index=metric_data.asymmetry_index,
        )
        
        db.add(metric)
        db.commit()
        db.refresh(metric)
        
        logger.info(
            "metric_created",
            metric_id=str(metric.id),
            job_id=str(metric.job_id),
            region=metric.region,
            asymmetry_index=metric.asymmetry_index,
        )
        
        return metric
    
    @staticmethod
    def create_metrics_bulk(
        db: Session,
        metrics_data: List[MetricCreate]
    ) -> List[Metric]:
        """
        Create multiple metrics in bulk.
        
        Args:
            db: Database session
            metrics_data: List of metric creation data
        
        Returns:
            List of created metric instances
        """
        metrics = [
            Metric(
                job_id=str(data.job_id),  # Convert UUID to string for SQLite
                region=data.region,
                left_volume=data.left_volume,
                right_volume=data.right_volume,
                asymmetry_index=data.asymmetry_index,
            )
            for data in metrics_data
        ]
        
        db.add_all(metrics)
        db.commit()
        
        for metric in metrics:
            db.refresh(metric)
        
        logger.info(
            "metrics_created_bulk",
            count=len(metrics),
            job_id=str(metrics[0].job_id) if metrics else None,
        )
        
        return metrics
    
    @staticmethod
    def get_metric(db: Session, metric_id) -> Optional[Metric]:
        """
        Retrieve a metric by ID.
        
        Args:
            db: Database session
            metric_id: Metric identifier (UUID or string - will be converted to string for SQLite)
        
        Returns:
            Metric instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility
        metric_id_str = str(metric_id)
        return db.query(Metric).filter(Metric.id == metric_id_str).first()
    
    @staticmethod
    def get_metrics_by_job(db: Session, job_id) -> List[Metric]:
        """
        Retrieve all metrics for a specific job.
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
        
        Returns:
            List of metric instances
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        return db.query(Metric).filter(Metric.job_id == job_id_str).all()

    @staticmethod
    def extract_metrics(db: Session, job_id: str, output_dir: str) -> List[Metric]:
        """
        Extract metrics from processing output directory and save to database.

        Args:
            db: Database session
            job_id: Job identifier
            output_dir: Path to processing output directory

        Returns:
            List of created metric instances
        """
        from pathlib import Path

        metrics_file = Path(output_dir) / "metrics.json"
        if not metrics_file.exists():
            logger.warning(f"Metrics file not found: {metrics_file}")
            return []

        try:
            with open(metrics_file, 'r') as f:
                metrics_data = json.load(f)

            created_metrics = []
            for metric_data in metrics_data:
                # Create metric record
                metric_create = MetricCreate(
                    job_id=job_id,
                    region=metric_data.get('region', 'Hippocampus'),
                    left_volume=metric_data.get('left_volume'),
                    right_volume=metric_data.get('right_volume'),
                    asymmetry_index=metric_data.get('asymmetry_index')
                )

                metric = MetricService.create_metric(db, metric_create)
                created_metrics.append(metric)

            logger.info(f"Extracted and saved {len(created_metrics)} metrics for job {job_id}")
            return created_metrics

        except Exception as e:
            logger.error(f"Failed to extract metrics for job {job_id}: {e}")
            return []

    @staticmethod
    def get_metrics_by_region(db: Session, region: str) -> List[Metric]:
        """
        Retrieve all metrics for a specific hippocampal region.
        
        Args:
            db: Database session
            region: Hippocampal subregion name
        
        Returns:
            List of metric instances
        """
        return db.query(Metric).filter(Metric.region == region).all()

