from pathlib import Path

from aliyun_utils import fc_upload

fc_upload(
    [Path("fc_server/target/x86_64-unknown-linux-musl/release/fc_server")],
    "uv_mirror_service",
    "uv_mirror_fc",
)
