"""
sanctions_loader.py — Free public-domain sanctions list loader for C6 AMLChecker.

Downloads and converts public-domain government sanctions lists to the JSON
format consumed by SanctionsScreener(lists_path=...).

Output JSON schema:
  {
    "OFAC": ["ENTITY NAME 1", "ENTITY NAME 2", ...],
    "UN":   [...],
    "EU":   [...]
  }

Sources (all public domain / open government data, no license fee):
  OFAC SDN: US Treasury, public domain
    https://sanctionslist.ofac.treas.gov/Home/SdnList (CSV)
  UN Consolidated: UN Security Council, public domain
    https://scsanctions.un.org/resources/xml/en/consolidated.xml
  EU CFSP: European External Action Service, CC0
    https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content

Usage (run from repo root, requires internet access):
  python -m lip.c6_aml_velocity.sanctions_loader \\
      --output lip/c6_aml_velocity/data/sanctions.json

  # Offline: validate existing snapshot
  python -m lip.c6_aml_velocity.sanctions_loader --validate \\
      --output lip/c6_aml_velocity/data/sanctions.json

IMPORTANT: This module makes HTTP calls ONLY when run as a CLI/update script.
           At runtime, SanctionsScreener loads the pre-built JSON from disk.
           The C6 production container is zero-outbound.
"""
import argparse
import csv
import io
import json
import logging
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public-domain source URLs
# ---------------------------------------------------------------------------

OFAC_SDN_CSV_URL = (
    "https://sanctionslist.ofac.treas.gov/Home/SdnList"
)
UN_XML_URL = (
    "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
)
EU_XML_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
)

_REQUEST_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_ofac_names(url: str = OFAC_SDN_CSV_URL) -> List[str]:
    """
    Download the OFAC SDN CSV and extract entity / individual names.

    The OFAC SDN CSV format (fixed, documented by US Treasury):
      col 0: ent_num
      col 1: SDN_Name  (last name / entity name — this is what we screen)
      col 2: SDN_Type  (individual | entity | vessel | aircraft)
      col 3: Program   (sanctions program, e.g. SDGT, IRAN)
      col 4: Title
      col 5: Call_Sign
      ...

    Returns:
        Deduplicated, uppercased list of screened names.
    """
    logger.info("Fetching OFAC SDN list from %s", url)
    names: List[str] = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LIP-SanctionsLoader/1.0"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        for row in reader:
            if len(row) < 2:
                continue
            name = row[1].strip()
            if name and name.upper() != "SDN_NAME":  # skip header
                names.append(name.upper())
    except Exception:
        logger.exception("Failed to fetch OFAC SDN list")
    return list(dict.fromkeys(names))  # preserve order, dedupe


def fetch_un_names(url: str = UN_XML_URL) -> List[str]:
    """
    Download and parse the UN Security Council Consolidated XML list.

    Extracts INDIVIDUAL/ENTITY <FIRST_NAME>, <SECOND_NAME>, <THIRD_NAME>,
    <FOURTH_NAME> and <NAME_ORIGINAL_SCRIPT> fields.

    Returns:
        Deduplicated, uppercased list of consolidated name strings.
    """
    logger.info("Fetching UN Consolidated List from %s", url)
    names: List[str] = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LIP-SanctionsLoader/1.0"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)

        def _text(el: Optional[ET.Element]) -> str:
            return (el.text or "").strip() if el is not None else ""

        for individual in root.iter("INDIVIDUAL"):
            parts = [
                _text(individual.find("FIRST_NAME")),
                _text(individual.find("SECOND_NAME")),
                _text(individual.find("THIRD_NAME")),
                _text(individual.find("FOURTH_NAME")),
            ]
            full = " ".join(p for p in parts if p)
            if full:
                names.append(full.upper())
            # Also add original script name if present
            orig = _text(individual.find("NAME_ORIGINAL_SCRIPT"))
            if orig:
                names.append(orig.upper())

        for entity in root.iter("ENTITY"):
            first = _text(entity.find("FIRST_NAME"))
            if first:
                names.append(first.upper())
            orig = _text(entity.find("NAME_ORIGINAL_SCRIPT"))
            if orig:
                names.append(orig.upper())

    except Exception:
        logger.exception("Failed to fetch UN Consolidated List")
    return list(dict.fromkeys(names))


def fetch_eu_names(url: str = EU_XML_URL) -> List[str]:
    """
    Download and parse the EU CFSP Consolidated Sanctions XML.

    Extracts nameAlias/@wholeName attributes from each sanctioned subject.

    Returns:
        Deduplicated, uppercased list of alias name strings.
    """
    logger.info("Fetching EU CFSP Consolidated List from %s", url)
    names: List[str] = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LIP-SanctionsLoader/1.0"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for alias in root.iter("nameAlias"):
            whole = alias.get("wholeName", "").strip()
            if whole:
                names.append(whole.upper())
    except Exception:
        logger.exception("Failed to fetch EU CFSP Consolidated List")
    return list(dict.fromkeys(names))


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_sanctions_json(
    ofac_names: List[str],
    un_names: List[str],
    eu_names: List[str],
    output_path: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Merge three name lists into the SanctionsScreener JSON schema.

    Args:
        ofac_names:  Names from OFAC SDN.
        un_names:    Names from UN Consolidated List.
        eu_names:    Names from EU CFSP List.
        output_path: If given, write the resulting JSON to this path.

    Returns:
        Dict with keys "OFAC", "UN", "EU" mapping to sorted name lists.
    """
    data: Dict[str, List[str]] = {
        "OFAC": sorted(set(ofac_names)),
        "UN":   sorted(set(un_names)),
        "EU":   sorted(set(eu_names)),
    }
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        total = sum(len(v) for v in data.values())
        logger.info(
            "Wrote %d entries (OFAC=%d UN=%d EU=%d) to %s",
            total,
            len(data["OFAC"]),
            len(data["UN"]),
            len(data["EU"]),
            output_path,
        )
    return data


def load_from_file(path: str) -> Dict[str, List[str]]:
    """Load and return an existing JSON snapshot without making network calls."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_snapshot(path: str) -> bool:
    """
    Validate that a sanctions.json snapshot has the expected structure.

    Returns:
        True if valid, False otherwise.
    """
    try:
        data = load_from_file(path)
        required_keys = {"OFAC", "UN", "EU"}
        if not required_keys.issubset(data.keys()):
            logger.error("Missing keys: %s", required_keys - set(data.keys()))
            return False
        for key in required_keys:
            if not isinstance(data[key], list):
                logger.error("%s is not a list", key)
                return False
        total = sum(len(data[k]) for k in required_keys)
        logger.info(
            "Snapshot valid: OFAC=%d UN=%d EU=%d (total=%d)",
            len(data["OFAC"]),
            len(data["UN"]),
            len(data["EU"]),
            total,
        )
        return True
    except Exception:
        logger.exception("Snapshot validation failed")
        return False


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Download and build LIP sanctions.json from free public lists."
    )
    parser.add_argument(
        "--output",
        default="lip/c6_aml_velocity/data/sanctions.json",
        help="Output path for the merged sanctions JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing snapshot at --output without downloading",
    )
    parser.add_argument(
        "--ofac-url", default=OFAC_SDN_CSV_URL, help="Override OFAC SDN CSV URL"
    )
    parser.add_argument(
        "--un-url", default=UN_XML_URL, help="Override UN XML URL"
    )
    parser.add_argument(
        "--eu-url", default=EU_XML_URL, help="Override EU XML URL"
    )
    args = parser.parse_args()

    if args.validate:
        ok = validate_snapshot(args.output)
        sys.exit(0 if ok else 1)

    ofac = fetch_ofac_names(args.ofac_url)
    un = fetch_un_names(args.un_url)
    eu = fetch_eu_names(args.eu_url)

    if not any([ofac, un, eu]):
        logger.error("All list fetches failed — no data to write")
        sys.exit(1)

    build_sanctions_json(ofac, un, eu, output_path=args.output)


if __name__ == "__main__":
    _cli()
