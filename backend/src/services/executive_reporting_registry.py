from typing import Set


class ExecutiveReportingRegistry:
    REPORT_TYPES = {
        "BOARD_REPORT",
        "EXECUTIVE_SUMMARY",
        "RISK_REVIEW",
        "QUARTERLY_REVIEW",
        "MONTHLY_REVIEW",
    }

    @classmethod
    def get_report_types(cls) -> Set[str]:
        """Retrieve all supported executive report types."""
        return cls.REPORT_TYPES

    @classmethod
    def is_valid_type(cls, report_type: str) -> bool:
        """Validate if a report type is supported."""
        return str(report_type).strip() in cls.REPORT_TYPES
