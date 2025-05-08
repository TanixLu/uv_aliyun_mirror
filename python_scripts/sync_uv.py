import os
import hashlib
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from aliyun_utils import oss_list_all_keys, oss_upload


github_token = os.environ.get("GITHUB_TOKEN")
if github_token:
    github_api_headers = {"Authorization": f"Bearer {github_token}"}
else:
    github_api_headers = None


def is_key_need_mirror(key: str) -> bool:
    return key.startswith("uv-") and not key.endswith(".sha256")


def get_uv_latest_release_key_url_tuples() -> List[Tuple[str, str]]:
    url = "https://api.github.com/repos/astral-sh/uv/releases/latest"
    resp = requests.get(url, headers=github_api_headers)
    resp.raise_for_status()
    release: dict = resp.json()
    assets = release["assets"]
    return [(asset["name"], asset["browser_download_url"]) for asset in assets]


def url_unquote(s: str) -> str:
    return requests.utils.unquote(s)


def calc_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_one_key_url_tuple_to_oss(key_url_tuple: Tuple[str, str]) -> str:
    key, url = key_url_tuple
    checksum_url = url + ".sha256"

    checksum_resp = requests.get(checksum_url)
    if checksum_resp.status_code == 404:
        checksum = None
    else:
        checksum_resp.raise_for_status()
        checksum = checksum_resp.text.split()[0]

    resp = requests.get(url)
    resp.raise_for_status()

    downloaded_checksum = calc_checksum(resp.content)
    if checksum is not None and downloaded_checksum != checksum:
        raise Exception(f"sha256 mismatch: {downloaded_checksum} != {checksum}")
    oss_upload(key, resp.content)
    return f"{url} uploaded to {key}"


def main() -> None:
    key_url_tuples = get_uv_latest_release_key_url_tuples()
    print(f"{len(key_url_tuples)=}")

    need_mirror_key_url_tuples = [
        (key, url) for key, url in key_url_tuples if is_key_need_mirror(key)
    ]
    print(f"{len(need_mirror_key_url_tuples)=}")

    oss_keys = oss_list_all_keys()
    print(f"{len(oss_keys)=}")

    oss_uv_keys = [key for key in oss_keys if is_key_need_mirror(key)]
    print(f"{len(oss_uv_keys)=}")

    not_exists_url_checksum_tuples = [
        (key, url) for key, url in need_mirror_key_url_tuples if key not in oss_uv_keys
    ]
    print(f"{len(not_exists_url_checksum_tuples)=}")

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [
            executor.submit(upload_one_key_url_tuple_to_oss, t)
            for t in not_exists_url_checksum_tuples
        ]
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                print(f"Error: {e}")

    print("Done")


if __name__ == "__main__":
    main()
