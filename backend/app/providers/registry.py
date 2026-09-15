"""Maps an InsuranceProvider row's integration_mode to a live adapter
instance. Real adapters (BritamAdapter, LamiAdapter, ...) are registered
here - each currently raises NotImplementedError on every call until real
API documentation and credentials are supplied (see
docs/PROVIDER_LANDSCAPE.md). Nothing else in the codebase needs to change
when a real integration is built: only the adapter file itself.
"""

from app.models.provider import InsuranceProvider
from app.providers.apa_adapter import APAAdapter
from app.providers.base import InsuranceProviderAdapter
from app.providers.britam_adapter import BritamAdapter
from app.providers.cic_adapter import CICAdapter
from app.providers.icea_lion_adapter import ICEALionAdapter
from app.providers.jubilee_adapter import JubileeAdapter
from app.providers.lami_adapter import LamiAdapter
from app.providers.mock_aggregator import MockAggregatorProvider
from app.providers.mock_provider import MockProvider
from app.providers.mtek_adapter import MtekAdapter
from app.providers.old_mutual_adapter import OldMutualAdapter
from app.providers.turaco_adapter import TuracoAdapter

# Keyed by InsuranceProvider.name.lower() - matched against the seeded
# provider rows in app/db/seed.py. Every entry here is a real, named
# company from docs/PROVIDER_LANDSCAPE.md; none of them can serve a real
# quote yet (see each adapter's WHAT_IS_KNOWN), but the provider row exists
# so an admin can see integration status and progress it once real API
# access is granted.
_REAL_ADAPTERS: dict[str, type[InsuranceProviderAdapter]] = {
    "britam": BritamAdapter,
    "jubilee insurance": JubileeAdapter,
    "apa insurance": APAAdapter,
    "cic insurance group": CICAdapter,
    "icea lion": ICEALionAdapter,
    "old mutual kenya": OldMutualAdapter,
    "lami technologies": LamiAdapter,
    "mtek services": MtekAdapter,
    "turaco": TuracoAdapter,
}


def get_adapter(provider: InsuranceProvider) -> InsuranceProviderAdapter:
    key = provider.name.strip().lower()
    if provider.integration_mode == "mock" or key not in _REAL_ADAPTERS:
        if provider.provider_type == "aggregator":
            return MockAggregatorProvider(provider_id=str(provider.id), display_name=provider.name)
        return MockProvider(provider_id=str(provider.id), display_name=provider.name)

    adapter_cls = _REAL_ADAPTERS[key]
    return adapter_cls(provider_id=str(provider.id))
