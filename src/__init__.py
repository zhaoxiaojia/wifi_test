#!/usr/bin/env python
# encoding: utf-8
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: __init__.py.py
@time: 2025/7/29 9:39
@desc:
'''

from pathlib import Path


def case_path_to_display(case_path: str) -> str:
	"""Convert an internal case path (config/storage) to a display path.

	- If path starts with "test/" strip that prefix for a compact display.
	- Normalises separators to POSIX form.
	"""
	if not case_path:
		return ""
	normalized = Path(case_path).as_posix()
	return normalized[5:] if normalized.startswith("test/") else normalized


def display_to_case_path(display_path: str) -> str:
	"""Convert a user-visible display path back into a storage case path.

	- Accepts both relative and absolute inputs; returns an absolute-style
	  POSIX path for storage when input is absolute, otherwise ensures the
	  path begins with `test/`.
	"""
	if not display_path:
		return ""
	normalized = display_path.replace('\\', '/')
	if normalized.startswith('./'):
		normalized = normalized[2:]
	from pathlib import Path as _Path

	path_obj = _Path(normalized)
	if path_obj.is_absolute() or normalized.startswith('../'):
		return path_obj.as_posix()
	return normalized if normalized.startswith("test/") else f"test/{normalized}"


def update_test_case_display(page, storage_path: str) -> None:
	"""Set page state for currently displayed test case.

	- Sets `page._current_case_path` and updates `page.test_case_edit` if present.
	- Accepts a storage path (POSIX-style) and normalises it for display.
	"""
	normalized = Path(storage_path).as_posix() if storage_path else ""
	try:
		page._current_case_path = normalized
	except Exception:
		pass
	if hasattr(page, 'test_case_edit') and hasattr(page.test_case_edit, 'setText'):
		page.test_case_edit.setText(case_path_to_display(normalized))

