import time
from typing import Callable
from threading import Thread
from functools import wraps
from retrying import retry
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from data_refinery_models.models import (
    WorkerJob,
    DownloaderJob,
    ProcessorJob
)
from data_refinery_foreman.surveyor.message_queue import app

# Import and set logger
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Maximum number of retries, so the number of attempts will be one
# greater than this because of the first attempt
MAX_NUM_RETRIES = 2

# For now it seems like no jobs should take longer than a day to be
# either picked up or run.
MAX_DOWNLOADER_RUN_TIME = timedelta(days=1)
MAX_PROCESSOR_RUN_TIME = timedelta(days=1)
MAX_QUEUE_TIME = timedelta(days=1)

# To prevent excessive spinning loop no more than once every 10
# seconds.
MIN_LOOP_TIME = timedelta(seconds=10)

PROCESSOR_PIPELINE_LOOKUP = {
    "AFFY_TO_PCL": "data_refinery_workers.processors.array_express.affy_to_pcl"
}


@retry(stop_max_attempt_number=3)
@transaction.atomic
def requeue_downloader_job(last_job: DownloaderJob) -> None:
    num_retries = last_job.num_retries + 1

    new_job = DownloaderJob.create_job_and_relationships(num_retries=num_retries,
                                                         batches=list(last_job.batches.all()),
                                                         downloader_task=last_job.downloader_task)
    app.send_task(last_job.downloader_task, args=[new_job.id])
    last_job.retried = True
    last_job.success = False
    last_job.save()


def handle_repeated_failure(job: WorkerJob) -> None:
    # Not strictly retried but will prevent the job from getting
    # retried any more times.
    job.retried = True
    # success may already be False, but if it was a hung or lost job
    # this will ensure it's marked as failed.
    job.success = False
    job.save()

    # At some point this should become more noisy/attention
    # grabbing. However for the time just logging should be sufficient
    # because all log messages will be closely monitored during early
    # testing stages.
    logger.warn("%s #%d failed %d times!!!", job.__name__, job.id, MAX_NUM_RETRIES + 1)


def handle_downloader_jobs(jobs: DownloaderJob) -> None:
    for job in jobs:
        if job.num_retries >= MAX_NUM_RETRIES:
            requeue_downloader_job(job)
        else:
            handle_repeated_failure(job)


def do_forever(min_loop_time: int) -> Callable:
    def decorator(function: Callable) -> Callable:
        @wraps(function)
        def wrapper():
            while(True):
                start_time = timezone.now()

                function()

                loop_time = timezone.now() - start_time
                if loop_time < min_loop_time:
                    remaining_time = MIN_LOOP_TIME - loop_time
                    time.sleep(remaining_time.seconds)

        return wrapper
    return decorator


@do_forever(MIN_LOOP_TIME)
def retry_failed_downloader_jobs() -> None:
    failed_jobs = DownloaderJob.objects.filter(success=False, retried=False)
    handle_downloader_jobs(failed_jobs)


@do_forever(MIN_LOOP_TIME)
def retry_hung_downloader_jobs() -> None:
    minimum_start_time = timezone.now() - MAX_DOWNLOADER_RUN_TIME
    hung_jobs = DownloaderJob.objects.filter(
        success=None,
        retried=False,
        end_time=None,
        start_time__lt=minimum_start_time
    )

    handle_downloader_jobs(hung_jobs)


@do_forever(MIN_LOOP_TIME)
def retry_lost_downloader_jobs() -> None:
    """Idea: at some point this function could integrate with the spot
    instances to determine if jobs are hanging due to a lack of
    instances. A naive time-based implementation like this could end up
    retrying every single queued job if there were a long period of spot
    instance bid price being very high."""
    minimum_creation_time = timezone.now() - MAX_QUEUE_TIME
    lost_jobs = DownloaderJob.objects.filter(
        success=None,
        retried=False,
        start_time=None,
        end_time=None,
        created_at__lt=minimum_creation_time
    )

    handle_downloader_jobs(lost_jobs)


@retry(stop_max_attempt_number=3)
@transaction.atomic
def requeue_processor_job(last_job: ProcessorJob) -> None:
    num_retries = last_job.num_retries + 1

    new_job = ProcessorJob.create_job_and_relationships(num_retries=num_retries,
                                                        batches=list(last_job.batches.all()),
                                                        pipeline_applied=last_job.pipeline_applied)
    processor_task = PROCESSOR_PIPELINE_LOOKUP[last_job.pipeline_applied]
    app.send_task(processor_task, args=[new_job.id])


def handle_processor_jobs(jobs: ProcessorJob) -> None:
    for job in jobs:
        if job.num_retries >= MAX_NUM_RETRIES:
            requeue_processor_job(job)
        else:
            handle_repeated_failure(job)


@do_forever(MIN_LOOP_TIME)
def retry_failed_processor_jobs() -> None:
    failed_jobs = ProcessorJob.objects.filter(success=False, retried=False)
    handle_processor_jobs(failed_jobs)


@do_forever(MIN_LOOP_TIME)
def retry_hung_processor_jobs() -> None:
    minimum_start_time = timezone.now() - MAX_DOWNLOADER_RUN_TIME
    hung_jobs = ProcessorJob.objects.filter(
        success=None,
        retried=False,
        end_time=None,
        start_time__lt=minimum_start_time
    )

    handle_processor_jobs(hung_jobs)


@do_forever(MIN_LOOP_TIME)
def retry_lost_processor_jobs() -> None:
    minimum_creation_time = timezone.now() - MAX_QUEUE_TIME
    lost_jobs = ProcessorJob.objects.filter(
        success=None,
        retried=False,
        start_time=None,
        end_time=None,
        created_at__lt=minimum_creation_time
    )

    handle_processor_jobs(lost_jobs)


def monitor_jobs():
    """Starts the retry threads and then chill."""
    threads = []
    thread = Thread(target=retry_failed_downloader_jobs)
    thread.start()
    threads.append(thread)

    thread = Thread(target=retry_hung_downloader_jobs)
    thread.start()
    threads.append(thread)

    thread = Thread(target=retry_lost_downloader_jobs)
    thread.start()
    threads.append(thread)

    thread = Thread(target=retry_failed_processor_jobs)
    thread.start()
    threads.append(thread)

    thread = Thread(target=retry_hung_processor_jobs)
    thread.start()
    threads.append(thread)

    thread = Thread(target=retry_lost_processor_jobs)
    thread.start()
    threads.append(thread)

    for thread in threads:
        thread.join()
