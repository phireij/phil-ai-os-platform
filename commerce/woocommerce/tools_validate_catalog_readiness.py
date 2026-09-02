from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.catalog_readiness import evaluate_catalog_tax_readiness


def main() -> int:
    template_path = ROOT / "fixtures" / "production-catalog-intake.template.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    result = evaluate_catalog_tax_readiness(payload)

    # The Ruby-specific template now carries the reconciled 2026 exempt / tax-disabled
    # decision, while the production catalog itself intentionally remains pending.
    assert result.catalog_ready is False
    assert result.tax_decision_ready is True
    assert result.ready_for_preproduction_configuration is False
    assert result.mutation_authorized is False
    assert result.production_publish_authorized is False
    assert result.blockers
    assert "catalog approval is pending" in result.blockers
    assert "Yamato separate-charge treatment is pending" not in result.blockers
    assert "COD fee treatment is pending" not in result.blockers

    print(
        "PHIL_AI_OS_CATALOG_TAX_INTAKE_GATE_GREEN "
        f"catalog_ready=false tax_decision_ready=true blockers={len(result.blockers)} "
        "mutation_authorized=false production_publish_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
