from retrying import retry
from django.utils import timezone
from django.db import transaction
from data_refinery_models.models import (
    Batch,
    BatchStatuses,
    DownloaderJob,
    ProcessorJob,
    ProcessorJobsToBatches
)
from data_refinery_workers.processors.processor_registry \
    import processor_pipeline_registry

# Import and set logger
import logging
logger = logging.getLogger(__name__)


def start_job(job: DownloaderJob):
    """Record in the database that this job is being started. """
    job.worker_id = "For now there's only one. For now..."
    job.start_time = timezone.now()
    job.save()


def end_job(job: DownloaderJob, batches: Batch, success):
    """Record in the database that this job has completed.

    Create a processor job and queue a processor task for each batch
    if the job was successful.
    """
    @retry(stop_max_attempt_number=3)
    def save_batch_create_job(batch):
        batch.status = BatchStatuses.DOWNLOADED.value
        batch.save()

        logger.debug("Creating processor job for batch #%d.", batch.id)
        processor_job = ProcessorJob()
        processor_job.save()
        processor_job_to_batch = ProcessorJobsToBatches(batch=batch,
                                                        processor_job=processor_job)
        processor_job_to_batch.save()
        return processor_job

    @retry(stop_max_attempt_number=3)
    def queue_task(processor_job):
        processor_task = processor_pipeline_registry[batch.pipeline_required]
        logger.debug("Queuing processor task %s for Job %d.",
                     processor_task.name,
                     processor_job.id)
        processor_task.delay(processor_job.id)

    if success:
        for batch in batches:
            with transaction.atomic():
                processor_job = save_batch_create_job(batch)
                queue_task(processor_job)

    job.success = success
    job.end_time = timezone.now()
    job.save()
