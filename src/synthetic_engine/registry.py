"""Explicit domain registration; the only builtin composition boundary."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

from synthetic_engine.config import Config
from synthetic_engine.core import Domain


@dataclass(frozen=True)
class DomainDefinition:
    name: str
    version: str
    description: str
    spec: str
    factory: Callable[[Config], Domain]
    validator: Callable[[Path, dict], dict]
    event_table: str = "records"
    partition_key: str = "partition"

    def __post_init__(self):
        for value in (self.name, self.event_table, self.partition_key):
            if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
                raise ValueError("Domain IDs and layout names must be safe identifiers")
        if self.event_table in {"dimensions", "ground_truth", "summaries"}:
            raise ValueError("Event table collides with a reserved output directory")


_domains: dict[str, DomainDefinition] = {}
_legacy: dict[str, Callable[[dict], dict]] = {}
_loaded = False


def register(definition: DomainDefinition):
    if definition.name in _domains:
        raise ValueError(f"Domain already registered: {definition.name}")
    _domains[definition.name] = definition


def _load_builtins():
    global _loaded
    if not _loaded:
        from synthetic_engine.domains.banking import definition
        from synthetic_engine.domains.banking.config import migrate_legacy
        register(definition())
        _legacy["banking_aml"] = migrate_legacy
        _loaded = True


def get_domain(name: str):
    _load_builtins()
    if name not in _domains:
        raise ValueError(f"Unknown domain {name!r}; available: {', '.join(sorted(_domains))}")
    return _domains[name]


def list_domains():
    _load_builtins()
    return [dict(name=d.name, version=d.version, description=d.description, spec=d.spec) for d in _domains.values()]


def normalize_config(payload):
    _load_builtins()
    if not isinstance(payload, dict):
        raise ValueError("Configuration must be a JSON object")
    name = payload.get("domain")
    if not isinstance(name, str):
        raise ValueError("Configuration requires a domain identifier")
    return _legacy[name](payload) if name in _legacy else payload
