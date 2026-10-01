"""Conservative deterministic mapping from observed visual state to Amazon's published condition scale."""

from src.models.domain import AmazonCondition, ObservedState, Verdict
from src.vision.schemas import ConditionObservation


def map_condition(condition_obs: ConditionObservation) -> tuple[AmazonCondition, Verdict, float, str]:
    """Map observed physical state to Amazon's published condition scale.

    Returns:
        tuple[AmazonCondition, Verdict, float, str]:
            (amazon_condition, condition_verdict, confidence, rule_rationale)
    """
    state = condition_obs.observed_state
    confidence = condition_obs.confidence
    detail_lower = condition_obs.detail.lower()

    # Rule 1: Low confidence or explicit uncertainty -> UNCERTAIN
    if state == ObservedState.UNCERTAIN or confidence < 0.5:
        return (
            AmazonCondition.UNCERTAIN,
            Verdict.UNCERTAIN,
            confidence,
            "Visual evidence is ambiguous or confidence is below threshold; requiring operator review.",
        )

    # Rule 2: Factory sealed packaging
    if state == ObservedState.FACTORY_SEALED:
        return (
            AmazonCondition.NEW,
            Verdict.PASS,
            confidence,
            "Factory shrink-wrap / manufacturer seal intact. Graded New on Amazon scale.",
        )

    # Rule 3: Opened but pristine and unused
    if state == ObservedState.OPENED_UNUSED:
        return (
            AmazonCondition.LIKE_NEW,
            Verdict.PASS,
            confidence,
            "Package opened but merchandise appears pristine and completely unused with original packaging. Graded Like New.",
        )

    # Rule 4: Signs of physical use / wear
    if state == ObservedState.SIGNS_OF_USE:
        # Check for minor vs moderate cosmetic wear
        if any(w in detail_lower for w in ("heavy", "deep", "significant", "severe")):
            return (
                AmazonCondition.ACCEPTABLE,
                Verdict.PASS,
                confidence,
                "Noticeable wear and significant cosmetic imperfections observed; functional testing unverified visually. Graded Acceptable.",
            )
        elif any(w in detail_lower for w in ("minor", "light", "scuff", "slight")):
            return (
                AmazonCondition.VERY_GOOD,
                Verdict.PASS,
                confidence,
                "Minor cosmetic blemishes or light handling marks observed; otherwise clean. Graded Very Good.",
            )
        else:
            return (
                AmazonCondition.GOOD,
                Verdict.PASS,
                confidence,
                "Moderate signs of prior handling or minor wear observed. Graded Good.",
            )

    # Rule 5: Damaged
    if state == ObservedState.DAMAGED:
        # Check if structural / severe or minor cosmetic damage
        if any(w in detail_lower for w in ("crack", "broken", "shattered", "structural", "heavy", "severe", "dented")):
            return (
                AmazonCondition.UNACCEPTABLE,
                Verdict.FAIL,
                confidence,
                "Physical structural damage observed. Graded Unacceptable on Amazon scale.",
            )
        return (
            AmazonCondition.ACCEPTABLE,
            Verdict.PASS,
            confidence,
            "Cosmetic damage observed; structural integrity intact. Graded Acceptable.",
        )

    # Rule 6: Empty box / no item
    if state == ObservedState.EMPTY_BOX:
        return (
            AmazonCondition.UNACCEPTABLE,
            Verdict.FAIL,
            confidence,
            "Package is empty; no product present inside parcel. Graded Unacceptable.",
        )

    # Fallback
    return (
        AmazonCondition.UNCERTAIN,
        Verdict.UNCERTAIN,
        confidence,
        "Observed physical state could not be deterministically classified; human review required.",
    )
