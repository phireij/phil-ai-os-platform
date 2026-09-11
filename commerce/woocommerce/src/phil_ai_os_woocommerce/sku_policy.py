from __future__ import annotations

from dataclasses import dataclass
import re


SKU_RE = re.compile(r"^RCD-[A-Z0-9]{2,8}-[A-Z0-9]{2,6}(?:-[A-Z0-9]{1,8})?$")


class SkuPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RubySku:
    brand: str
    product_code: str
    form_code: str
    option_code: str | None = None

    def __post_init__(self) -> None:
        if self.brand != "RCD":
            raise SkuPolicyError("brand prefix must be RCD")
        for label, value, minimum, maximum in (
            ("product_code", self.product_code, 2, 8),
            ("form_code", self.form_code, 2, 6),
        ):
            if not (minimum <= len(value) <= maximum) or not value.isalnum() or value.upper() != value:
                raise SkuPolicyError(f"invalid {label}")
        if self.option_code is not None:
            value = self.option_code
            if not (1 <= len(value) <= 8) or not value.isalnum() or value.upper() != value:
                raise SkuPolicyError("invalid option_code")

    def render(self) -> str:
        parts = [self.brand, self.product_code, self.form_code]
        if self.option_code is not None:
            parts.append(self.option_code)
        return "-".join(parts)


def parse_ruby_sku(value: str) -> RubySku:
    normalized = str(value or "").strip()
    if not SKU_RE.fullmatch(normalized):
        raise SkuPolicyError("SKU must follow RCD-PRODUCT-FORM[-OPTION]")
    parts = normalized.split("-")
    return RubySku(
        brand=parts[0],
        product_code=parts[1],
        form_code=parts[2],
        option_code=parts[3] if len(parts) == 4 else None,
    )


def build_ruby_sku(product_code: str, form_code: str, option_code: str | int | None = None) -> str:
    sku = RubySku(
        brand="RCD",
        product_code=str(product_code).strip().upper(),
        form_code=str(form_code).strip().upper(),
        option_code=None if option_code is None else str(option_code).strip().upper(),
    )
    return sku.render()
