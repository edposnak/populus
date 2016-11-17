from __future__ import absolute_import

import itertools
import logging
import os

from populus.utils.compile import (
    compute_project_compilation_arguments,
    compute_test_compilation_arguments,
    compute_installed_packages_compilation_arguments,
)


def compile_project_contracts(project):
    logger = logging.getLogger('populus.compilation.compile_project_contracts')

    project_source_paths, project_import_remappings = compute_project_compilation_arguments(
        project.contracts_source_dir,
        project.installed_packages_dir,
    )
    logger.debug(
        "Found %s project source files: %s",
        len(project_source_paths),
        project_source_paths,
    )
    test_source_paths, test_import_remappings = compute_test_compilation_arguments(
        project.tests_dir,
        project.installed_packages_dir,
    )
    logger.debug(
        "Found %s test source files: %s",
        len(test_source_paths),
        test_source_paths,
    )
    installed_packages_compilation_arguments = (
        compute_installed_packages_compilation_arguments(project.installed_packages_dir)
    )
    if installed_packages_compilation_arguments:
        installed_packages_source_paths, installed_packages_import_remappings = (
            installed_packages_compilation_arguments
        )
    else:
        installed_packages_source_paths = tuple()
        installed_packages_import_remappings = tuple()
    logger.debug(
        "Found %s dependency source files: %s",
        len(installed_packages_source_paths),
        installed_packages_source_paths,
    )

    all_source_paths = tuple(itertools.chain(
        project_source_paths,
        test_source_paths,
        *installed_packages_source_paths
    ))
    all_import_remappings = tuple(itertools.chain(
        project_import_remappings,
        test_import_remappings,
        *installed_packages_import_remappings
    ))

    compiler_backend = project.get_compiler_backend()
    compiled_contract_data = compiler_backend.get_compiled_contract_data(
        source_file_paths=all_source_paths,
        import_remappings=all_import_remappings,
    )

    logger.info("> Found %s contract source files", len(all_source_paths))
    for path in all_source_paths:
        logger.info("  - %s", os.path.relpath(path))

    logger.info("> Compiled %s contracts", len(compiled_contract_data))
    for contract_name in sorted(compiled_contract_data.keys()):
        logger.info("  - %s", contract_name)

    return all_source_paths, compiled_contract_data
