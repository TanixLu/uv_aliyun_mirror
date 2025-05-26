import json
import hashlib
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from aliyun_utils import oss_list_all_keys, oss_upload, oss_batch_delete


python_prefix = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
)
pypy_prefix = "https://downloads.python.org/pypy/"


def get_all_download_url_checksum_tuples() -> List[Tuple[str, str]]:
    download_metadata_url = "https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-python/download-metadata.json"
    resp = requests.get(download_metadata_url)
    resp.raise_for_status()
    download_metadata: dict = json.loads(resp.text)
    return [(v["url"], v["sha256"]) for v in download_metadata.values()]


def is_url_need_mirror(url: str) -> bool:
    return "debug" not in url and (
        url.startswith(python_prefix) or url.startswith(pypy_prefix)
    )


def url_unquote(s: str) -> str:
    return requests.utils.unquote(s)


def url2key(url: str) -> str:
    if url.startswith(python_prefix):
        return url_unquote(url[len(python_prefix) :])
    elif url.startswith(pypy_prefix):
        return url_unquote(url[len(pypy_prefix) :])
    raise Exception(f"Unknown url: {url}")


def calc_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_one_url_checksum_tuple_to_oss(url_checksum_tuple: Tuple[str, str]) -> str:
    url, checksum = url_checksum_tuple
    key = url2key(url)
    resp = requests.get(url)
    resp.raise_for_status()
    downloaded_checksum = calc_checksum(resp.content)
    if checksum is not None and downloaded_checksum != checksum:
        raise Exception(f"sha256 mismatch: {downloaded_checksum} != {checksum}")
    oss_upload(key, resp.content)
    return f"{url} uploaded to {key}"


def main() -> None:
    download_url_checksum_tuples = get_all_download_url_checksum_tuples()
    print(f"{len(download_url_checksum_tuples)=}")

    need_mirror_url_checksum_tuples = [
        t for t in download_url_checksum_tuples if is_url_need_mirror(t[0])
    ]
    need_mirror_keys_set = set([url2key(t[0]) for t in need_mirror_url_checksum_tuples])
    print(f"{len(need_mirror_url_checksum_tuples)=}")

    oss_keys = oss_list_all_keys()
    print(f"{len(oss_keys)=}")

    not_exists_url_checksum_tuples = [
        t for t in need_mirror_url_checksum_tuples if url2key(t[0]) not in oss_keys
    ]
    print(f"{len(not_exists_url_checksum_tuples)=}")

    outdated_keys = [k for k in oss_keys if k not in need_mirror_keys_set]
    print(f"{len(outdated_keys)=}")

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [
            executor.submit(upload_one_url_checksum_tuple_to_oss, t)
            for t in not_exists_url_checksum_tuples
        ]
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                print(f"Error: {e}")

    if outdated_keys:
        try:
            oss_batch_delete(outdated_keys)
            print("delete all outdated python")
        except Exception as e:
            print(f"Error: {e}")

    print("Done")


if __name__ == "__main__":
    main()
