"""CNA error types.

All rule violations raise RuleViolationError with the case number that was violated.
The UI layer catches these and displays the violated rule.
"""


class RuleViolationError(Exception):
    """Raised when a game action violates a specific rule case.

    Attributes:
        case_number: The rulebook case number violated (e.g., "8.12").
        message: Human-readable description of the violation.
    """

    def __init__(self, case_number: str, message: str):
        self.case_number = case_number
        self.message = message
        super().__init__(f"[{case_number}] {message}")
