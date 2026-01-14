#!pip install -U mostlyai python-dotenv
import os

from dotenv import load_dotenv
from mostlyai.sdk import MostlyAI


def get_mostly_client() -> MostlyAI:
    """Return a MostlyAI client using credentials from .env.

    Expects the following entries in the project's .env file:
      - MOSTLYAI_API_KEY
      - MOSTLYAI_BASE_URL (optional, defaults to https://app.mostly.ai)
    """

    # Load variables from .env in the project root
    load_dotenv()

    api_key = os.getenv("MOSTLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("MOSTLYAI_API_KEY is not set in the environment/.env file.")

    base_url = os.getenv("MOSTLYAI_BASE_URL", "https://app.mostly.ai")

    return MostlyAI(api_key=api_key, base_url=base_url)


if __name__ == "__main__":
    # Example usage when running this file directly.
    mostly = get_mostly_client()

    # train a generator
    g = mostly.train(
        data="https://github.com/mostly-ai/public-demo-data/raw/dev/census/census.csv.gz",
    )

    # probe for some samples
    mostly.probe(g, size=10)

    # generate a synthetic dataset
    sd = mostly.generate(g, size=2_000)

    # start using it
    sd.data()