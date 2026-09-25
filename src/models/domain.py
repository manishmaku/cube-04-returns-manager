"""Domain enums and core types for the Returns Manager."""

from enum import Enum


class Verdict(str, Enum):
    """Three-value check verdict. UNCERTAIN is a first-class citizen (RULES.md §2.4)."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class PartStatus(str, Enum):
    """Status of an individual expected component or accessory."""
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    NOT_OBSERVED = "NOT_OBSERVED"


class ObservedState(str, Enum):
    """Visual physical observation from returned package inspection."""
    FACTORY_SEALED = "factory_sealed"
    OPENED_UNUSED = "opened_unused"
    SIGNS_OF_USE = "signs_of_use"
    DAMAGED = "damaged"
    EMPTY_BOX = "empty_box"
    UNCERTAIN = "uncertain"


class AmazonCondition(str, Enum):
    """Amazon's official published condition scale."""
    NEW = "New"
    LIKE_NEW = "Like New"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    UNACCEPTABLE = "Unacceptable"
    UNCERTAIN = "UNCERTAIN"


class Disposition(str, Enum):
    """Deterministic return disposition recommendations."""
    RESTOCK = "restock"
    REFURBISH = "refurbish"
    LIQUIDATE = "liquidate"
    DISPOSE = "dispose"
    PENDING_REVIEW = "pending_review"


class RecordStatus(str, Enum):
    """Status of an evidence record."""
    COMPLETED = "completed"
    PENDING = "pending"
    REVIEW = "review"
    FAILED = "failed"
