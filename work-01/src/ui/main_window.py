"""Desktop UI; corpus imports run on a separate thread and connection."""
import sqlite3
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from ..database.repository import Repository
from ..dictionary.frequency import import_file
from ..parser.text_finder import find_all_texts
from ..parser.tokenizer import LANGUAGES


class ImportWorker(QThread):
    progress = Signal(str)
    result = Signal(str)

    def __init__(self, db_path, paths, language, encoding, parent=None):
        super().__init__(parent)
        self.db_path, self.paths, self.language, self.encoding = db_path, paths, language, encoding

    def run(self):
        repository = None
        imported = skipped = tokens = 0
        try:
            repository = Repository(self.db_path)
            for path in self.paths:
                self.progress.emit(f"Импорт: {path.name}")
                outcome = import_file(repository, path, self.language, self.encoding,
                                      progress=lambda n: self.progress.emit(f"{path.name}: {n:,} слов"))
                skipped += int(outcome["skipped"])
                imported += int(not outcome["skipped"])
                tokens += outcome["tokens"]
            self.result.emit(f"Импортировано файлов: {imported}; пропущено повторов: {skipped}; слов: {tokens:,}")
        except (OSError, ValueError, sqlite3.Error) as error:
            self.result.emit(f"Импорт остановлен: {error}\nРанее завершённые файлы сохранены; проблемный файл отменён.")
        finally:
            if repository:
                repository.close()


class MainWindow(QMainWindow):
    PAGE_SIZE = 200

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.repository = Repository(db_path)
        self.worker = None
        self.offset = 0
        self.setWindowTitle("Частотные словари")
        self.resize(1000, 720)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        title = QLabel("Частотные словари")
        title.setStyleSheet("font-size: 26px; font-weight: bold; padding: 10px 0")
        layout.addWidget(title)
        controls = QHBoxLayout()
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Начало слова…")
        self.sort = QComboBox()
        for label, value in [("Алфавит ↑", ("word", False)), ("Алфавит ↓", ("word", True)),
                             ("Частота ↓", ("frequency", True)), ("Частота ↑", ("frequency", False))]:
            self.sort.addItem(label, value)
        controls.addWidget(self.language)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.sort)
        layout.addLayout(controls)
        self.statistics = QLabel()
        self.statistics.setWordWrap(True)
        layout.addWidget(self.statistics)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Слово", "Частота"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 540)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        pages = QHBoxLayout()
        self.previous = QPushButton("← Назад")
        self.next = QPushButton("Далее →")
        self.page = QLabel()
        pages.addWidget(self.previous)
        pages.addWidget(self.page, 1)
        pages.addWidget(self.next)
        layout.addLayout(pages)
        actions = QHBoxLayout()
        self.action_buttons = []
        for label, callback in [("Добавить слово", self.add_word), ("Исправить", self.rename_word),
                                ("Удалить", self.delete_word), ("Импорт файлов", self.import_files),
                                ("Импорт папки", self.import_folder)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
            self.action_buttons.append(button)
        layout.addLayout(actions)
        encoding_row = QHBoxLayout()
        encoding_row.addWidget(QLabel("Кодировка импортируемых TXT:"))
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8-sig", "cp1251", "utf-16", "cp1252"])
        encoding_row.addWidget(self.encoding)
        encoding_row.addStretch()
        layout.addLayout(encoding_row)
        self.status = QLabel("Выберите язык и импортируйте тексты. Словарь сохраняется автоматически.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.language.currentIndexChanged.connect(self.reset_page)
        self.sort.currentIndexChanged.connect(self.reset_page)
        self.search.textChanged.connect(self.reset_page)
        self.previous.clicked.connect(lambda: self.change_page(-1))
        self.next.clicked.connect(lambda: self.change_page(1))
        self.refresh()

    def reset_page(self, *_):
        self.offset = 0
        self.refresh()

    def change_page(self, step):
        self.offset = max(0, self.offset + step * self.PAGE_SIZE)
        self.refresh()

    def refresh(self):
        language = self.language.currentData()
        sort, descending = self.sort.currentData()
        rows = self.repository.rows(language, self.search.text(), sort, descending, self.PAGE_SIZE + 1, self.offset)
        self.next.setEnabled(len(rows) > self.PAGE_SIZE)
        self.previous.setEnabled(self.offset > 0)
        rows = rows[:self.PAGE_SIZE]
        self.table.setRowCount(len(rows))
        for row, (word, count) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(word))
            item = QTableWidgetItem(str(count))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, item)
        self.page.setText(f"Страница {self.offset // self.PAGE_SIZE + 1} · показано {len(rows)}")
        stats = self.repository.stats(language)
        self.statistics.setText(
            f"Словоупотреблений в словаре: {stats['total']:,}   ·   Уникальных: {stats['unique']:,}\n"
            f"Импортировано из текстов: {stats['imported']:,} / {stats['target']:,}   ·   "
            + ("Объём корпуса достигнут" if stats['imported'] >= stats['target'] else "Корпус нужно пополнить"))

    def selected_word(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            raise ValueError("Сначала выберите слово в таблице")
        return self.table.item(row, 0).text()

    def mutate(self, operation):
        try:
            operation()
            self.reset_page()
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Ошибка", str(error))

    def add_word(self):
        word, ok = QInputDialog.getText(self, "Добавить слово", "Слово (начальная частота — 0):")
        if ok:
            self.mutate(lambda: self.repository.add(self.language.currentData(), word))

    def rename_word(self):
        def operation():
            old = self.selected_word()
            new, ok = QInputDialog.getText(self, "Исправить слово", "Новое написание (частоты совпавших слов суммируются):", text=old)
            if ok:
                self.repository.rename(self.language.currentData(), old, new)
        self.mutate(operation)

    def delete_word(self):
        def operation():
            word = self.selected_word()
            answer = QMessageBox.question(self, "Подтверждение", f'Удалить «{word}»?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                self.repository.delete(self.language.currentData(), word)
        self.mutate(operation)

    def import_files(self):
        from pathlib import Path
        paths, _ = QFileDialog.getOpenFileNames(self, "Выберите тексты", "", "Тексты (*.txt *.TXT)")
        if paths:
            self.start_import([Path(p) for p in paths])

    def import_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Папка с текстами (включая вложенные)")
        if path:
            try:
                self.start_import(find_all_texts(path))
            except OSError as error:
                QMessageBox.warning(self, "Ошибка", str(error))

    def start_import(self, paths):
        if not paths:
            self.status.setText("В папке нет TXT-файлов")
            return
        self.set_busy(True)
        self.worker = ImportWorker(self.db_path, paths, self.language.currentData(), self.encoding.currentText(), self)
        self.worker.progress.connect(self.status.setText)
        self.worker.result.connect(self.status.setText)
        self.worker.finished.connect(self.import_finished)
        self.worker.start()

    def set_busy(self, busy):
        for widget in [*self.action_buttons, self.language, self.sort, self.search, self.encoding, self.previous, self.next]:
            widget.setEnabled(not busy)

    def import_finished(self):
        self.set_busy(False)
        self.reset_page()
        self.worker.deleteLater()
        self.worker = None

    def closeEvent(self, event):
        if self.worker is not None:
            QMessageBox.information(self, "Идёт импорт", "Дождитесь завершения импорта перед закрытием приложения.")
            event.ignore()
            return
        self.repository.close()
        event.accept()
