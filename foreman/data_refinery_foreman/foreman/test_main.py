from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from data_refinery_foreman.foreman import main
from data_refinery_common.models import (
    SurveyJob,
    DownloaderJob,
    ProcessorJob,
    OriginalFile,
    Dataset,
    DownloaderJobOriginalFileAssociation,
    ProcessorJobOriginalFileAssociation,
    ProcessorJobDatasetAssociation,
)


class SurveyTestCase(TestCase):
    def setUp(self):
        survey_job = SurveyJob(source_type="ARRAY_EXPRESS")
        survey_job.save()
        self.survey_job = survey_job

    def create_downloader_job(self):
        job = DownloaderJob(downloader_task="SRA",
                            nomad_job_id="DOWNLOADER/dispatch-1528945054-e8eaf540",
                            num_retries=0,
                            accession_code="NUNYA",
                            success=None)
        job.save()

        og_file = OriginalFile()
        og_file.source_filename = "doesn't matter"
        og_file.filename = "this either"
        og_file.absolute_file_path = "nor this"
        og_file.save()

        assoc1 = DownloaderJobOriginalFileAssociation()
        assoc1.original_file = og_file
        assoc1.downloader_job = job
        assoc1.save()

        og_file = OriginalFile()
        og_file.source_filename = "doesn't matter"
        og_file.filename = "this either"
        og_file.absolute_file_path = "nor this"
        og_file.save()

        assoc = DownloaderJobOriginalFileAssociation()
        assoc.original_file = og_file
        assoc.downloader_job = job
        assoc.save()

        return job

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_requeuing_downloader_job(self, mock_send_job):
        job = self.create_downloader_job()

        main.requeue_downloader_job(job)
        mock_send_job.assert_called_once()

        jobs = DownloaderJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

        self.assertEqual(retried_job.original_files.count(), 2)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_repeated_download_failures(self, mock_send_job):
        """Jobs will be repeatedly retried."""
        job = self.create_downloader_job()

        for i in range(main.MAX_NUM_RETRIES):
            main.handle_downloader_jobs([job])
            self.assertEqual(i + 1, len(mock_send_job.mock_calls))

            jobs = DownloaderJob.objects.all().order_by("-id")
            previous_job = jobs[1]
            self.assertTrue(previous_job.retried)
            self.assertEqual(previous_job.num_retries, i)
            self.assertFalse(previous_job.success)

            job = jobs[0]
            self.assertFalse(job.retried)
            self.assertEqual(job.num_retries, i + 1)

        # Once MAX_NUM_RETRIES has been hit handle_repeated_failure
        # should be called.
        main.handle_downloader_jobs([job])
        last_job = DownloaderJob.objects.all().order_by("-id")[0]
        self.assertTrue(last_job.retried)
        self.assertEqual(last_job.num_retries, main.MAX_NUM_RETRIES)
        self.assertFalse(last_job.success)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_failed_downloader_jobs(self, mock_send_job):
        job = self.create_downloader_job()
        job.success = False
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_failed_downloader_jobs.__wrapped__()
        mock_send_job.assert_called_once()

        jobs = DownloaderJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_hung_downloader_jobs(self, mock_send_job):
        job = self.create_downloader_job()
        job.start_time = timezone.now() - main.MAX_DOWNLOADER_RUN_TIME - timedelta(seconds=1)
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_hung_downloader_jobs.__wrapped__()
        mock_send_job.assert_called_once()

        jobs = DownloaderJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_lost_downloader_jobs(self, mock_send_job):
        job = self.create_downloader_job()
        job.created_at = timezone.now() - main.MAX_QUEUE_TIME - timedelta(seconds=1)
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_lost_downloader_jobs.__wrapped__()
        mock_send_job.assert_called_once()

        jobs = DownloaderJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    def create_processor_job(self):
        job = ProcessorJob(pipeline_applied="AFFY_TO_PCL",
                           nomad_job_id="PROCESSOR/dispatch-1528945054-e8eaf540",
                           num_retries=0,
                           success=None)
        job.save()

        og_file = OriginalFile()
        og_file.source_filename = "doesn't matter"
        og_file.filename = "this either"
        og_file.absolute_file_path = "nor this"
        og_file.save()

        assoc1 = ProcessorJobOriginalFileAssociation()
        assoc1.original_file = og_file
        assoc1.processor_job = job
        assoc1.save()

        og_file = OriginalFile()
        og_file.source_filename = "doesn't matter"
        og_file.filename = "this either"
        og_file.absolute_file_path = "nor this"
        og_file.save()

        assoc = ProcessorJobOriginalFileAssociation()
        assoc.original_file = og_file
        assoc.processor_job = job
        assoc.save()

        return job

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_requeuing_processor_job(self, mock_send_job):
        job = self.create_processor_job()

        main.requeue_processor_job(job)
        mock_send_job.assert_called_once()

        jobs = ProcessorJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_repeated_processor_failures(self, mock_send_job):
        """Jobs will be repeatedly retried."""
        job = self.create_processor_job()

        for i in range(main.MAX_NUM_RETRIES):
            main.handle_processor_jobs([job])
            self.assertEqual(i + 1, len(mock_send_job.mock_calls))

            jobs = ProcessorJob.objects.all().order_by("-id")
            previous_job = jobs[1]
            self.assertTrue(previous_job.retried)
            self.assertEqual(previous_job.num_retries, i)
            self.assertFalse(previous_job.success)

            job = jobs[0]
            self.assertFalse(job.retried)
            self.assertEqual(job.num_retries, i + 1)

        # Once MAX_NUM_RETRIES has been hit handle_repeated_failure
        # should be called.
        main.handle_processor_jobs([job])
        last_job = ProcessorJob.objects.all().order_by("-id")[0]
        self.assertTrue(last_job.retried)
        self.assertEqual(last_job.num_retries, main.MAX_NUM_RETRIES)
        self.assertFalse(last_job.success)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_failed_processor_jobs(self, mock_send_job):
        job = self.create_processor_job()
        job.success = False
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_failed_processor_jobs.__wrapped__()
        mock_send_job.assert_called_once()

        jobs = ProcessorJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_hung_processor_jobs(self, mock_send_job):
        job = self.create_processor_job()
        job.start_time = timezone.now() - main.MAX_PROCESSOR_RUN_TIME - timedelta(seconds=1)
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_hung_processor_jobs.__wrapped__()
        mock_send_job.assert_called_once()

        jobs = ProcessorJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)

    @patch('data_refinery_foreman.foreman.main.send_job')
    def test_retrying_lost_processor_jobs(self, mock_send_job):
        job = self.create_processor_job()
        job.created_at = timezone.now() - main.MAX_QUEUE_TIME - timedelta(seconds=1)
        job.save()

        # Just run it once, not forever so get the function that is
        # decorated with @do_forever
        main.retry_lost_processor_jobs.__wrapped__()

        mock_send_job.assert_called_once()

        jobs = ProcessorJob.objects.order_by('id')
        original_job = jobs[0]
        self.assertTrue(original_job.retried)
        self.assertEqual(original_job.num_retries, 0)
        self.assertFalse(original_job.success)

        retried_job = jobs[1]
        self.assertEqual(retried_job.num_retries, 1)
