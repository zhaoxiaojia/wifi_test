# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/27 14:43
# @Author  : chao.li
# @File    : report_plugin.py
import os
import pytest
import logging
from _pytest.terminal import TerminalReporter


def pytest_runtest_call(item):
    try:
        item.runtest()
    except Exception as e:
        logging.exception(e)
        raise

@pytest.mark.trylast
def pytest_configure(config):
    # Get the standard terminal reporter plugin...
    standard_reporter = config.pluginmanager.getplugin('terminalreporter')
    reporter = QaTerminalReporter(standard_reporter)

    # ...and replace it with our own instafailing reporter.
    config.pluginmanager.unregister(standard_reporter)
    config.pluginmanager.register(reporter, 'terminalreporter')

    for test_path in config.option.file_or_dir:
        if "::" in test_path:
            test_path = test_path.split("::")[0]
        if not os.path.exists(test_path):
            pytest.result.log_brok("Given test path does not exist: %s" % test_path)
            raise Exception("Given test path does not exist: %s" % test_path)


class QaTerminalReporter(TerminalReporter):

    def __init__(self, reporter):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = reporter._tw
        try:
            self._sessionstarttime = reporter._sessionstarttime
        except:
            pass

    def write_line(self, line, **markup):
        logging.info(line)
        return super().write_line(line, **markup)

    def pytest_runtest_logstart(self, nodeid, location):
        # ensure that the path is printed before the
        # 1st test of a module starts running
        logging.info('{title:{char}^{length}}'.format(title=' runtest start ', length=80, char='='))
        logging.info(nodeid)
        if self.showlongtestinfo:
            line = self._locationline(nodeid, *location)
            self.write_ensure_prefix(line, "\n")
        elif self.showfspath:
            fsid = nodeid.split("::")[0]
            self.write_fspath_result(fsid, "\n")

    def pytest_sessionstart(self, session):
        logging.info('{title:{char}^{length}}'.format(title=' live log sessionstart ', length=80, char='-'))
        # super(QaTerminalReporter, self).pytest_sessionstart(session)

    def pytest_runtest_setup(self):
        logging.info('{title:{char}^{length}}'.format(title=' live log setup ', length=80, char='-'))

    def pytest_runtest_teardown(self):
        logging.info('{title:{char}^{length}}'.format(title=' live log teardown ', length=80, char='-'))

    def pytest_sessionfinish(self, exitstatus):
        logging.info('{title:{char}^{length}}'.format(title=' live log sessionfinish ', length=80, char='-'))
        # super(AATSTerminalReporter, self).pytest_sessionfinish(exitstatus)

    def pytest_runtest_call(self):
        logging.info('{title:{char}^{length}}'.format(title=' live log call ', length=80, char='-'))

    def pytest_collectreport(self, report):
        # Show errors occurred during the collection instantly.
        TerminalReporter.pytest_collectreport(self, report)
        if report.failed:
            self.rewrite("")  # erase the "collecting" message
            msg = "Error collecting {}".format(
                self._getfailureheadline(report))
            self.print_failure(report)

    def pytest_runtest_logreport(self, report):
        # Show failures and errors occuring during running a test
        # instantly.
        if (report.when != 'call') and report.outcome == 'passed':
            return

        cat, letter, word = self.config.hook.pytest_report_teststatus(
            report=report,
            config=self.config)
        self.stats.setdefault(cat, []).append(report)
        self._tests_ran = True
        if report.failed and not hasattr(report, 'wasxfail'):
            if self.verbosity <= 0:
                self._tw.line()
            line = self._getcrashline(report)
            msg = line.split(os.getcwd())[-1].lstrip('/')
            self.print_failure(report)
            # All the exceptions thrown from AATS result in a test failure.
            # Certain AATS exceptions however are actually issues in the
            # test environment and need to be marked as 'skipped' instead
            # of 'failed.'
            # Similarly, AATS timeout exceptions will be reported with 'BROK.'
        elif report.passed:
            # if pytest.result.log_auto_pass:
            msg = 'Test Passed'
        elif report.outcome == 'skipped':
            msg = "Test Skipped."
            if report.longrepr:
                try:
                    msg = report.longrepr[2]
                except:
                    pass
        logging.debug('{title:{char}^{length}}'.format(title=' runtest finish ', length=80, char='='))

    def summary_fialures(self):
        # Prevent failure summary from being shown since we already
        # show the failure instantly after failure has occured.
        pass

    def summary_errors(self):
        # Prevent error summary from being shown since we already
        # show the error instantly after error has occured.
        pass

    def print_failure(self, report):
        if self.config.option.tbstyle != "no":
            if self.config.option.tbstyle == "line":
                line = self._getcrashline(report)
                self.write_line(line)
            else:
                msg = self._getfailureheadline(report)
                if not hasattr(report, 'when'):
                    msg = "ERROR collecting " + msg
                elif report.when == "setup":
                    msg = "ERROR at setup of " + msg
                elif report.when == "teardown":
                    msg = "ERROR at teardown of " + msg
                self.write_sep("_", msg)
                # Todo
                if not self.config.getvalue("usepdb"):
                    self._outrep_summary(report)
