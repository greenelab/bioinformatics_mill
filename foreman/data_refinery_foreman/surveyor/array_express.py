import requests
from typing import List
from data_refinery_models.models import (
    Batch,
    BatchKeyValue,
    SurveyJob,
    SurveyJobKeyValue
)
from data_refinery_foreman.surveyor.external_source import (
    ExternalSourceSurveyor,
    ProcessorPipeline
)

# Import and set logger
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArrayExpressSurveyor(ExternalSourceSurveyor):
    # Files API endpoint for ArrayExpress
    FILES_URL = "http://www.ebi.ac.uk/arrayexpress/json/v2/files"
    DOWNLOADER_TASK = "data_refinery_workers.downloaders.array_express.download_array_express"

    def source_type(self):
        return "ARRAY_EXPRESS"

    def downloader_task(self):
        return self.DOWNLOADER_TASK

    def determine_pipeline(self,
                           batch: Batch,
                           key_values: List[BatchKeyValue] = []):
        return ProcessorPipeline.AFFY_TO_PCL

    def survey(self, survey_job: SurveyJob):
        accession_code = (SurveyJobKeyValue
                          .objects
                          .filter(survey_job_id=survey_job.id,
                                  key__exact="accession_code")
                          [:1]
                          .get()
                          .value)
        parameters = {"raw": "true", "array": accession_code}

        r = requests.get(self.FILES_URL, params=parameters)
        response_dictionary = r.json()

        try:
            experiments = response_dictionary["files"]["experiment"]
        except KeyError:  # If the platform does not exist or has no files...
            logger.info(
                "No files were found with this platform accession code: %s",
                accession_code
            )
            return True

        logger.info("Found %d new experiments for Survey Job #%d.",
                    len(experiments),
                    survey_job.id)

        for experiment in experiments:
            data_files = experiment["file"]

            # If there is only one file object in data_files,
            # ArrayExpress does not put it in a list of size 1
            if (type(data_files) != list):
                data_files = [data_files]

            for data_file in data_files:
                if (data_file["kind"] == "raw"):
                    url = data_file["url"].replace("\\", "")
                    # This is another place where this is still a POC.
                    # More work will need to be done to determine some
                    # of these additional metadata fields.
                    self.handle_batch(Batch(size_in_bytes=data_file["size"],
                                            download_url=url,
                                            raw_format="MICRO_ARRAY",
                                            processed_format="PCL",
                                            accession_code=accession_code,
                                            organism=1))

        return True
