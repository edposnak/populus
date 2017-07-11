from __future__ import absolute_import

import anyconfig

import jsonschema

import os
import json
import logging

from toolz.functoolz import (
    compose,
)
from toolz.dicttoolz import (
    assoc,
)

from eth_utils import (
    to_tuple,
    to_dict,
    is_string,
)

from populus import ASSETS_DIR
from populus.exceptions import (
    ValidationError,
)

from .contracts import (
    get_shallow_dependency_graph,
    get_recursive_contract_dependencies,
)
from .deploy import (
    compute_deploy_order,
)
from .filesystem import (
    recursive_find_files,
    ensure_file_exists,
)


DEFAULT_CONTRACTS_DIR = "./contracts/"


def get_contracts_source_dir(project_dir):
    contracts_source_dir = os.path.join(project_dir, DEFAULT_CONTRACTS_DIR)
    return os.path.abspath(contracts_source_dir)


BUILD_ASSET_DIR = "./build"


def get_build_asset_dir(project_dir):
    build_asset_dir = os.path.join(project_dir, BUILD_ASSET_DIR)
    return build_asset_dir


COMPILED_CONTRACTS_ASSET_FILENAME = './contracts.json'


def get_compiled_contracts_asset_path(build_asset_dir):
    compiled_contracts_asset_path = os.path.join(
        build_asset_dir,
        COMPILED_CONTRACTS_ASSET_FILENAME,
    )
    return compiled_contracts_asset_path


@to_tuple
def find_solidity_source_files(base_dir):
    return (
        os.path.relpath(source_file_path)
        for source_file_path
        in recursive_find_files(base_dir, "*.sol")
    )


def get_project_source_paths(contracts_source_dir):
    project_source_paths = find_solidity_source_files(contracts_source_dir)
    return project_source_paths


def get_test_source_paths(tests_dir):
    test_source_paths = find_solidity_source_files(tests_dir)
    return test_source_paths


def write_compiled_sources(compiled_contracts_asset_path, compiled_sources):
    logger = logging.getLogger('populus.compilation.write_compiled_sources')
    ensure_file_exists(compiled_contracts_asset_path)

    with open(compiled_contracts_asset_path, 'w') as outfile:
        outfile.write(
            json.dumps(compiled_sources.to_dict(),
                       sort_keys=True,
                       indent=4,
                       separators=(',', ': '))
        )

    logger.info(
        "> Wrote compiled assets to: %s",
        os.path.relpath(compiled_contracts_asset_path)
    )

    return compiled_contracts_asset_path


@to_dict
def add_dependencies_to_compiled_contracts(compiled_contract_data):
    dependency_graph = get_shallow_dependency_graph(
        compiled_contract_data,
    )
    deploy_order = compute_deploy_order(dependency_graph)

    for contract_name, contract_data in compiled_contract_data.items():
        deps = get_recursive_contract_dependencies(
            contract_name,
            dependency_graph,
        )
        ordered_deps = [cid for cid in deploy_order if cid in deps]
        yield contract_name, assoc(contract_data, 'ordered_dependencies', ordered_deps)


post_process_compiled_contracts = compose(
    add_dependencies_to_compiled_contracts,
)


def load_json_if_string(value):
    if is_string(value):
        return json.loads(value)
    else:
        return value


def normalize_contract_metadata(metadata):
    if not metadata:
        return None
    elif is_string(metadata):
        return json.loads(metadata)
    else:
        raise ValueError("Unknown metadata format '{0}'".format(metadata))


V1 = 'v1'


CONTRACT_DATA_SCHEMA_PATHS = {
    V1: os.path.join(ASSETS_DIR, 'contract-data.v1.schema.json'),
}


def validate_contract_data(contract_data, schema_version=V1):
    if schema_version not in CONTRACT_DATA_SCHEMA_PATHS:
        raise KeyError("No schema for version: {0} - Must be one of {1}".format(
            schema_version,
            ", ".join(sorted(CONTRACT_DATA_SCHEMA_PATHS.keys())),
        ))
    schema = anyconfig.load(CONTRACT_DATA_SCHEMA_PATHS[schema_version])
    validator = jsonschema.Draft4Validator(schema)
    errors = [error for error in validator.iter_errors(contract_data)]
    if errors:
        raise ValidationError(
            "Invalid contract data:\n{0}".format(
                "\n".join((error.message for error in errors))
            )
        )
