
import re


class DocumentTextNormalizer:

    FIELD_PATTERN = re.compile(
    r"^([A-Za-z][A-Za-z ]{0,60})"
    r"\s*[:\uFF1A]\s*(.*)$"
)

    @classmethod
    def normalize_line(cls, text: str) -> str:

        match = cls.FIELD_PATTERN.fullmatch(
            text.strip()
        )

        if match is None:
            return text

        label, value = match.groups()

        return f"{label.strip()}: {value}"

    @classmethod
    def normalize_lines(
        cls,
        lines: list[str],
    ) -> list[str]:

        return [
            cls.normalize_line(line)
            for line in lines
        ]
