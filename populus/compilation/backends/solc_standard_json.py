import pprint

from eth_utils import (
    add_0x_prefix,
    to_dict,
)

from solc import (
    compile_standard,
)
from solc.exceptions import (
    ContractsNotFound,
)

from populus.utils.compile import (
    load_json_if_string,
    normalize_contract_metadata,
)

from .base import (
    BaseCompilerBackend,
)


@to_dict
def build_standard_input_sources(source_file_paths):
    for file_path in source_file_paths:
        with open(file_path) as source_file:
            yield file_path, {'content': source_file.read()}


@to_dict
def normalize_standard_json_contract_data(contract_data):
    if 'metadata' in contract_data:
        yield 'metadata', normalize_contract_metadata(contract_data['metadata'])
    if 'evm' in contract_data:
        evm_data = contract_data['evm']
        if 'bytecode' in evm_data:
            yield 'bytecode', add_0x_prefix(evm_data['bytecode'].get('object', ''))
            if 'linkReferences' in evm_data['bytecode']:
                yield 'linkrefs', evm_data['bytecode']['linkReferences']
        if 'deployedBytecode' in evm_data:
            yield 'bytecode_runtime', add_0x_prefix(evm_data['deployedBytecode'].get('object', ''))
            if 'linkReferences' in evm_data['deployedBytecode']:
                yield 'linkrefs_runtime', evm_data['deployedBytecode']['linkReferences']
    if 'abi' in contract_data:
        yield 'abi', load_json_if_string(contract_data['abi'])
    if 'userdoc' in contract_data:
        yield 'userdoc', load_json_if_string(contract_data['userdoc'])
    if 'devdoc' in contract_data:
        yield 'devdoc', load_json_if_string(contract_data['devdoc'])


@to_dict
def build_compiled_contracts(compilation_result):
    for path, file_contracts in compilation_result['contracts'].items():
        for contract_name, raw_contract_data in file_contracts.items():
            contract_data = normalize_standard_json_contract_data(raw_contract_data)
            yield (
                (path, contract_name),
                contract_data,
            )


class SolcStandardJSONBackend(BaseCompilerBackend):
    def get_compiled_contracts(self, source_file_paths, import_remappings):
        self.logger.debug("Import remappings: %s", import_remappings)
        self.logger.debug("Compiler Settings: %s", pprint.pformat(self.compiler_settings))

        if 'remappings' in self.compiler_settings and import_remappings is not None:
            self.logger.warn("Import remappings setting will by overridden by backend settings")

        sources = build_standard_input_sources(source_file_paths)

        std_input = {
            'language': 'Solidity',
            'sources': sources,
            'settings': {
                'remappings': import_remappings
            }
        }
        std_input['settings'].update(self.compiler_settings)

        try:
            compilation_result = compile_standard(std_input)
        except ContractsNotFound:
            return {}

        compiled_contracts = build_compiled_contracts(compilation_result)
        return compiled_contracts
