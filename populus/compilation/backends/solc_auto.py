from __future__ import absolute_import

from semantic_version import Spec

from solc import (
    get_solc_version,
)

from .base import (
    BaseCompilerBackend,
)
from .solc_combined_json import (
    SolcCombinedJSONBackend,
)
from .solc_standard_json import (
    SolcStandardJSONBackend,
)


def get_solc_backend_class_for_version(solc_version):
    if solc_version in Spec('<0.4.9'):
        return SolcCombinedJSONBackend
    else:
        return SolcStandardJSONBackend


class SolcAutoBackend(BaseCompilerBackend):
    def __init__(self, settings):
        proxy_backend_class = get_solc_backend_class_for_version(get_solc_version())
        self.proxy_backend = proxy_backend_class(settings)

    @property
    def settings(self):
        return self.proxy_backend.settings

    def get_compiled_contracts(self, *args, **kwargs):
        return self.proxy_backend.get_compiled_contracts(*args, **kwargs)
