import requests
from typing import List, Dict

from data_refinery_common.models import (
    Batch,
    BatchKeyValue,
    SurveyJobKeyValue,
    Organism
)
from data_refinery_foreman.surveyor.external_source import ExternalSourceSurveyor
from data_refinery_common.job_lookup import ProcessorPipeline, Downloaders
import xml.etree.ElementTree as ET

# Import and set logger
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDBJ_URL_BASE = "ftp://ftp.ddbj.nig.ac.jp/ddbj_database/dra/fastq/"
ENA_URL_TEMPLATE = "https://www.ebi.ac.uk/ena/data/view/{}&display=xml"
TEST_XML = "SRA200/SRA200001"
TAIL = "SRA200001.run.xml"

# SRA has a convention around its accession IDs. Each accession ID has
# a three letter prefix. The first is what organization the data was
# submitted to:
# A - America
# E - Europe
# D - Japan

# The second letter is presumably related to the type of data, but for
# RNA data it is always R so I haven't needed to verify this. The
# third letter corresponds to what type of data the accession ID is
# referring to:
SUBMISSION_CODE = "A"
EXPERIMENT_CODE = "X"
STUDY_CODE = "P"
SAMPLE_CODE = "S"
RUN_CODE = "R"


class UnsupportedDataTypeError(BaseException):
    pass


class SraSurveyor(ExternalSourceSurveyor):
    def source_type(self):
        return Downloaders.SRA.value

    def determine_pipeline(self,
                           batch: Batch,
                           key_values: List[BatchKeyValue] = []):
        return ProcessorPipeline.SALMON

    @staticmethod
    def gather_submission_metadata(metadata: Dict) -> None:
        response = requests.get(ENA_URL_TEMPLATE.format(metadata["submission_accession"]))
        submission_xml = ET.fromstring(response.text)[0]
        submission_metadata = submission_xml.attrib

        # We already have these
        submission_metadata.pop("accession")
        submission_metadata.pop("alias")

        metadata.update(submission_metadata)

        for child in submission_xml:
            if child.tag == "TITLE":
                metadata["submission_title"] = child.text
            elif child.tag == "SUBMISSION_ATTRIBUTES":
                for grandchild in child:
                    metadata[grandchild.find("TAG").text.lower()] = grandchild.find("VALUE").text

    @staticmethod
    def gather_library_metadata(metadata: Dict, library: ET.Element) -> None:
        for child in library:
            if child.tag == "LIBRARY_LAYOUT":
                metadata["library_layout"] = child[0].tag
            else:
                metadata[child.tag.lower()] = child.text

        # SRA contains several types of data. We only want RNA-Seq for now.
        if metadata["library_strategy"] != "RNA-Seq":
            raise UnsupportedDataTypeError("library_strategy not RNA-Seq.")
        if metadata["library_source"] not in ["TRANSCRIPTOMIC", "OTHER"]:
            raise UnsupportedDataTypeError("library_source not TRANSCRIPTOMIC or OTHER.")

    @staticmethod
    def parse_read_spec(metadata: Dict, read_spec: ET.Element, counter: int) -> None:
        for child in read_spec:
            key = "read_spec_{}_{}".format(str(counter), child.tag.replace("READ_", "").lower())
            metadata[key] = child.text

    @staticmethod
    def gather_spot_metadata(metadata: Dict, spot: ET.Element) -> None:
        """We don't actually know what this metadata is about."""
        for child in spot:
            if child.tag == "SPOT_DECODE_SPEC":
                read_spec_counter = 0
                for grandchild in child:
                    if grandchild.tag == "SPOT_LENGTH":
                        metadata["spot_length"] = grandchild.text
                    elif grandchild.tag == "READ_SPEC":
                        SraSurveyor.parse_read_spec(metadata, grandchild, read_spec_counter)
                        read_spec_counter = read_spec_counter + 1

    @staticmethod
    def gather_experiment_metadata(metadata: Dict) -> None:
        response = requests.get(ENA_URL_TEMPLATE.format(metadata["experiment_accession"]))
        experiment_xml = ET.fromstring(response.text)

        experiment = experiment_xml[0]
        for child in experiment:
            if child.tag == "TITLE":
                metadata["experiment_title"] = child.text
            elif child.tag == "DESIGN":
                for grandchild in child:
                    if grandchild.tag == "DESIGN_DESCRIPTION":
                        metadata["experiment_desing_description"] = grandchild.text
                    elif grandchild.tag == "LIBRARY_DESCRIPTOR":
                        SraSurveyor.gather_library_metadata(metadata, grandchild)
                    elif grandchild.tag == "SPOT_DESCRIPTOR":
                        SraSurveyor.gather_spot_metadata(metadata, grandchild)
            elif child.tag == "PLATFORM":
                # This structure is extraneously nested.
                metadata["platform_instrument_model"] = child[0][0].text

    @staticmethod
    def parse_run_link(run_link: ET.ElementTree) -> (str, str):
        key = ""
        value = ""

        # The first level in this element is a XREF_LINK which is
        # really just an unnecessary level
        for child in run_link[0]:
            if child.tag == "DB":
                key = child.text.lower().replace("ena-", "") + "_accession"
            elif child.tag == "ID":
                value = child.text

        return (key, value)

    @staticmethod
    def parse_attribute(attribute: ET.ElementTree, key_prefix: str ="") -> (str, str):
        key = ""
        value = ""

        for child in attribute:
            if child.tag == "TAG":
                key = key_prefix + child.text.lower().replace("-", "_").replace(" ", "_")
            elif child.tag == "VALUE":
                value = child.text

        return (key, value)

    @staticmethod
    def gather_run_metadata(run_accession: str) -> Dict:
        """A run refers to a specific read in an experiment."""
        discoverable_accessions = ["study_accession", "sample_accession", "submission_accession"]
        response = requests.get(ENA_URL_TEMPLATE.format(run_accession))
        run_xml = ET.fromstring(response.text)
        run = run_xml[0]

        useful_attributes = ["center_name", "run_center", "run_date", "broker_name"]
        metadata = {key: run.attrib[key] for key in useful_attributes}
        metadata["run_accession"] = run_accession

        for child in run:
            if child.tag == "EXPERIMENT_REF":
                metadata["experiment_accession"] = child.attrib["accession"]
            elif child.tag == "RUN_LINKS":
                for grandchild in child:
                    key, value = SraSurveyor.parse_run_link(grandchild)
                    if value != "" and key in discoverable_accessions:
                        metadata[key] = value
            elif child.tag == "RUN_ATTRIBUTES":
                for grandchild in child:
                    key, value = SraSurveyor.parse_attribute(grandchild, "run_")
                    metadata[key] = value

        return metadata

    @staticmethod
    def gather_sample_metadata(metadata: Dict) -> None:
        response = requests.get(ENA_URL_TEMPLATE.format(metadata["sample_accession"]))
        sample_xml = ET.fromstring(response.text)

        sample = sample_xml[0]
        metadata["sample_center_name"] = sample.attrib["center_name"]
        for child in sample:
            if child.tag == "TITLE":
                metadata["sample_title"] = child.text
            elif child.tag == "SAMPLE_NAME":
                for grandchild in child:
                    if grandchild.tag == "TAXON_ID":
                        metadata["organism_id"] = grandchild.text
                    elif grandchild.tag == "SCIENTIFIC_NAME":
                        metadata["organism_name"] = grandchild.text.upper()
            elif child.tag == "SAMPLE_ATTRIBUTES":
                for grandchild in child:
                    key, value = SraSurveyor.parse_attribute(grandchild, "sample_")
                    metadata[key] = value

    @staticmethod
    def gather_study_metadata(metadata: Dict) -> None:
        metadata = {"study_accession": "DRP000595"}
        response = requests.get(ENA_URL_TEMPLATE.format(metadata["study_accession"]))
        study_xml = ET.fromstring(response.text)

        study = study_xml[0]
        for child in study:
            if child.tag == "DESCRIPTOR":
                for grandchild in child:
                    # STUDY_TYPE is the only tag which uses attributes
                    # instead of the text for whatever reason
                    if grandchild.tag == "STUDY_TYPE":
                        metadata[grandchild.tag.lower()] = grandchild.attrib["existing_study_type"]
                    else:
                        metadata[grandchild.tag.lower()] = grandchild.text
            elif child.tag == "STUDY_ATTRIBUTES":
                for grandchild in child:
                    key, value = SraSurveyor.parse_attribute(grandchild, "study_")
                    metadata[key] = value

    @staticmethod
    def gather_all_metadata(run_accession):
        metadata = SraSurveyor.gather_run_metadata(run_accession)

        SraSurveyor.gather_experiment_metadata(metadata)
        SraSurveyor.gather_sample_metadata(metadata)
        SraSurveyor.gather_study_metadata(metadata)
        SraSurveyor.gather_submission_metadata(metadata)

        return metadata

    def _generate_batches(self,
                          samples: List[Dict],
                          experiment: Dict,
                          replicate_raw: bool=True) -> List[Batch]:
        """Generates a Batch for each sample in samples.

        Uses the metadata contained in experiment (which should be
        generated via get_experiment_metadata) to add additional
        metadata to each Batch. If replicate_raw is True (the default)
        then only raw files will be replicated. Otherwise all files
        will be replicated.
        """
        batches = []
        for sample in samples:
            if "file" not in sample:
                continue

            organism_name = "UNKNOWN"
            for characteristic in sample["characteristic"]:
                if characteristic["category"].upper() == "ORGANISM":
                    organism_name = characteristic["value"].upper()

            if organism_name == "UNKNOWN":
                logger.error("Sample from experiment %s did not specify the organism name.",
                             experiment["experiment_accession_code"])
                organism_id = 0
            else:
                organism_id = Organism.get_id_for_name(organism_name)

            for sample_file in sample["file"]:
                # Generally we only want to replicate the raw data if
                # we can, however if there isn't raw data then we'll
                # take the processed stuff.
                if (replicate_raw and sample_file["type"] != "data") \
                        or sample_file["name"] is None:
                    continue

                # sample_file["comment"] is only a list if there's
                # more than one comment...
                comments = sample_file["comment"]
                if isinstance(comments, list):
                    # Could be: "Derived ArrayExpress Data Matrix FTP
                    # file" or: "ArrayExpress FTP file". If there is
                    # no comment with a name including "FTP file" then
                    # we don't know where to download it so we need to
                    # mark this job as an error. Therefore don't catch
                    # the potential exception where download_url
                    # doesn't get defined.
                    for comment in comments:
                        if comment["name"].find("FTP file") != -1:
                            download_url = comment["value"]
                else:
                    download_url = comments["value"]

                raw_format = sample_file["name"].split(".")[-1]
                processed_format = "PCL" if replicate_raw else raw_format

                batches.append(Batch(
                    size_in_bytes=-1,  # Will have to be determined later
                    download_url=download_url,
                    raw_format=raw_format,
                    processed_format=processed_format,
                    platform_accession_code=experiment["platform_accession_code"],
                    experiment_accession_code=experiment["experiment_accession_code"],
                    organism_id=organism_id,
                    organism_name=organism_name,
                    experiment_title=experiment["name"],
                    release_date=experiment["release_date"],
                    last_uploaded_date=experiment["last_update_date"],
                    name=sample_file["name"]
                ))

        return batches

    def survey(self) -> bool:
        experiment_accession_code = (
            SurveyJobKeyValue
            .objects
            .get(survey_job_id=self.survey_job.id,
                 key__exact="experiment_accession_code")
            .value
        )

        logger.info("Surveying experiment with accession code: %s.", experiment_accession_code)

        experiment = self.get_experiment_metadata(experiment_accession_code)
        r = requests.get(SAMPLES_URL.format(experiment_accession_code))
        samples = r.json()["experiment"]["sample"]
        batches = self._generate_batches(samples, experiment)

        if len(samples) != 0 and len(batches) == 0:
            # Found no samples with raw data, so replicate the
            # processed data instead
            batches = self._generate_batches(samples, experiment, replicate_raw=False)

        # Group batches based on their download URL and handle each group.
        download_urls = {batch.download_url for batch in batches}
        for url in download_urls:
            batches_with_url = [batch for batch in batches if batch.download_url == url]
            try:
                self.handle_batches(batches_with_url)
            except Exception:
                return False

        return True
