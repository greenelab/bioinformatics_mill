"""This command will create and run survey jobs for each experiment
in the experiment_list. experiment list should be a file containing
one experiment accession code per line.
"""

import boto3
import botocore
import nomad
import uuid

from django.core.management.base import BaseCommand

from data_refinery_common.logging import get_and_configure_logger
from data_refinery_common.message_queue import send_job
from data_refinery_common.utils import parse_s3_url, get_env_variable
from data_refinery_foreman.surveyor import surveyor

logger = get_and_configure_logger(__name__)

SURVEYOR_JOB_NAME = "SURVEYOR"

def queue_surveyor_for_accession(accession: str) -> None:
    """Dispatches a surveyor job for the accession code."""
    nomad_host = get_env_variable("NOMAD_HOST")
    nomad_port = get_env_variable("NOMAD_PORT", "4646")
    nomad_client = nomad.Nomad(nomad_host, port=int(nomad_port), timeout=5)

    try:
        nomad_response = nomad_client.job.dispatch_job("SURVEYOR", meta={"ACCESSION": accession})
    except URLNotFoundNomadException:
        logger.error("Dispatching Surveyor Nomad job to host %s and port %s failed.",
                     job_type, nomad_job, nomad_host, nomad_port, accession_code=accession)
    except Exception as e:
        logger.exception('Unable to Dispatch Nomad Job.',
            job_name=job_type.value,
            job_id=str(job.id),
            reason=str(e)
        )

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help=("""An file listing accession codes. s3:// URLs are also accepted."

Note: One entry per line, GSE* entries survey GEO, E-GEO-* entries survey ArrayExpress.
""")
        )

        parser.add_argument(
            "--offset",
            type=int,
            help=("Skip a number of lines at the beginning"),
            default=0
        )

    def handle(self, *args, **options):
        if options['file'] is None:
            logger.error("You must specify a file.")
            return "1"

        if 's3://' in options["file"]:
            bucket, key = parse_s3_url(options["file"])
            s3 = boto3.resource('s3')
            try:
                filepath = "/tmp/input_" + str(uuid.uuid4()) + ".txt"
                s3.Bucket(bucket).download_file(key, filepath)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == "404":
                    logger.error("The remote file does not exist.")
                    raise
                else:
                    raise
        else:
            filepath = options["file"]

        with open(filepath) as accession_file:
            for i, accession in enumerate(accession_file):
                if i < options["offset"]:
                    continue
                accession = accession.strip()
                try:
                    queue_surveyor_for_accession(accession)
                except Exception as e:
                    logger.exception(e)
