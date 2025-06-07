import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QDialog,
    QLabel, QLineEdit, QSpinBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt

DB_FILE = 'mbworld_tasks.db'


class TaskDatabase:
    def __init__(self, filename=DB_FILE):
        self.conn = sqlite3.connect(filename)
        self._create_table()

    def _create_table(self):
        c = self.conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self.conn.commit()

    def add_task(self, description, priority):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO tasks (description, priority, done) VALUES (?, ?, 0)",
            (description, priority)
        )
        self.conn.commit()

    def mark_done(self, task_id, done=True):
        c = self.conn.cursor()
        c.execute("UPDATE tasks SET done = ? WHERE id = ?", (int(done), task_id))
        self.conn.commit()

    def delete_task(self, task_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def fetch_tasks(self, done=False):
        c = self.conn.cursor()
        c.execute(
            "SELECT id, description, priority FROM tasks WHERE done = ? ORDER BY priority ASC",
            (int(done),)
        )
        return c.fetchall()


class AddTaskDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add Task")
        layout = QVBoxLayout()
        self.desc_edit = QLineEdit()
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)

        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.desc_edit)
        layout.addWidget(QLabel("Priority:"))
        layout.addWidget(self.priority_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_data(self):
        return self.desc_edit.text(), self.priority_spin.value()


class MBWorldTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.db = TaskDatabase()
        self.setWindowTitle("MB World Project Tracker")
        self.resize(600, 400)
        main_layout = QHBoxLayout()

        # Left: To-Do
        self.todo_table = QTableWidget()
        self.todo_table.setColumnCount(2)
        self.todo_table.setHorizontalHeaderLabels(["Task", "Priority"])
        self.todo_table.horizontalHeader().setStretchLastSection(True)

        # Right: Done
        self.done_table = QTableWidget()
        self.done_table.setColumnCount(2)
        self.done_table.setHorizontalHeaderLabels(["Task", "Priority"])
        self.done_table.horizontalHeader().setStretchLastSection(True)

        # Middle buttons
        btn_layout = QVBoxLayout()
        self.add_btn = QPushButton("Add ->")
        self.done_btn = QPushButton("Mark Done ->")
        self.remove_btn = QPushButton("Delete")

        self.add_btn.clicked.connect(self.add_task)
        self.done_btn.clicked.connect(self.mark_done)
        self.remove_btn.clicked.connect(self.delete_task)

        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.done_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()

        main_layout.addWidget(self.todo_table)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.done_table)
        self.setLayout(main_layout)

        self.load_tasks()

    def load_tasks(self):
        todo = self.db.fetch_tasks(done=False)
        done = self.db.fetch_tasks(done=True)
        self.populate_table(self.todo_table, todo)
        self.populate_table(self.done_table, done)

    def populate_table(self, table, data):
        table.setRowCount(len(data))
        for row, (task_id, desc, prio) in enumerate(data):
            item_desc = QTableWidgetItem(desc)
            item_desc.setData(Qt.ItemDataRole.UserRole, task_id)
            item_prio = QTableWidgetItem(str(prio))
            table.setItem(row, 0, item_desc)
            table.setItem(row, 1, item_prio)
        table.sortItems(1)

    def add_task(self):
        dialog = AddTaskDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            desc, prio = dialog.get_data()
            if desc:
                self.db.add_task(desc, prio)
                self.load_tasks()

    def get_selected_task_id(self, table):
        row = table.currentRow()
        if row >= 0:
            item = table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def mark_done(self):
        task_id = self.get_selected_task_id(self.todo_table)
        if task_id is not None:
            self.db.mark_done(task_id, True)
            self.load_tasks()

    def delete_task(self):
        task_id = self.get_selected_task_id(self.done_table)
        if task_id is not None:
            self.db.delete_task(task_id)
            self.load_tasks()


def main():
    app = QApplication(sys.argv)
    tracker = MBWorldTracker()
    tracker.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
