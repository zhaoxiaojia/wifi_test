from __future__ import annotations

from typing import Any


def reset_wizard_after_run(page: Any) -> None:
    """Reset Config wizard state after a successful run.

    This helper centralises the post-run behaviour so that both the Config
    page and any other entry points can reuse the same logic:
    - navigate back to the first (DUT) page
    - re-sync Run button enabled state
    - restore second-page (Execution) CSV selection and enabled state
    """
    # Navigate back to DUT page if the stack is available.
    stack = getattr(page, "stack", None)
    if stack is not None and hasattr(stack, "setCurrentIndex"):
        try:
            stack.setCurrentIndex(0)
        except Exception:
            pass

    # Delegate button/CSV reset to the ConfigController when present.
    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None:
        try:
            config_ctl.sync_run_buttons_enabled()
        except Exception:
            pass
        try:
            config_ctl.reset_second_page_inputs()
        except Exception:
            pass


__all__ = ["reset_wizard_after_run"]

