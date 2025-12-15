# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/21 15:26
# @Author  : chao.li
# @File    : case_handle.py

import json
import logging
from pathlib import Path
import os
import yaml


class testcaseManager:
    """Manage test case and test suite configuration files.

    This helper encapsulates operations for reading, updating and
    synchronising test case metadata stored in ``testcase.json`` and test
    suite definitions stored in ``testsuite.yaml``.  It maintains an
    internal mapping of test case names to their attributes and provides
    methods for ensuring that every Python file under the specified test
    directory is represented in the case dictionary.  Test suites are
    represented as YAML lists of test case paths grouped by suite name.
    """

    def __init__(self, path: str = 'test') -> None:
        """Initialise a new :class:`testcaseManager` instance.

        Parameters
        ----------
        path:
            Filesystem path to the root directory containing test case
            implementations.  Each non‑``__init__.py`` Python file within
            this tree will be tracked as a test case.

        Side Effects
        ------------
        Immediately invokes :meth:`sync_caseJson` to populate
        ``testcase.json`` with any new test files.
        """
        self.test_path = Path(path)
        # JSON file mapping test case names to their metadata
        self.case_json = Path('testcase.json')
        # YAML file mapping suite names to lists of test case paths
        self.suite_yaml = Path('testsuite.yaml')
        self.suite_dict: dict = {}
        # Populate case_json on construction
        self.sync_caseJson()

    def _ensure_case(self, filepath: str, filename: str) -> None:
        """Ensure that a test case entry exists for the given file.

        Given a directory path and filename, construct a POSIX path and
        insert a default entry into the ``case_dict`` mapping if the
        filename is not already present.  Existing entries are left
        untouched.  When adding a new entry the ``id`` is initialised to
        ``1``, the description is set to a placeholder string, the
        ``priority`` defaults to ``"P0"`` and the ``path`` field stores
        the fully qualified POSIX path of the test file.

        Parameters
        ----------
        filepath:
            Directory portion of the test file path.
        filename:
            Name of the test file (including extension).

        Returns
        -------
        None
        """
        path = Path(filepath, filename).as_posix()
        if filename not in self.case_dict:
            logging.info("新增: %s", path)
        self.case_dict.setdefault(
            filename,
            {"id": 1, "desc": "xxx", "priority": "P0", "path": path},
        )

    def load_caseJson(self) -> None:
        """Load the test case dictionary from ``testcase.json``.

        Reads the JSON file specified by :attr:`case_json` and populates
        ``self.case_dict`` with its contents.  If the file is empty or
        contains invalid JSON, ``case_dict`` will be reset to an empty
        dictionary.  This method does not return any value; it updates
        internal state only.

        Returns
        -------
        None
        """
        self.case_dict = {}
        with self.case_json.open('r') as f:
            try:
                self.case_dict = json.load(f)
            except json.JSONDecodeError:
                self.case_dict = {}

    def update_caseJson(self, case: str, **kwargs) -> None:
        """Update a single test case entry and persist to disk.

        Looks up the given ``case`` in ``case_dict`` and applies keyword
        updates to its dictionary.  After updating the in‑memory mapping
        the entire ``case_dict`` is written back to :attr:`case_json` with
        pretty formatting for human readability.

        Parameters
        ----------
        case:
            Key of the test case to update.
        **kwargs:
            Arbitrary keyword pairs to merge into the selected case entry.

        Returns
        -------
        None
        """
        self.case_dict[case].update(**kwargs)
        logging.info(self.case_dict)
        with self.case_json.open('w') as f:
            json.dump(self.case_dict, f, indent=4)

    def sync_caseJson(self) -> None:
        """Synchronise discovered test files with ``testcase.json``.

        Walks the directory tree rooted at :attr:`test_path` and ensures
        that every Python file (except ``__init__.py`` and files within
        ``__pycache__`` directories) has an entry in ``case_dict``.  The
        updated mapping is then serialised to ``testcase.json`` in UTF‑8
        with indentation for readability.  Use this method whenever new
        test modules are added to the test directory.

        Returns
        -------
        None
        """
        self.load_caseJson()
        for filepath, _, filenames in os.walk(self.test_path):
            if '__pycache__' in filepath:
                continue
            for filename in filenames:
                if '__init__.py' in filename:
                    continue
                self._ensure_case(filepath, filename)
        json_str = json.dumps(self.case_dict, indent=4, ensure_ascii=False)
        with self.case_json.open('w') as f:
            f.write(json_str)

    def load_suiteYaml(self, suite: str = '') -> list | None:
        """Retrieve the list of test cases belonging to a given suite.

        Reads the YAML file specified by :attr:`suite_yaml` and loads it
        into ``suite_dict``.  If a ``suite`` name is provided and exists
        within the YAML data, the corresponding list of test case paths is
        returned.  If the suite does not exist, ``None`` is returned.

        Parameters
        ----------
        suite:
            Name of the suite to look up.  If omitted or empty, this
            method simply loads the YAML data into ``suite_dict`` without
            returning a specific suite.

        Returns
        -------
        list | None
            A list of test case paths if the suite exists; otherwise
            ``None``.
        """
        with open(self.suite_yaml, 'r') as f:
            yaml_data = yaml.load(f, Loader=yaml.FullLoader)
        if yaml_data:
            self.suite_dict = yaml_data
            if suite and suite in yaml_data:
                test_case = yaml_data[suite]
                return test_case
        return None

    def sync_testSuite(self, suite: str, case: str, **kwargs) -> list | None:
        """Update suite membership and persist changes to ``testsuite.yaml``.

        Ensures that the specified ``case`` is listed under the given
        ``suite`` in the YAML configuration.  If additional keyword
        arguments are provided, the test case entry in ``case_dict`` is
        updated via :meth:`update_caseJson` before modifying the suite
        definition.  New suites are created on demand.  The updated
        structure is written back to disk with indentation for ease of
        review.

        Parameters
        ----------
        suite:
            Name of the suite to update.
        case:
            Filename of the test case to add to the suite.
        **kwargs:
            Optional key/value pairs used to update the case metadata
            before adding it to the suite.

        Returns
        -------
        list | None
            The updated list of test case paths for the suite, or ``None``
            if no suite data existed prior to the update.
        """
        if kwargs:
            self.update_caseJson(case, **kwargs)
        case_list = self.load_suiteYaml(suite)
        if case_list:
            for i in case_list:
                if case in i:
                    break
            else:
                case_list.append(self.case_dict[case]['path'])
            data = {
                **self.suite_dict, **{suite: case_list}
            }
        else:
            data = {suite: [self.case_dict[case]['path']]}

        with self.suite_yaml.open('w') as f:
            yaml.dump(data, stream=f, indent=4)
        return case_list
