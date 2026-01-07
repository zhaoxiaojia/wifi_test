from __future__ import annotations


class UiAutomationMixin:
    def u(self, type="u2"):
        return self._u_impl(type=type)

    def _u_impl(self, *, type="u2"):
        raise NotImplementedError

    def uiautomator_dump(self, filepath="", uiautomator_type="u2"):
        return self._uiautomator_dump_impl(filepath=filepath, uiautomator_type=uiautomator_type)

    def _uiautomator_dump_impl(self, *, filepath="", uiautomator_type="u2"):
        raise NotImplementedError
