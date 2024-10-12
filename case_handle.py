# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/21 15:26
# @Author  : chao.li
# @File    : case_handle.py

import json
import logging
import os

import yaml


class testCase:
    def __init__(self, path='test'):
        self.test_path = path
        self.case_json = 'testcase.json'
        self.suite_yaml = 'testsuite.yaml'
        self.sute_dict = {}
        self.sync_caseJson()

    def load_caseJson(self):
        '''
        Get the testcase information from testcase.json
        Returns:

        '''
        self.case_dict = {}
        with open(self.case_json, 'r') as f:
            content = f.read()
        if content:
            self.case_dict = json.loads(content)

    def update_caseJson(self, case, **kwargs):
        self.case_dict[case].update(**kwargs)
        logging.info(self.case_dict)
        with open(self.case_json, 'w') as f:
            f.write(json.dumps(self.case_dict, indent=4))

    def sync_caseJson(self):
        '''
        Synchronize the test files in the test folder to testcase.json
        Returns:

        '''
        self.load_caseJson()
        for filepath, dirnames, filenames in os.walk(self.test_path):
            if '__pycache__' in filepath:
                continue
            for filename in filenames:
                if '__init__.py' in filename:
                    continue
                if filename not in self.case_dict.keys():
                    logging.info(f'新增: {os.path.join(filepath, filename)}')
                    logging.info('新增:', os.path.join(filepath, filename).replace('\\', '/'))
                    print(type(os.path.join(filepath, filename)))
                    self.case_dict[filename] = {'id': 1, 'desc': 'xxx', 'priority': 'P0',
                                                'path': os.path.join(filepath, filename).replace('\\', '/')}

        json_str = json.dumps(self.case_dict, indent=4, ensure_ascii=False)
        with open(self.case_json, 'w') as f:
            f.write(json_str)

    def load_suiteYaml(self, suite=''):
        '''
        Find the suite from testsuite.yaml
        Args:
            suite: suite name

        Returns: list of testcase in suite

        '''
        with open(self.suite_yaml, 'r') as f:
            yaml_data = yaml.load(f, Loader=yaml.FullLoader)
        if yaml_data:
            self.sute_dict = yaml_data
            if suite in yaml_data:
                test_case = yaml_data[suite]
                return test_case

    def sync_testSuite(self, suite, case, **kwargs):
        '''
        Update testsuite information to testsuite.yaml
        Args:
            suite: suite name
            case: case path
            **kwargs: case information

        Returns:

        '''
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
                **self.sute_dict, **{suite: case_list}
            }
        else:
            data = {suite: [self.case_dict[case]['path']]}

        with open(self.suite_yaml, 'w') as f:
            yaml.dump(data, stream=f, indent=4)
        return case_list
