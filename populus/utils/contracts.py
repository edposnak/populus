import collections
import itertools
import json
import re

from eth_utils import (
    is_string,
    remove_0x_prefix,
)

from .filesystem import (
    is_under_path,
)
from .linking import (
    find_link_references,
    convert_linkrefs_from_standard_json,
)
from .mappings import (
    get_nested_key,
)
from .string import (
    normalize_class_name,
)


class ContractMapping(collections.Mapping):
    """
    Container for compiled
    """
    def __init__(self, compiled_contracts=None):
        if compiled_contracts is None:
            compiled_contracts = {}

        for contract_key in compiled_contracts.keys():
            if not isinstance(contract_key, tuple):
                raise ValueError("Invalid key: {0}".format(contract_key))
        self.compiled_contracts = compiled_contracts

    def to_dict(self):
        """
        Convert this to a normal dictionary.
        """
        return {':'.join(k): v for k, v in self.compiled_contracts.items()}

    @classmethod
    def from_dict(cls, _dict):
        """
        Create an instance from a dictionary.
        """
        compiled_contracts = {}

        for k, v in _dict.items():
            if isinstance(k, tuple):
                path, sym = k
            else:
                path, _, sym = k.rpartition(':')
            compiled_contracts[(path, sym)] = v

        return cls(compiled_contracts)

    def normalize_key(self, key, return_on_no_match=False):
        """
        TODO
        """
        if isinstance(key, list):
            key = tuple(key)

        if key in self.compiled_contracts:
            return key

        if isinstance(key, str):
            kpath, _, ksym = key.rpartition(':')
        else:
            kpath, ksym = key

        key_matches = [
            (path, sym) for (path, sym) in self.compiled_contracts.keys()
            if (not kpath or not path or kpath == path) and sym == ksym
        ]

        if len(key_matches) == 0:
            if return_on_no_match:
                if isinstance(key, str):
                    path, _, sym = key.rpartition(':')
                    return (path, sym)
                return key
            raise KeyError('No matches found for index {}'.format(key))

        if len(key_matches) > 1:
            raise KeyError('Multiple matches found for index {}: {}'.format(key, key_matches))

        return key_matches[0]

    #
    # Mapping API
    #
    def __getitem__(self, key):
        return self.compiled_contracts[self.normalize_key(key)]

    def __setitem__(self, key, value):
        self.compiled_contracts[self.normalize_key(key, return_on_no_match=True)] = value

    def __contains__(self, key):
        return self.normalize_key(key, return_on_no_match=True) in self.compiled_contracts

    def __len__(self):
        return len(self.compiled_contracts)

    def __delitem__(self, key):
        del self.compiled_contracts[self.normalize_key(key)]

    def __iter__(self):
        return iter(self.compiled_contracts)

    def get(self, key, default=None):
        return self.compiled_contracts.get(self.normalize_key(key, return_on_no_match=True), default)

    def items(self):
        return self.compiled_contracts.items()

    def keys(self):
        return self.compiled_contracts.keys()

    def values(self):
        return self.compiled_contracts.values()


class ContractMappingEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ContractMapping):
            return obj.to_dict()
        return json.JSONEncoder.default(self, obj)


def get_contract_source_file_path(contract_data):
    compilation_target = get_nested_key(contract_data, 'metadata.settings.compilationTarget')
    assert len(compilation_target) == 1
    return tuple(compilation_target.keys())[0]


def is_project_contract(contracts_source_dir, contract_data):
    try:
        contract_source_file_path = get_contract_source_file_path(contract_data)
    except KeyError:
        # TODO: abstract contracts don't have a metadata value.  How do we handle this....
        return False
    return is_under_path(contracts_source_dir, contract_source_file_path)


def is_test_contract(tests_dir, contract_data):
    try:
        contract_source_file_path = get_contract_source_file_path(contract_data)
    except KeyError:
        # TODO: abstract contracts don't have a metadata value.  How do we handle this....
        return False
    return is_under_path(tests_dir, contract_source_file_path)


def package_contracts(contract_factories):
    _dict = {
        '__len__': lambda s: len(contract_factories),
        '__iter__': lambda s: iter(contract_factories.items()),
        '__contains__': lambda s, k: contract_factories.__contains__(k),
        '__getitem__': lambda s, k: contract_factories.__getitem__(k),
        '__setitem__': lambda s, k, v: contract_factories.__setitem__(k, v),
        'keys': lambda s: contract_factories.keys(),
        'values': lambda s: contract_factories.values(),
    }
    _dict.update(contract_factories)

    return type('contracts', (object,), _dict)()


CONTRACT_FACTORY_FIELDS = {
    'abi',
    'asm',
    'ast',
    'bytecode',
    'bytecode_runtime',
    'clone_bin',
    'dev_doc',
    'interface',
    'metadata',
    'opcodes',
    'src_map',
    'src_map_runtime',
    'user_doc',
}


def create_contract_factory(web3, contract_name, contract_data):
    factory_kwargs = {
        key: contract_data[key]
        for key
        in CONTRACT_FACTORY_FIELDS
        if key in contract_data
    }
    return web3.eth.contract(
        contract_name=normalize_class_name(contract_name),
        **factory_kwargs
    )


def construct_contract_factories(web3, contracts):
    contract_classes = {}
    for (_, contract_name), contract_data in contracts.items():
        if contract_name in contract_classes:
            raise ValueError('Name `{}` appears multiple times in {}'.format(contract_name, contracts))
        contract_classes[contract_name] = create_contract_factory(web3, contract_name, contract_data)

    return package_contracts(contract_classes)


def get_link_references(contract_data, ref_candidates, is_runtime=False):
    bytecode_key = 'bytecode'
    linkrefs_key = 'linkrefs'

    if is_runtime:
        bytecode_key += '_runtime'
        linkrefs_key += '_runtime'

    if linkrefs_key in contract_data:
        return convert_linkrefs_from_standard_json(contract_data[linkrefs_key])

    metadata_sources = (contract_data.get('metadata') or {}).get('sources')
    if metadata_sources is not None:
        ref_candidates = tuple(
            (path, name) for path, name in ref_candidates
            if not path or path in metadata_sources.keys()
        )

    return find_link_references(contract_data[bytecode_key], ref_candidates)


def get_shallow_dependency_graph(contracts):
    """
    Given a dictionary or mapping of compiled contract data, this returns a *shallow*
    dependency graph of each contracts explicit link dependencies.
    """
    use_primitive = isinstance(contracts, dict)

    if use_primitive:
        contracts = ContractMapping.from_dict(contracts)

    link_dependencies = {
        contract_key: set(ref.full_name for ref in get_link_references(
            contract_data,
            contracts.keys(),
        ))
        for contract_key, contract_data
        in contracts.items()
        if is_string(contract_data.get('bytecode'))
    }

    if use_primitive:
        # if all path components are empty, then return with string keys
        if all(not path and all(not dpath for (dpath, dsym) in depset)
               for (path, sym), depset in link_dependencies.items()):
            return {
                sym: set(dsym for (_, dsym) in depset)
                for (_, sym), depset in link_dependencies.items()
            }

        return link_dependencies

    return ContractMapping(link_dependencies)


def get_recursive_contract_dependencies(contract_name, dependency_graph):
    """
    Recursive computation of the linker dependencies for a specific contract
    within a contract dependency graph.
    """
    direct_dependencies = dependency_graph.get(contract_name, set())
    sub_dependencies = itertools.chain.from_iterable((
        get_recursive_contract_dependencies(dep, dependency_graph)
        for dep in direct_dependencies
    ))
    return set(itertools.chain(direct_dependencies, sub_dependencies))


CONTRACT_NAME_REGEX = '^[_a-zA-Z][_a-zA-Z0-9]*$'


def is_contract_name(value):
    return bool(re.match(CONTRACT_NAME_REGEX, value))


EMPTY_BYTECODE_VALUES = {None, "0x"}


SWARM_HASH_PREFIX = "a165627a7a72305820"
SWARM_HASH_SUFFIX = "0029"
EMBEDDED_SWARM_HASH_REGEX = (
    SWARM_HASH_PREFIX +
    "[0-9a-zA-Z]{64}" +
    SWARM_HASH_SUFFIX +
    "$"
)

SWARM_HASH_REPLACEMENT = (
    SWARM_HASH_PREFIX +
    "<" +
    "-" * 20 +
    "swarm-hash-placeholder" +
    "-" * 20 +
    ">" +
    SWARM_HASH_SUFFIX
)


def compare_bytecode(left, right):
    unprefixed_left = remove_0x_prefix(left)
    unprefixed_right = remove_0x_prefix(right)

    norm_left = re.sub(EMBEDDED_SWARM_HASH_REGEX, SWARM_HASH_REPLACEMENT, unprefixed_left)
    norm_right = re.sub(EMBEDDED_SWARM_HASH_REGEX, SWARM_HASH_REPLACEMENT, unprefixed_right)

    if len(norm_left) != len(unprefixed_left) or len(norm_right) != len(unprefixed_right):
        raise ValueError(
            "Invariant.  Normalized bytecodes are not the correct lengths:" +
            "\n- left  (original)  :" +
            left, +
            "\n- left  (unprefixed):" +
            unprefixed_left +
            "\n- left  (normalized):" +
            norm_left +
            "\n- right (original)  :" +
            right +
            "\n- right (unprefixed):" +
            unprefixed_right +
            "\n- right (normalized):" +
            norm_right
        )

    return norm_left == norm_right


def verify_contract_bytecode(web3, expected_bytecode, address):
    """
    TODO: write tests for this.
    """
    from populus.contracts.exceptions import BytecodeMismatch

    # Check that the contract has bytecode
    if expected_bytecode in EMPTY_BYTECODE_VALUES:
        raise ValueError(
            "Contract instances which contain an address cannot have empty "
            "runtime bytecode"
        )

    chain_bytecode = web3.eth.getCode(address)

    if chain_bytecode in EMPTY_BYTECODE_VALUES:
        raise BytecodeMismatch(
            "No bytecode found at address: {0}".format(address)
        )
    elif not compare_bytecode(chain_bytecode, expected_bytecode):
        raise BytecodeMismatch(
            "Bytecode found at {0} does not match compiled bytecode:\n"
            " - chain_bytecode: {1}\n"
            " - compiled_bytecode: {2}".format(
                address,
                chain_bytecode,
                expected_bytecode,
            )
        )


def find_deploy_block_number(web3, address):
    chain_bytecode = web3.eth.getCode(address, "latest")
    if chain_bytecode in EMPTY_BYTECODE_VALUES:
        raise NotImplementedError("Cannot find deploy transaction for address with empty code")

    left = 0
    right = web3.eth.blockNumber

    while left + 1 < right:
        middle = (left + right) // 2
        # This only works if the node was not fast synced for the provided
        # `block_identifier`.
        try:
            middle_code = web3.eth.getCode(address, block_identifier=middle)
        except ValueError as err:
            if 'Missing trie node' in str(err):
                left = middle
                continue
            raise

        if middle_code in EMPTY_BYTECODE_VALUES:
            left = middle
        else:
            right = middle

    code_at_right = web3.eth.getCode(address, block_identifier=right)
    if code_at_right in EMPTY_BYTECODE_VALUES:
        raise ValueError(
            "Something went wrong with the binary search to find the deploy block"
        )
    code_at_previous_block = web3.eth.getCode(address, block_identifier=right - 1)
    if code_at_previous_block not in EMPTY_BYTECODE_VALUES:
        raise ValueError(
            "Something went wrong with the binary search to find the deploy block"
        )
    return right
