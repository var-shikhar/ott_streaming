from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    direct_database_url: str = ""  # Neon direct URL for Alembic; falls back to database_url

    jwt_secret: str = "dev-only-secret-change-me-in-production-0000"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # use "none" (+ cookie_secure=true) when frontend and API are on different domains

    frontend_origin: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    storage_mode: str = "local"  # "local" | "s3"
    media_root: str = "media"
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    cloudfront_domain: str = ""
    cloudfront_key_pair_id: str = ""
    cloudfront_private_key_path: str = ""
    cdn_cookie_domain: str = ""  # e.g. ".example.com" so API-set cookies reach the CDN

    imagekit_public_key: str = ""
    imagekit_private_key: str = ""
    imagekit_url_endpoint: str = ""

    razorpay_key_id: str = "rzp_test_dummy"
    razorpay_key_secret: str = "dummy"
    razorpay_webhook_secret: str = "whsec_dummy"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("database_url", "direct_database_url")
    @classmethod
    def _force_psycopg_driver(cls, v: str) -> str:
        # Neon/Render hand out plain postgres(ql):// URLs; we ship psycopg v3,
        # so rewrite the scheme or SQLAlchemy tries to import psycopg2.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v.removeprefix("postgresql://")
        return v


settings = Settings()
