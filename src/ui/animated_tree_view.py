from PyQt5.QtCore import QPropertyAnimation, QParallelAnimationGroup, QObject, pyqtProperty
from qfluentwidgets import TreeView


class _RowHeightWrapper(QObject):
    """Helper object to animate row height via property animation."""

    def __init__(self, tree, index):
        super().__init__(tree)
        self._tree = tree
        self._index = index

    def _set_height(self, height: int):
        self._tree._row_heights[self._index] = height
        self._tree.updateGeometries()

    def _get_height(self) -> int:
        return self._tree._row_heights.get(self._index, 0)

    height = pyqtProperty(int, fset=_set_height, fget=_get_height)


class AnimatedTreeView(TreeView):
    """带展开动画的 TreeView"""

    ANIMATION_DURATION = 180  # ms

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._row_heights = {}

    # 重写行高提示以支持动画高度
    def indexRowSizeHint(self, index):  # noqa: N802 (Qt 命名约定)
        return self._row_heights.get(index, super().indexRowSizeHint(index))

    def setExpanded(self, index, expand):  # noqa: D401, N802
        """重写以在展开时添加动画"""
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
