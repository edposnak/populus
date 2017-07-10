from __future__ import absolute_import

import pprint

from semantic_version import Spec

from eth_utils import (
    add_0x_prefix,
    to_dict,
)

from solc import (
    compile_files,
    get_solc_version,
)
from solc.exceptions import (
    ContractsNotFound,
)

from populus.utils.compile import (
    load_json_if_string,
    normalize_contract_metadata,
)
from populus.utils.mappings import (
    get_nested_key,
)

from .base import (
    BaseCompilerBackend,
)


if get_solc_version() in Spec('<0.4.9'):
    def _get_combined_key(key_from_compiler, contract_data):
        metadata = contract_data.get('metadata')
        if metadata is not None:
            targ = metadata.get('settings', {}).get('compilationTarget')
            if targ is not None:
                if len(targ) != 1:
                    raise ValueError('Invalid compilationTarget {}'.format(targ))
                return next(':'.join(it) for it in targ.items())
        return key_from_compiler
else:
    def _get_combined_key(key_from_compiler, _):
        return key_from_compiler


def normalize_combined_json_contract_key(key_from_compiler, contract_data):
    if ':' not in key_from_compiler:
        try:
            compilation_target = get_nested_key(
                contract_data,
                'metadata.settings.compilationTarget',
            )
        except KeyError:
            pass
        else:
            if len(compilation_target) != 1:
                raise ValueError('Invalid compilationTarget {}'.format(targ))
            return next(it for it in compilation_target.items())
    path, _, name = key_from_compiler.rpartition(':')
    return path, name


@to_dict
def normalize_combined_json_contract_data(contract_data):
    if 'metadata' in contract_data:
        yield 'metadata', normalize_contract_metadata(contract_data['metadata'])
    if 'bin' in contract_data:
        yield 'bytecode', add_0x_prefix(contract_data['bin'])
    if 'bin-runtime' in contract_data:
        yield 'bytecode_runtime', add_0x_prefix(contract_data['bin-runtime'])
    if 'abi' in contract_data:
        yield 'abi', load_json_if_string(contract_data['abi'])
    if 'userdoc' in contract_data:
        yield 'userdoc', load_json_if_string(contract_data['userdoc'])
    if 'devdoc' in contract_data:
        yield 'devdoc', load_json_if_string(contract_data['devdoc'])


@to_dict
def normalize_compiled_contracts(compiled_contracts):
    for compiler_key, raw_contract_data in compiled_contracts.items():
        contract_data = normalize_combined_json_contract_data(raw_contract_data)
        contract_key = normalize_combined_json_contract_key(compiler_key, contract_data)
        yield contract_key, contract_data


class SolcCombinedJSONBackend(BaseCompilerBackend):
    def get_compiled_contract_data(self, source_file_paths, import_remappings):
        self.logger.debug("Import remappings: %s", import_remappings)
        self.logger.debug("Compiler Settings: %s", pprint.pformat(self.compiler_settings))

        if 'import_remappings' in self.compiler_settings and import_remappings is not None:
            self.logger.warn("Import remappings setting will be overridden by backend settings")

        try:
            compilation_result = compile_files(
                source_file_paths,
                import_remappings=import_remappings,
                **self.compiler_settings,
            )
        except ContractsNotFound:
            return {}

        compiled_contracts = normalize_compiled_contracts(compilation_result)
        return compiled_contracts
