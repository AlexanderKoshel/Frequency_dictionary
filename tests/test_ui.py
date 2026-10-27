"""Headless UI smoke tests; the core suite also runs without Qt installed."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QCoreApplication, QEvent
    from src.ui.main_window import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = MainWindow(self.root / "dictionary.db")
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def test_crud_search_confirmation(self):
        with patch("src.ui.main_window.QInputDialog.getText", return_value=("кот", True)):
            self.window.add_word()
        self.assertEqual(self.window.table.rowCount(), 1)
        self.window.table.selectRow(0)
        with patch("src.ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.delete_word()
        self.assertEqual(self.window.table.rowCount(), 1)
        self.window.table.selectRow(0)
        with patch("src.ui.main_window.QInputDialog.getText", return_value=("собака", True)):
            self.window.rename_word()
        self.window.search.setText("кот")
        self.assertEqual(self.window.table.rowCount(), 0)
        self.window.search.clear()
        self.window.table.selectRow(0)
        with patch("src.ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_word()
        self.assertEqual(self.window.table.rowCount(), 0)

    def test_background_import(self):
        text = self.root / "sample.txt"
        text.write_text("кот кот собака", encoding="utf-8")
        self.window.start_import([text])
        deadline = time.monotonic() + 10
        while self.window.worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertIsNone(self.window.worker)
        self.assertEqual(self.window.table.rowCount(), 2)
        self.assertEqual(self.window.repository.stats("ru")["total"], 3)
        self.assertTrue(self.window.language.isEnabled())


if __name__ == "__main__":
    unittest.main()
