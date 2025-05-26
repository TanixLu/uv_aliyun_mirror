import os
from typing import List, Union
from pathlib import Path
import zipfile
from io import BytesIO
from base64 import b64encode

import oss2
from alibabacloud_tea_openapi.client import Client as OpenApiClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

access_key_id = os.environ["ACCESS_KEY_ID"]
access_key_secret = os.environ["ACCESS_KEY_SECRET"]

fc_endpoint = "1671029124596767.cn-hangzhou.fc.aliyuncs.com"

oss_endpoint = "https://oss-cn-hangzhou.aliyuncs.com"
oss_region = "cn-hangzhou"
oss_bucket_name = "uv-mirror-bucket"
oss_auth = oss2.AuthV4(access_key_id, access_key_secret)
oss_bucket = oss2.Bucket(oss_auth, oss_endpoint, oss_bucket_name, region=oss_region)


def zip2base64(path_list: List[Path]) -> str:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in path_list:
            if path.is_dir():
                for file in path.rglob("*"):
                    if file.is_file():
                        arcname = str(file.relative_to(path.parent))
                        zip_file.write(file, arcname)
            else:
                arcname = path.name
                zip_file.write(path, arcname)
    return b64encode(zip_buffer.getvalue()).decode()


def fc_upload(path_list: List[Path], service_name: str, function_name: str) -> None:
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=fc_endpoint,
    )

    open_api_client = OpenApiClient(config)

    runtime = util_models.RuntimeOptions()

    function_path = f"{service_name}%24{function_name}"

    params = open_api_models.Params(
        action="UpdateFunction",
        version="2023-03-30",
        protocol="HTTPS",
        method="PUT",
        auth_type="AK",
        style="FC",
        pathname=f"/2023-03-30/functions/{function_path}",
        req_body_type="json",
        body_type="json",
    )
    request = open_api_models.OpenApiRequest(
        body={"code": {"zipFile": zip2base64(path_list)}}
    )

    open_api_client.call_api(params, request, runtime)


def oss_list_all_keys() -> List[str]:
    keys = []
    list_result = oss_bucket.list_objects(max_keys=1000)
    keys.extend([obj.key for obj in list_result.object_list])
    while list_result.is_truncated:
        list_result = oss_bucket.list_objects(
            marker=list_result.next_marker, max_keys=1000
        )
        keys.extend([obj.key for obj in list_result.object_list])
    return keys


def oss_upload(bucket_key: str, data: Union[bytes, Path]) -> None:
    if isinstance(data, Path):
        result = oss_bucket.put_object(bucket_key, data.read_bytes())
    else:
        result = oss_bucket.put_object(bucket_key, data)
    if result.status != 200:
        raise Exception(f"Failed to upload {bucket_key}")


def oss_batch_delete(key_list: List[str]) -> None:
    result = oss_bucket.batch_delete_objects(key_list)
    if result.status != 200:
        raise Exception(f"Failed to delete {key_list}")
