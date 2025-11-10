#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Animated tree view utilities for Qt-based UIs.

This module extends :class:`qfluentwidgets.TreeView` to provide a smooth
row-expansion animation. Instead of instantly jumping to the final row heights,
a temporary per-index height map is animated from 0 -> target height.

Design
------
- A private helper QObject (:class:`_RowHeightWrapper`) exposes a Qt property
  named ``height`` that reads/writes a single index's row height in a dict.
- :class:`AnimatedTreeView` overrides ``indexRowSizeHint`` to serve heights
  from that dict while an animation is in progress, falling back to the base
  implementation when no temporary value exists.
- On expand, a :class:`QParallelAnimationGroup` drives per-child
  :class:`QPropertyAnimation` instances to the target heights. When finished,
  the temporary overrides are removed and normal sizing resumes.

Notes
-----
This module does *not* depend on any I/O or application settings. It is purely
a visual enhancement and should be safe to reuse across Qt apps that expose a
TreeView-like interface with ``indexRowSizeHint`` and ``setExpanded``.
"""

from __future__ import annotations

from PyQt5.QtCore import QPropertyAnimation, QParallelAnimationGroup, QObject, pyqtProperty
from qfluentwidgets import TreeView


class _RowHeightWrapper(QObject):
    """
    Helper object that bridges a single index's row height to a Qt property.

    The wrapper allows using :class:`QPropertyAnimation` on a per-index basis.
    It stores and retrieves heights in the parent tree's private height map
    (``tree._row_heights``), then triggers geometry updates on change.

    Parameters
    ----------
    tree : AnimatedTreeView
        The owning tree view. Used to access the temporary height map and to
        refresh geometries while animating.
    index : QModelIndex
        The model index whose row height is being animated.
    """

    def __init__(self, tree, index):
        super().__init__(tree)
        self._tree = tree
        self._index = index

    def _set_height(self, height: int) -> None:
        """
        Set the current animated height for ``self._index`` and refresh geometry.

        Parameters
        ----------
        height : int
            The intermediate height value (in pixels).
        """
        self._tree._row_heights[self._index] = height
        self._tree.updateGeometries()

    def _get_height(self) -> int:
        """
        Return the current temporary height for ``self._index``.

        Returns
        -------
        int
            The temporary height if present, otherwise ``0``.
        """
        return self._tree._row_heights.get(self._index, 0)

    #: Qt property used by QPropertyAnimation (name must be bytes on PyQt5).
    height = pyqtProperty(int, fset=_set_height, fget=_get_height)


class AnimatedTreeView(TreeView):
    """
    A TreeView with expand animation for child rows.

    Behavior
    --------
    - When expanding an index, the control pre-expands the node (so children
      exist), then animates each direct child's row height from 0 to its native
      size hint using a parallel animation group.
    - While the animation runs, :meth:`indexRowSizeHint` serves the temporary
      heights from ``_row_heights`` so the viewport progressively reveals rows.
    - After the animation finishes, temporary overrides are cleared, updates are
      re-enabled, and the viewport is repainted once.

    Attributes
    ----------
    ANIMATION_DURATION : int
        Total duration of the expand animation in milliseconds.
    _row_heights : dict
        Internal mapping from ``QModelIndex`` to *temporary* row heights used
        only during an active animation cycle.
    """

    ANIMATION_DURATION = 180  # ms

    def __init__(self, *args, **kwargs):
        """Initialize the tree and the temporary height cache."""
        super().__init__(*args, **kwargs)
        self._row_heights = {}

    # Override row size hint to consult the temporary height map while animating.
    def indexRowSizeHint(self, index):  # noqa: N802 (Qt naming convention)
        """
        Return the row height for ``index`` while honoring active animations.

        During an animation, this method returns the temporary height stored in
        ``_row_heights``. When no override is present, it delegates to the base
        implementation.

        Parameters
        ----------
        index : QModelIndex
            The model index whose row height is requested.

        Returns
        -------
        int
            Height in pixels, either from the temporary cache or from the base
            class's ``indexRowSizeHint``.
        """
        return self._row_heights.get(index, super().indexRowSizeHint(index))

    def setExpanded(self, index, expand):  # noqa: D401, N802
        """
        Reimplemented to animate child rows on expand.

        If ``expand`` is truthy and a model is present, the method:
        1) Temporarily disables updates to avoid unnecessary repaints.
        2) Calls the base :meth:`setExpanded` to materialize children.
        3) Builds a :class:`QParallelAnimationGroup` with one animation per
           direct child index, animating height 0 -> target size hint.
        4) On completion, removes temporary heights, re-enables updates, and
           repaints the viewport.

        Parameters
        ----------
        index : QModelIndex
            The parent index that is being expanded or collapsed.
        expand : bool
            Whether to expand (``True``) or collapse (``False``) the node.
        """
        model = self.model()
        if expand and model is not None:
            self.setUpdatesEnabled(False)
            super().setExpanded(index, expand)
            group = QParallelAnimationGroup(self)
            for row in range(model.rowCount(index)):
                child = model.index(row, 0, index)
                target = super().indexRowSizeHint(child)
                self._row_heights[child] = 0
                wrapper = _RowHeightWrapper(self, child)
                anim = QPropertyAnimation(wrapper, b"height", self)
                anim.setDuration(self.ANIMATION_DURATION)
                anim.setStartValue(0)
                anim.setEndValue(target)
                group.addAnimation(anim)

            def _on_finished():
                for row in range(model.rowCount(index)):
                    child = model.index(row, 0, index)
                    self._row_heights.pop(child, None)
                self.setUpdatesEnabled(True)
                self.viewport().update()

            group.finished.connect(_on_finished)
            group.start(QPropertyAnimation.DeleteWhenStopped)
        else:
            super().setExpanded(index, expand)
