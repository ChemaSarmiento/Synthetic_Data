"""Banking domain. AML is an optional scenario within this domain."""

from synthetic_engine.domains.banking.generator import BankingDomain


def definition():
    from synthetic_engine.domains.banking.validation import validate_banking
    from synthetic_engine.registry import DomainDefinition
    return DomainDefinition(
        name="banking", version="0.4.0",
        description="Banking entities and transactions; optional AML scenarios",
        spec="specs/domains/banking/spec.md",
        factory=BankingDomain, validator=validate_banking,
        event_table="transactions", partition_key="event_date",
    )
