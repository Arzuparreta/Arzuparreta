import asyncio
import logging

from logpilot.settings import get_settings
from logpilot.main import run_services


def main() -> None:
    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level.upper(), logging.INFO))
    asyncio.run(run_services())


if __name__ == "__main__":
    main()
