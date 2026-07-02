import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.config import settings
from app.storage.base import PlaybackAuth

CONTENT_TYPES = {".m3u8": "application/vnd.apple.mpegurl", ".ts": "video/mp2t",
                 ".jpg": "image/jpeg", ".mp4": "video/mp4"}


def _cf_b64(data: bytes) -> str:
    return base64.b64encode(data).decode().replace("+", "-").replace("=", "_").replace("/", "~")


class S3Storage:
    def __init__(self):
        self.s3 = boto3.client("s3", region_name=settings.aws_region)

    def publish(self, episode_id: str, local_dir: Path) -> str:
        prefix = f"hls/{episode_id}"
        for f in local_dir.iterdir():
            self.s3.upload_file(
                str(f), settings.s3_bucket, f"{prefix}/{f.name}",
                ExtraArgs={"ContentType": CONTENT_TYPES.get(f.suffix, "application/octet-stream")})
        return f"{prefix}/master.m3u8"

    def playback(self, hls_path: str) -> PlaybackAuth:
        resource = f"https://{settings.cloudfront_domain}/{hls_path.rsplit('/', 1)[0]}/*"
        expires = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
        policy = json.dumps({"Statement": [{"Resource": resource, "Condition": {
            "DateLessThan": {"AWS:EpochTime": expires}}}]}, separators=(",", ":"))
        key = serialization.load_pem_private_key(
            Path(settings.cloudfront_private_key_path).read_bytes(), password=None)
        signature = key.sign(policy.encode(), padding.PKCS1v15(), hashes.SHA1())
        return PlaybackAuth(
            url=f"https://{settings.cloudfront_domain}/{hls_path}",
            cookies={
                "CloudFront-Policy": _cf_b64(policy.encode()),
                "CloudFront-Signature": _cf_b64(signature),
                "CloudFront-Key-Pair-Id": settings.cloudfront_key_pair_id,
            })
