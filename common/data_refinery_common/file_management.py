import os
import urllib
import shutil
import boto3
from data_refinery_models.models import Batch
from data_refinery_common.utils import get_env_variable


RAW_PREFIX = get_env_variable("RAW_PREFIX")
TEMP_PREFIX = get_env_variable("TEMP_PREFIX")
PROCESSED_PREFIX = get_env_variable("PROCESSED_PREFIX")
LOCAL_ROOT_DIR = get_env_variable("LOCAL_ROOT_DIR")
USE_S3 = get_env_variable("USE_S3") == "True"
S3_BUCKET_NAME = get_env_variable("S3_BUCKET_NAME")


def get_raw_dir(batch: Batch) -> str:
    if USE_S3:
        return os.path.join(RAW_PREFIX, batch.internal_location)
    else:
        return os.path.join(LOCAL_ROOT_DIR, RAW_PREFIX, batch.internal_location)


def get_download_path(batch: Batch) -> str:
    """Get the path to the downloaded file.

    In cases where extraction is necessary, this will not match the name
    of the batch's extracted file.
    """
    path = urllib.parse.urlparse(batch.download_url).path
    file_name = os.path.basename(path)
    return os.path.join(get_raw_dir(batch), file_name)


def get_raw_path(batch: Batch) -> str:
    return os.path.join(get_raw_dir(batch), batch.name)


# Use the ID of the batch in the temporary paths so it can be removed
# after processing is complete without interfering with other jobs.
def get_temp_dir(batch: Batch) -> str:
    return os.path.join(LOCAL_ROOT_DIR,
                        TEMP_PREFIX,
                        batch.internal_location,
                        str(batch.id))


def get_temp_pre_path(batch: Batch) -> str:
    """Returns the path of the pre-processed file for the batch."""
    return os.path.join(LOCAL_ROOT_DIR,
                        TEMP_PREFIX,
                        batch.internal_location,
                        str(batch.id),
                        batch.name)


def get_temp_post_path(batch: Batch) -> str:
    """Returns the path of the post-processed file for the batch."""
    # This may be brittle, there's probably a better way.
    file_base = batch.name.split(".")[0]
    new_name = file_base + "." + batch.processed_format
    return os.path.join(LOCAL_ROOT_DIR,
                        TEMP_PREFIX,
                        batch.internal_location,
                        str(batch.id),
                        new_name)


def get_processed_dir(batch: Batch) -> str:
    if USE_S3:
        return os.path.join(PROCESSED_PREFIX, batch.internal_location)
    else:
        return os.path.join(LOCAL_ROOT_DIR, PROCESSED_PREFIX, batch.internal_location)


def get_processed_path(batch: Batch) -> str:
    return os.path.join(get_processed_dir(batch), batch.name)


def download_raw_file(batch: Batch) -> None:
    """Moves the batch's raw file to the temp directory.

    Depending on the value of the USE_S3 environment variable this may
    just be from the RAW_PREFIX directory or it may be from S3.
    """
    raw_path = get_raw_path(batch)
    temp_dir = get_temp_dir(batch)
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = get_temp_pre_path(batch)
    if USE_S3:
        bucket = boto3.resource("s3").Bucket(S3_BUCKET_NAME)
        with open(temp_path, 'wb') as temp_file:
            bucket.download_fileobj(raw_path, temp_file)
    else:
        shutil.copyfile(raw_path, temp_path)


def upload_processed_file(batch: Batch) -> None:
    """Moves the batch's processed file out of the temp directory.

    Depending on the value of the USE_S3 environment variable this may
    just be to the PROCESSED_PREFIX directory or it may be to S3.
    """
    temp_path = get_temp_post_path(batch)
    processed_path = get_processed_path(batch)
    if USE_S3:
        bucket = boto3.resource("s3").Bucket(S3_BUCKET_NAME)
        with open(temp_path, 'rb') as temp_file:
            bucket.put_object(Key=processed_path, Body=temp_file)
    else:
        shutil.copyfile(temp_path, processed_path)


def remove_temp_directory(batch: Batch) -> None:
    temp_dir = get_temp_dir(batch)
    shutil.rmtree(temp_dir)


def remove_raw_files(batch: Batch) -> None:
    raw_path = get_raw_path(batch)
    if USE_S3:
        bucket = boto3.resource("s3").Bucket(S3_BUCKET_NAME)
        bucket.delete_objects(
            Delete={
                'Objects': {
                    'Key': raw_path
                }
            }
        )
    else:
        os.remove(raw_path)
