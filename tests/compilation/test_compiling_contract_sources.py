import os

from populus import ASSETS_DIR

from populus.compilation import (
    compile_project_contracts,
)

from populus.utils.compile import (
    get_contracts_source_dir,
)
from populus.utils.testing import (
    load_contract_fixture,
    load_test_contract_fixture,
    load_example_package,
)

GREETER_SOURCE_PATH = os.path.join(ASSETS_DIR, 'Greeter.sol')


@load_contract_fixture('Math.sol')
def test_compiling_project_contracts(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'contracts/Math.sol' in source_paths

    assert 'Math' in contract_data
    assert 'bytecode' in contract_data['Math']
    assert 'bytecode_runtime' in contract_data['Math']
    assert 'abi' in contract_data['Math']


@load_contract_fixture('ImportTestA.sol')
@load_contract_fixture('ImportTestB.sol')
@load_contract_fixture('ImportTestC.sol')
def test_compiling_with_local_project_imports(project):
    _, contract_data = compile_project_contracts(project)

    assert 'ImportTestA' in contract_data
    assert 'ImportTestB' in contract_data
    assert 'ImportTestC' in contract_data


@load_example_package('owned')
def test_compiling_with_single_installed_package(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'owned' in contract_data


@load_example_package('owned')
@load_example_package('standard-token')
def test_compiling_with_multiple_installed_packages(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'owned' in contract_data
    assert 'Token' in contract_data
    assert 'StandardToken' in contract_data


@load_example_package('transferable')
def test_compiling_with_nested_installed_packages(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'owned' in contract_data
    assert 'transferable' in contract_data


@load_example_package('transferable')
def test_compiling_with_nested_installed_packages(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'owned' in contract_data
    assert 'transferable' in contract_data


@load_test_contract_fixture('TestMath.sol')
def test_compiling_with_test_contracts(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'TestMath' in contract_data


@load_contract_fixture('Abstract.sol')
def test_compiling_with_abstract_contract(project):
    _, contract_data = compile_project_contracts(project)

    assert 'Abstract' in contract_data


@load_contract_fixture('Abstract.sol')
@load_contract_fixture('UsesAbstract.sol')
def test_compiling_with_abstract_contract_inhereted(project):
    _, contract_data = compile_project_contracts(project)

    assert 'Abstract' in contract_data
    assert 'UsesAbstract' in contract_data


@load_contract_fixture(GREETER_SOURCE_PATH)
def test_compiling_example_greeter_contract(project):
    _, contract_data = compile_project_contracts(project)

    assert 'Greeter' in contract_data


@load_example_package('owned')
@load_test_contract_fixture('UsesOwned.sol')
def test_compiling_with_import_from_package(project):
    source_paths, contract_data = compile_project_contracts(project)

    assert 'UsesOwned' in contract_data
    assert 'owned' in contract_data
