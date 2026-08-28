from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import CategoryRecord


class CategoryHierarchyError(ValueError):
    """Raised when a category hierarchy is ambiguous or internally invalid."""


@dataclass(frozen=True)
class CategoryPlanItem:
    category: CategoryRecord
    depth: int

    @property
    def key(self) -> str:
        return self.category.key

    @property
    def parent_key(self) -> str | None:
        return self.category.parent_key


def plan_category_hierarchy(categories: Iterable[CategoryRecord]) -> tuple[CategoryPlanItem, ...]:
    """Return deterministic parent-before-child category order.

    This function performs no WooCommerce calls. It only proves that the
    canonical hierarchy is safe to project later after parent remote IDs exist.
    """
    by_key: dict[str, CategoryRecord] = {}
    for category in categories:
        if category.key in by_key:
            raise CategoryHierarchyError(f"duplicate category key: {category.key}")
        by_key[category.key] = category

    for category in by_key.values():
        if category.parent_key is not None and category.parent_key not in by_key:
            raise CategoryHierarchyError(
                f"missing parent category for {category.key}: {category.parent_key}"
            )

    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[CategoryPlanItem] = []
    depth_by_key: dict[str, int] = {}

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in visiting:
            raise CategoryHierarchyError(f"category hierarchy cycle detected at: {key}")
        visiting.add(key)
        category = by_key[key]
        if category.parent_key is None:
            depth = 0
        else:
            visit(category.parent_key)
            depth = depth_by_key[category.parent_key] + 1
        visiting.remove(key)
        visited.add(key)
        depth_by_key[key] = depth
        ordered.append(CategoryPlanItem(category=category, depth=depth))

    for key in sorted(by_key):
        visit(key)

    return tuple(ordered)
