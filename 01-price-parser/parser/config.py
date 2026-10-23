import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_url: str = "https://books.toscrape.com/"
    max_pages: int = 3
    request_delay: float = 0.5
    retries: int = 3
    output_dir: str = "output"
    db_path: str = "output/prices.db"
    user_agent: str = "Mozilla/5.0 (compatible; portfolio-price-parser/1.0)"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            base_url=os.getenv("BASE_URL", cls.base_url),
            max_pages=int(os.getenv("MAX_PAGES", cls.max_pages)),
            request_delay=float(os.getenv("REQUEST_DELAY", cls.request_delay)),
            retries=int(os.getenv("RETRIES", cls.retries)),
            output_dir=os.getenv("OUTPUT_DIR", cls.output_dir),
            db_path=os.getenv("DB_PATH", cls.db_path),
        )
