from enum import Enum


class PipelineEnums(Enum):
    """An abstract class to enumerate valid processor pipelines.

    Enumerations which extend this class are valid values for the
    pipeline_required field of the Batches table.
    """
    pass


class ProcessorPipeline(PipelineEnums):
    """Pipelines which perform some kind of processing on the data."""
    AFFY_TO_PCL = "AFFY_TO_PCL"
    SALMON = "SALMON"
    TRANSCRIPTOME_INDEX_LONG = "TRANSCRIPTOME_INDEX_LONG"
    TRANSCRIPTOME_INDEX_SHORT = "TRANSCRIPTOME_INDEX_SHORT"
    NO_OP = "NO_OP"
    NONE = "NONE"


class DiscoveryPipeline(PipelineEnums):
    """Pipelines which discover appropriate processing for the data."""
    pass


class Downloaders(Enum):
    """An enumeration of downloaders for batch.downloader_task."""
    ARRAY_EXPRESS = "ARRAY_EXPRESS"
    SRA = "SRA"
    TRANSCRIPTOME_INDEX = "TRANSCRIPTOME_INDEX"

salmon --no-version-check quant -l A -i /home/user/data_store/Gallus_gallus_long/index -1 /home/user/data_store/DRX001563/DRR002116.fastq.gz -p 20 -o /home/user/data_store/DRX001563/proccessed/ --seqBias --gcBias --dumpEq --writeUnmappedNames

salmon --no-version-check quant -l A -i /home/user/data_store/Gallus_gallus_long/index -r /home/user/data_store/DRX001563/DRR002116.fastq.gz -p 20 -o /home/user/data_store/DRX001563/proccessed/ --seqBias --gcBias --dumpEq --writeUnmappedNames