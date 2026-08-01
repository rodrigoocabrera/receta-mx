from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "data" / "catalog" / "medications.demo.json"


def normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.upper().strip().split())


@dataclass(frozen=True)
class CatalogMetadata:
    catalog_id: str
    version: str
    status: str
    authoritative: bool
    source_name: str
    source_url: str
    published_at: str
    valid_from: str
    jurisdiction: str = "MX"


class MedicationCatalog:
    """Versioned medication terminology provider.

    The bundled alpha catalog is synthetic and non-authoritative. The provider
    boundary is intentional: production deployments can replace the JSON file
    with a signed Compendio/COFEPRIS feed without changing prescription logic.
    """

    def __init__(self, metadata: CatalogMetadata, items: list[dict[str, Any]]) -> None:
        self.metadata = metadata
        self.items = items
        self._by_code = {normalize_search(str(item["code"])): item for item in items}

    @classmethod
    def from_json(cls, path: str | Path = DEFAULT_CATALOG_PATH) -> "MedicationCatalog":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        metadata = CatalogMetadata(**payload["metadata"])
        return cls(metadata, payload["items"])

    def get(self, code: str) -> dict[str, Any] | None:
        return self._by_code.get(normalize_search(code))

    def search(
        self,
        query: str = "",
        *,
        sale_fraction: str | None = None,
        controlled_group: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized = normalize_search(query)
        tokens = normalized.split()
        results: list[tuple[int, dict[str, Any]]] = []
        for item in self.items:
            if sale_fraction and item.get("sale_fraction") != sale_fraction:
                continue
            if controlled_group and item.get("controlled_group") != controlled_group:
                continue
            haystack = normalize_search(
                " ".join(
                    str(item.get(key, ""))
                    for key in (
                        "code",
                        "generic_name",
                        "form",
                        "strength",
                        "route",
                        "presentation",
                        "atc_code",
                    )
                )
            )
            if tokens and not all(token in haystack for token in tokens):
                continue
            score = 0
            if normalized and normalize_search(item.get("generic_name", "")) == normalized:
                score += 100
            if normalized and normalize_search(item.get("code", "")) == normalized:
                score += 120
            if normalized and haystack.startswith(normalized):
                score += 30
            results.append((score, item))
        results.sort(key=lambda pair: (-pair[0], pair[1]["generic_name"], pair[1]["code"]))
        return [dict(item) for _, item in results[: max(1, min(limit, 100))]]

    def validate_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        code = item.get("code")
        if not code:
            return None
        catalog_item = self.get(str(code))
        if not catalog_item:
            return None
        checks = {
            "generic_name": normalize_search,
            "sale_fraction": normalize_search,
            "controlled_group": normalize_search,
        }
        for field, normalizer in checks.items():
            supplied = item.get(field)
            expected = catalog_item.get(field)
            if supplied and expected and normalizer(str(supplied)) != normalizer(str(expected)):
                raise ValueError(f"El campo {field} no coincide con el catálogo para {code}.")
        return dict(catalog_item)


CATALOG = MedicationCatalog.from_json()
CATALOG_VERSION = CATALOG.metadata.version
DEMO_CATALOG = CATALOG.items
