import os
import numpy as np
import subprocess
import sys
import csv
import random
import sqlite3
import platform
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDateTime, QDate, QPoint, QTimer, QSettings
from PyQt6.QtGui import (
    QColor, QDoubleValidator, QPainter, QPen, 
    QPixmap, QPolygon, QIcon, QCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QTabWidget, QDateEdit, QComboBox,
    QDialog, QDialogButtonBox, QGraphicsSimpleTextItem
)
from PyQt6.QtCharts import (
    QChart, QChartView, QLineSeries, QDateTimeAxis, 
    QValueAxis, QBarSeries, QBarSet, QBarCategoryAxis, QScatterSeries
)



# ================= TABLE ITEMS =================
class DateTimeTableWidgetItem(QTableWidgetItem):
    def __init__(self, text):
        super().__init__(text)
        self.sort_value = QDateTime.fromString(text, "yyyy-MM-dd HH:mm:ss")
        if not self.sort_value.isValid():
            self.sort_value = QDateTime.fromString(text, "yyyy-MM-dd")

    def __lt__(self, other):
        return self.sort_value < other.sort_value



# ================= DATABASE =================
class KittenDatabase:
    def __init__(self, production=True):
        self.production = production
        try:
            if platform.system() == "Windows":
                app_data = Path.home() / "AppData" / "Local" / "KittenTracker"
            elif platform.system() == "Darwin":
                app_data = Path.home() / "Library" / "Application Support" / "KittenTracker"
            else:
                app_data = Path.home() / ".local" / "share" / "KittenTracker"

            app_data.mkdir(parents=True, exist_ok=True)
            db_name = "kitten_tracker_prod.db" if production else "kitten_tracker_dev.db"
            self.db_path = app_data / db_name
            self.backup_dir = app_data / "backups"
            self.backup_dir.mkdir(exist_ok=True)

            self.conn = sqlite3.connect(self.db_path)
            self._exec("PRAGMA foreign_keys = ON;")
            self._create_tables()
            self._migrate_old_data()
            self._migrate_schema()
        except Exception as e:
            QMessageBox.critical(None, "Fatal Error", f"Failed to initialize database: {str(e)}")
            sys.exit(1)

    def _exec(self, query, params=()):
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            QMessageBox.warning(None, "Database Error", f"Operation failed: {str(e)}")
            return False

    def _create_tables(self):
        self._exec("""
            CREATE TABLE IF NOT EXISTS animals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                animal_type TEXT,
                birthdate DATE
            )
        """)
        self._exec("""
            CREATE TABLE IF NOT EXISTS weight_data (
                animal_id INTEGER REFERENCES animals(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                weight REAL NOT NULL,
                notes TEXT,
                UNIQUE(animal_id, date)
            )
        """)
        self._exec("""
            CREATE TABLE IF NOT EXISTS diet_logs (
                animal_id INTEGER REFERENCES animals(id) ON DELETE CASCADE,
                timestamp DATETIME NOT NULL,
                meal_type TEXT,
                food_item TEXT,
                brand TEXT,
                amount REAL,
                notes TEXT
            )
        """)

    def _migrate_old_data(self):
        old_path = Path("kitten_tracker.db")
        if old_path.exists():
            try:
                old_conn = sqlite3.connect(old_path)
                old_data = old_conn.execute("SELECT * FROM animals").fetchall()
                for row in old_data:
                    self._exec(
                        "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
                        (row[1], row[2], row[3])
                    )
                old_path.unlink()
            except Exception as e:
                print(f"Migration failed: {str(e)}")

    def _migrate_schema(self):
        cursor = self.conn.execute("PRAGMA table_info(diet_logs)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'notes' not in columns:
            self._exec("ALTER TABLE diet_logs ADD COLUMN notes TEXT")

        if 'brand' not in columns:
            self._exec("ALTER TABLE diet_logs ADD COLUMN brand TEXT")

    def get_data_folder(self):
        return self.db_path.parent

    def add_meal(self, animal_id, timestamp, meal_type, food, brand, amount, notes=""):
        return self._exec(
            "INSERT INTO diet_logs (animal_id, timestamp, meal_type, food_item, brand, amount, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (animal_id, timestamp, meal_type, food, brand, amount, notes)
        )

    def add_weight(self, animal_id, date, weight, notes=""):
        return self._exec(
            "INSERT INTO weight_data (animal_id, date, weight, notes) VALUES (?, ?, ?, ?)",
            (animal_id, date, weight, notes)
        )

    def get_weight_data(self, animal_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT date, weight, notes FROM weight_data WHERE animal_id=? ORDER BY date",
            (animal_id,)
        )
        return cursor.fetchall()

    def get_daily_nutrition(self, animal_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DATE(timestamp), SUM(amount)
            FROM diet_logs
            WHERE animal_id=?
            GROUP BY DATE(timestamp)
            ORDER BY DATE(timestamp)
        """, (animal_id,))
        return cursor.fetchall()

    def get_diet_logs(self, animal_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, meal_type, food_item, brand, amount, notes "
            "FROM diet_logs WHERE animal_id=? ORDER BY timestamp",
            (animal_id,)
        )
        return cursor.fetchall()

    def clear_test_data(self):
        self._exec("DELETE FROM animals")
        self._exec("DELETE FROM weight_data")
        self._exec("DELETE FROM diet_logs")

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}.db"
        try:
            self.conn.close()
            import shutil
            shutil.copy(self.db_path, backup_path)
            self.conn = sqlite3.connect(self.db_path)

            # Instead of a plain info box, show "Open Folder" or "OK"
            box = QMessageBox()
            box.setWindowTitle("Backup Created")
            box.setText(f"Backup created: {backup_path.name}")
            box.setIcon(QMessageBox.Icon.Information)

            open_folder = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
            box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)

            box.exec()

            if box.clickedButton() == open_folder:
                # Attempt to open the backups folder
                if platform.system() == "Windows":
                    os.startfile(self.backup_dir)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", self.backup_dir])
                else:
                    subprocess.run(["xdg-open", self.backup_dir])

        except Exception as e:
            QMessageBox.critical(None, "Backup Failed", f"Error: {str(e)}")





# ================= CHARTS =================
class HealthCorrelationChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Nutrition vs Weight Correlation")

        self.scatter = QScatterSeries()
        self.scatter.setName("Daily Data")
        self.scatter.setColor(QColor("#FFA726"))
        self.scatter.setMarkerSize(12)
        self.scatter.setBorderColor(QColor(0, 0, 0, 0))

        self.trend = QLineSeries()
        self.trend.setName("Trend Line")
        self.trend.setPen(QPen(QColor("#7E57C2"), 2, Qt.PenStyle.DashLine))

        self.addSeries(self.scatter)
        self.addSeries(self.trend)

        self.x_axis = QValueAxis()
        self.y_axis = QValueAxis()
        self.x_axis.setTitleText("Daily Nutrition (g)")
        self.y_axis.setTitleText("Weight Change (%)")
        self.x_axis.setLabelFormat("%.0f")
        self.y_axis.setLabelFormat("%.1f%%")

        self.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)

        self.scatter.attachAxis(self.x_axis)
        self.scatter.attachAxis(self.y_axis)
        self.trend.attachAxis(self.x_axis)
        self.trend.attachAxis(self.y_axis)

    def update_chart(self, nutrition_data, weight_data):
        self.scatter.clear()
        self.trend.clear()

        if not nutrition_data or len(weight_data) < 2:
            self.x_axis.setRange(0, 100)
            self.y_axis.setRange(-5, 5)
            return

        dates = [datetime.strptime(d[0], "%Y-%m-%d") for d in weight_data]
        weights = [d[1] for d in weight_data]

        weight_changes = {}
        for i in range(1, len(dates)):
            days_between = (dates[i] - dates[i - 1]).days
            if days_between == 0:
                continue
            daily_change = (weights[i] - weights[i - 1]) / weights[i - 1] / days_between
            for d in range(days_between):
                current_date = dates[i - 1] + timedelta(days=d)
                weight_changes[current_date] = daily_change * 100

        plot_data = []
        for nut_date_str, nut_total in nutrition_data:
            nut_date = datetime.strptime(nut_date_str, "%Y-%m-%d")
            if nut_date in weight_changes:
                plot_data.append((float(nut_total), weight_changes[nut_date]))

        if not plot_data:
            return

        x_vals = [p[0] for p in plot_data]
        y_vals = [p[1] for p in plot_data]

        for x, y in plot_data:
            self.scatter.append(x, y)

        if len(x_vals) > 1:
            coeffs = np.polyfit(x_vals, y_vals, 1)
            trend_func = np.poly1d(coeffs)
            min_x, max_x = min(x_vals), max(x_vals)
            self.trend.append(min_x, trend_func(min_x))
            self.trend.append(max_x, trend_func(max_x))

            x_pad = (max_x - min_x) * 0.1
            y_pad = (max(y_vals) - min(y_vals)) * 0.2
            self.x_axis.setRange(min_x - x_pad, max_x + x_pad)
            self.y_axis.setRange(min(y_vals) - y_pad, max(y_vals) + y_pad)

            correlation = np.corrcoef(x_vals, y_vals)[0, 1]
            self.setTitle(f"Nutrition vs Weight Change (r = {correlation:.2f})")

class MedicationTab(QWidget):
    def __init__(self, db):
        """
        db is your existing KittenDatabase instance
        """
        super().__init__()
        self.db = db
        self._ensure_table_exists()
        self.setStyleSheet("background: #1E1E1E; color: white;")
        self.layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Medication Manager")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.layout.addWidget(title_label)

        # Animal picker
        animal_layout = QHBoxLayout()
        animal_layout.addWidget(QLabel("Animal:"))
        self.animal_combo = QComboBox()
        animal_layout.addWidget(self.animal_combo)
        animal_layout.addStretch()
        self.layout.addLayout(animal_layout)

        # Form to add new medication
        form_layout = QHBoxLayout()
        self.med_name_input = QLineEdit()
        self.med_name_input.setPlaceholderText("Medication Name")
        self.med_name_input.setStyleSheet("background: #333; color: white;")

        self.start_date_input = QDateEdit(calendarPopup=True)
        self.start_date_input.setDate(QDate.currentDate())
        self.start_date_input.setStyleSheet("background: #333; color: white;")

        self.frequency_input = QLineEdit()
        self.frequency_input.setPlaceholderText("Frequency (e.g. daily)")
        self.frequency_input.setStyleSheet("background: #333; color: white;")

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes")
        self.notes_input.setStyleSheet("background: #333; color: white;")

        self.add_button = QPushButton("Add Medication")
        self.add_button.setStyleSheet("background: #4CAF50; color: white;")
        self.add_button.clicked.connect(self.add_medication)

        form_layout.addWidget(self.med_name_input)
        form_layout.addWidget(self.start_date_input)
        form_layout.addWidget(self.frequency_input)
        form_layout.addWidget(self.notes_input)
        form_layout.addWidget(self.add_button)
        self.layout.addLayout(form_layout)

        # Table to display medications
        self.med_table = QTableWidget()
        self.med_table.setColumnCount(5)
        self.med_table.setHorizontalHeaderLabels(["Name", "Start Date", "Frequency", "Notes", "Actions"])
        self.med_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.med_table.setStyleSheet("background: #2E2E2E;")
        self.med_table.setSortingEnabled(False)
        self.layout.addWidget(self.med_table)

        # Populate animal combo & signals
        self.refresh_animals()
        self.animal_combo.currentIndexChanged.connect(self.load_medications)

    def _ensure_table_exists(self):
        """
        Creates the 'medications' table if it does not exist.
        """
        create_query = """
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id INTEGER REFERENCES animals(id) ON DELETE CASCADE,
                med_name TEXT NOT NULL,
                start_date DATE NOT NULL,
                frequency TEXT,
                notes TEXT
            )
        """
        self.db._exec(create_query)

    def refresh_animals(self):
        self.animal_combo.clear()
        rows = self.db.conn.cursor().execute("SELECT id, name FROM animals").fetchall()
        for animal_id, name in rows:
            self.animal_combo.addItem(name, animal_id)
        if rows:
            self.animal_combo.setCurrentIndex(0)
            self.load_medications()

    def current_animal_id(self):
        if self.animal_combo.currentIndex() == -1:
            return None
        return self.animal_combo.currentData()

    def add_medication(self):
        """
        Inserts a new medication record for the currently selected animal.
        """
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "No Animal", "Please select an animal first.")
            return

        med_name = self.med_name_input.text().strip()
        start_date = self.start_date_input.date().toString("yyyy-MM-dd")
        frequency = self.frequency_input.text().strip()
        notes = self.notes_input.text().strip()

        if not med_name:
            QMessageBox.warning(self, "Invalid Input", "Medication name cannot be empty.")
            return

        insert_query = """
            INSERT INTO medications (animal_id, med_name, start_date, frequency, notes)
            VALUES (?, ?, ?, ?, ?)
        """
        success = self.db._exec(insert_query, (animal_id, med_name, start_date, frequency, notes))
        if success:
            self.med_name_input.clear()
            self.frequency_input.clear()
            self.notes_input.clear()
            self.load_medications()
            QMessageBox.information(self, "Medication Added", "Medication record created successfully!")
        else:
            QMessageBox.warning(self, "Error", "Failed to add medication record.")

    def load_medications(self):
        """
        Loads medication entries into the table for the selected animal.
        """
        animal_id = self.current_animal_id()
        if not animal_id:
            self.med_table.setRowCount(0)
            return

        cursor = self.db.conn.cursor()
        rows = cursor.execute("""
            SELECT id, med_name, start_date, frequency, notes
            FROM medications
            WHERE animal_id=?
            ORDER BY start_date DESC
        """, (animal_id,)).fetchall()

        self.med_table.setRowCount(0)
        for row_idx, (record_id, med_name, start_date, frequency, notes) in enumerate(rows):
            self.med_table.insertRow(row_idx)

            self.med_table.setItem(row_idx, 0, QTableWidgetItem(med_name))
            self.med_table.setItem(row_idx, 1, QTableWidgetItem(str(start_date)))
            self.med_table.setItem(row_idx, 2, QTableWidgetItem(frequency))
            self.med_table.setItem(row_idx, 3, QTableWidgetItem(notes))

            # Action cell (delete button)
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background: #F44336; color: white;")
            delete_btn.clicked.connect(lambda _, rid=record_id: self.delete_medication(rid))

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.addWidget(delete_btn)
            cell_layout.addStretch()
            cell_widget.setLayout(cell_layout)

            self.med_table.setCellWidget(row_idx, 4, cell_widget)

    def delete_medication(self, record_id):
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this medication record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            query = "DELETE FROM medications WHERE id=?"
            if self.db._exec(query, (record_id,)):
                QMessageBox.information(self, "Deleted", "Medication record deleted.")
                self.load_medications()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete record.")


class VaccinationTab(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._ensure_table_exists()
        self.setStyleSheet("background: #1E1E1E; color: white;")

        self.layout = QVBoxLayout(self)
        title_label = QLabel("Vaccination Records")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.layout.addWidget(title_label)

        # Animal selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Animal:"))
        self.animal_combo = QComboBox()
        select_layout.addWidget(self.animal_combo)
        select_layout.addStretch()
        self.layout.addLayout(select_layout)

        # Form to add vaccination records
        form_layout = QHBoxLayout()
        self.vax_name_input = QLineEdit()
        self.vax_name_input.setPlaceholderText("Vaccine Name")
        self.vax_name_input.setStyleSheet("background: #333; color: white;")

        self.date_admin_input = QDateEdit(calendarPopup=True)
        self.date_admin_input.setDate(QDate.currentDate())
        self.date_admin_input.setStyleSheet("background: #333; color: white;")

        self.date_due_input = QDateEdit(calendarPopup=True)
        self.date_due_input.setDate(QDate.currentDate().addMonths(6))
        self.date_due_input.setStyleSheet("background: #333; color: white;")

        self.vax_notes_input = QLineEdit()
        self.vax_notes_input.setPlaceholderText("Notes")
        self.vax_notes_input.setStyleSheet("background: #333; color: white;")

        self.add_btn = QPushButton("Add Vaccination")
        self.add_btn.setStyleSheet("background: #4CAF50; color: white;")
        self.add_btn.clicked.connect(self.add_vaccination)

        form_layout.addWidget(self.vax_name_input)
        form_layout.addWidget(self.date_admin_input)
        form_layout.addWidget(self.date_due_input)
        form_layout.addWidget(self.vax_notes_input)
        form_layout.addWidget(self.add_btn)
        self.layout.addLayout(form_layout)

        # Table for vaccinations
        self.vax_table = QTableWidget()
        self.vax_table.setColumnCount(5)
        self.vax_table.setHorizontalHeaderLabels(["Vaccine", "Date Administered", "Next Due", "Notes", "Actions"])
        self.vax_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.vax_table.setStyleSheet("background: #2E2E2E;")
        self.layout.addWidget(self.vax_table)

        # Load animals & signals
        self.refresh_animals()
        self.animal_combo.currentIndexChanged.connect(self.load_vaccinations)

    def _ensure_table_exists(self):
        create_query = """
            CREATE TABLE IF NOT EXISTS vaccinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id INTEGER REFERENCES animals(id) ON DELETE CASCADE,
                vaccine_name TEXT NOT NULL,
                date_admin DATE NOT NULL,
                date_due DATE,
                notes TEXT
            )
        """
        self.db._exec(create_query)

    def refresh_animals(self):
        self.animal_combo.clear()
        rows = self.db.conn.cursor().execute("SELECT id, name FROM animals").fetchall()
        for animal_id, name in rows:
            self.animal_combo.addItem(name, animal_id)
        if rows:
            self.animal_combo.setCurrentIndex(0)
            self.load_vaccinations()

    def current_animal_id(self):
        if self.animal_combo.currentIndex() == -1:
            return None
        return self.animal_combo.currentData()

    def add_vaccination(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "No Animal", "Select an animal to add vaccinations.")
            return

        vax_name = self.vax_name_input.text().strip()
        date_admin = self.date_admin_input.date().toString("yyyy-MM-dd")
        date_due = self.date_due_input.date().toString("yyyy-MM-dd")
        notes = self.vax_notes_input.text().strip()

        if not vax_name:
            QMessageBox.warning(self, "Error", "Vaccine name cannot be empty.")
            return

        insert_query = """
            INSERT INTO vaccinations (animal_id, vaccine_name, date_admin, date_due, notes)
            VALUES (?, ?, ?, ?, ?)
        """
        success = self.db._exec(insert_query, (animal_id, vax_name, date_admin, date_due, notes))
        if success:
            self.vax_name_input.clear()
            self.vax_notes_input.clear()
            self.load_vaccinations()
            QMessageBox.information(self, "Vaccination Added", "Vaccine record added!")
        else:
            QMessageBox.warning(self, "Error", "Failed to add vaccination record.")

    def load_vaccinations(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            self.vax_table.setRowCount(0)
            return

        cursor = self.db.conn.cursor()
        rows = cursor.execute("""
            SELECT id, vaccine_name, date_admin, date_due, notes
            FROM vaccinations
            WHERE animal_id=?
            ORDER BY date_admin DESC
        """, (animal_id,)).fetchall()

        self.vax_table.setRowCount(0)
        for i, (rec_id, name, d_admin, d_due, notes) in enumerate(rows):
            self.vax_table.insertRow(i)

            self.vax_table.setItem(i, 0, QTableWidgetItem(name))
            self.vax_table.setItem(i, 1, QTableWidgetItem(d_admin))
            self.vax_table.setItem(i, 2, QTableWidgetItem(d_due))
            self.vax_table.setItem(i, 3, QTableWidgetItem(notes))

            # Action cell with delete
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background: #F44336; color: white;")
            delete_btn.clicked.connect(lambda _, rid=rec_id: self.delete_vaccination(rid))

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.addWidget(delete_btn)
            cell_layout.addStretch()
            cell_widget.setLayout(cell_layout)
            self.vax_table.setCellWidget(i, 4, cell_widget)

    def delete_vaccination(self, rec_id):
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this vaccination record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            query = "DELETE FROM vaccinations WHERE id=?"
            if self.db._exec(query, (rec_id,)):
                QMessageBox.information(self, "Deleted", "Vaccination record deleted.")
                self.load_vaccinations()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete record.")


class GrowthChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Weight Growth")

        self.scatter = QScatterSeries()
        self.scatter.setName("Measurements")
        self.scatter.setColor(QColor("#4CAF50"))
        self.scatter.setMarkerSize(10)

        self.trend = QLineSeries()
        self.trend.setName("Trend Line")
        self.trend.setPen(QPen(QColor("#26C6DA"), 2, Qt.PenStyle.DashLine))

        self.addSeries(self.scatter)
        self.addSeries(self.trend)

        self.x_axis = QDateTimeAxis()
        self.y_axis = QValueAxis()
        self.x_axis.setTitleText("Date")
        self.y_axis.setTitleText("Weight (kg)")
        self.x_axis.setFormat("MMM d")

        self.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)

        self.scatter.attachAxis(self.x_axis)
        self.scatter.attachAxis(self.y_axis)
        self.trend.attachAxis(self.x_axis)
        self.trend.attachAxis(self.y_axis)

    def update_chart(self, data, unit='kg'):
        self.scatter.clear()
        self.trend.clear()

        if not data:
            self.x_axis.setRange(QDateTime.currentDateTime().addMonths(-1), QDateTime.currentDateTime())
            self.y_axis.setRange(0, 10)
            return

        conversion = 2.20462 if unit == 'lbs' else 1
        x_vals = []
        y_vals = []

        for date_str, weight, _ in data:
            dt = QDateTime.fromString(date_str, "yyyy-MM-dd")
            adj_weight = weight * conversion
            self.scatter.append(dt.toMSecsSinceEpoch(), adj_weight)
            x_vals.append(dt.toMSecsSinceEpoch())
            y_vals.append(adj_weight)

        if len(data) > 1:
            coeffs = np.polyfit(x_vals, y_vals, 1)
            trend_func = np.poly1d(coeffs)
            self.trend.append(
                QDateTime.fromString(data[0][0], "yyyy-MM-dd").toMSecsSinceEpoch(),
                trend_func(x_vals[0])
            )
            self.trend.append(
                QDateTime.fromString(data[-1][0], "yyyy-MM-dd").toMSecsSinceEpoch(),
                trend_func(x_vals[-1])
            )

        self.y_axis.setTitleText(f'Weight ({unit})')
        self.x_axis.setRange(
            QDateTime.fromString(data[0][0], "yyyy-MM-dd"),
            QDateTime.fromString(data[-1][0], "yyyy-MM-dd")
        )
        self.y_axis.applyNiceNumbers()

        

class NutritionChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Daily Nutrition Intake")

        self.bars = QBarSeries()
        self.bars.setLabelsVisible(True)
        self.addSeries(self.bars)

        self.goal_line = QLineSeries()
        self.goal_line.setPen(QPen(QColor("#FF5252"), 2, Qt.PenStyle.DashLine))
        self.addSeries(self.goal_line)

        self.x_axis = QBarCategoryAxis()
        self.y_axis = QValueAxis()
        self.y_axis.setTitleText("Grams")

        self.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)

        self.bars.attachAxis(self.x_axis)
        self.bars.attachAxis(self.y_axis)
        self.goal_line.attachAxis(self.x_axis)
        self.goal_line.attachAxis(self.y_axis)

    def update_chart(self, data, goal=80):
        self.bars.clear()
        self.goal_line.clear()

        if not data:
            self.x_axis.clear()
            self.y_axis.setRange(0, 100)
            return

        bar_set = QBarSet("Intake")
        bar_set.setColor(QColor("#26C6DA"))

        categories = []
        amounts = []
        max_val = goal

        for date_str, total in data:
            categories.append(date_str)
            clean_total = round(float(total))
            amounts.append(clean_total)
            if clean_total > max_val:
                max_val = clean_total

        bar_set.append(amounts)
        self.bars.append(bar_set)

        self.x_axis.setCategories(categories)
        self.y_axis.setRange(0, max_val * 1.2)

        if categories:
            self.goal_line.append(0, goal)
            self.goal_line.append(len(categories) - 1, goal)


class DatabaseResetHelper:
    def __init__(self, db):
        """
        db is your existing KittenDatabase instance
        """
        self.db = db

    def force_recreate_tables(self):
        """
        Drops the old tables completely, then recreates them using
        KittenDatabase._create_tables(). All data is lost!
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS diet_logs")
            cursor.execute("DROP TABLE IF EXISTS weight_data")
            cursor.execute("DROP TABLE IF EXISTS animals")
            self.db.conn.commit()

            self.db._create_tables()
            QMessageBox.information(None, "Tables Recreated", 
                "All tables dropped and recreated successfully!")
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(None, "Error", f"Failed to recreate tables: {str(e)}")



# ================= MAIN APP (PARTIAL) =================
class KittenTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.production_mode = True
        try:
            self.db = KittenDatabase(production=self.production_mode)
            self.unit = 'kg'
            self.nutrition_goal = 80

            self.tab_config_path = self.db.get_data_folder() / "tab_order.json"

            self.setup_ui()
            self._refresh_animal_list()
            self.setWindowIcon(self.generate_random_icon())
            self.setWindowTitle(self.random_window_title())
            self._add_database_menu()

            self._load_tab_order()
        except Exception as e:
            QMessageBox.critical(None, "Startup Failed", f"Application failed to start: {str(e)}")
            sys.exit(1)

    def _add_database_menu(self):
        db_menu = self.menuBar().addMenu("Database")
        db_menu.addAction("Open Data Folder", self.open_data_folder)
        db_menu.addAction("Clear Test Data", self.clear_test_data_confirm)
        db_menu.addSeparator()
        db_menu.addAction("Exit", self.close)

        dev_menu = self.menuBar().addMenu("Developer")
        self.dev_mode = dev_menu.addAction("Development Mode")
        self.dev_mode.setCheckable(True)
        self.dev_mode.triggered.connect(lambda: self.toggle_dev_mode(self.dev_mode.isChecked()))

        self.randomize_ui = dev_menu.addAction("Randomize UI")
        self.randomize_ui.triggered.connect(lambda: [
            self.setWindowIcon(self.generate_random_icon()),
            self.setWindowTitle(self.random_window_title())
        ])

    def open_data_folder(self):
        path = self.db.get_data_folder()
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Open Failed", f"Couldn't open folder: {str(e)}")

    def clear_test_data_confirm(self):
        confirm = QMessageBox.question(
            self, "Confirm Clear",
            "This will DELETE ALL DATA!\nAre you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.db.clear_test_data()
                self.load_data()
                QMessageBox.information(self, "Success", "All data cleared successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear data: {str(e)}")

    def generate_random_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        painter.setBrush(bg_color)

        shape = random.choice(["circle", "square", "triangle"])
        if shape == "circle":
            painter.drawEllipse(4, 4, 56, 56)
        elif shape == "square":
            painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        else:
            poly = QPolygon([QPoint(32, 8), QPoint(58, 56), QPoint(6, 56)])
            painter.drawPolygon(poly)

        emojis = random.sample(
            ["😺", "🐾", "🐱", "🎀", "🦴", "🍗", "🐟", "🥛", "🌟", "⚡", "❤️", "🌈", "🍎", "🐭", "🧶", "🎈"],
            2
        )
        font = painter.font()
        font.setPointSize(24)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        for i, emoji in enumerate(emojis):
            painter.drawText(
                random.randint(8, 32),
                random.randint(32, 48) + i * 16,
                emoji
            )

        painter.end()
        return QIcon(pixmap)

    def random_window_title(self):
        adjectives = ["Fluffy", "Playful", "Majestic", "Cuddly", "Adorable"]
        nouns = ["Companion", "Friend", "Pal", "Buddy", "Maine Coon"]
        return f"{random.choice(adjectives)} {random.choice(nouns)} Tracker 🐾"

    def setup_ui(self):
        self.setWindowTitle("Animal Tracker 🐾")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet("background: #1E1E1E; color: white;")

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.tabBar().tabMoved.connect(self._on_tab_moved)
        self.setCentralWidget(self.tabs)

        # Dashboard
        self.dash_tab = QWidget()
        self.dash_tab.setObjectName("DashboardTab")
        layout = QVBoxLayout(self.dash_tab)

        stats = QHBoxLayout()
        self.current_weight = self._create_card("Current Weight", "N/A", "#4CAF50")
        self.weekly_gain = self._create_card("Weekly Trend", "N/A", "#26C6DA")
        self.age_card = self._create_card("Age", "N/A", "#7E57C2")
        stats.addWidget(self.current_weight)
        stats.addWidget(self.weekly_gain)
        stats.addWidget(self.age_card)

        goal_layout = QHBoxLayout()
        goal_layout.addWidget(QLabel("Daily Goal:"))
        self.goal_input = QLineEdit("80")
        self.goal_input.setFixedWidth(80)
        self.goal_input.setValidator(QDoubleValidator(1, 999, 0))
        self.goal_input.setStyleSheet("background: #333; color: white;")
        self.goal_input.editingFinished.connect(self.update_goal)
        goal_layout.addWidget(self.goal_input)
        goal_layout.addWidget(QLabel("grams"))
        stats.addLayout(goal_layout)

        chart_layout = QHBoxLayout()
        self.growth_chart = QChartView(GrowthChart())
        self.nutrition_chart = QChartView(NutritionChart())
        self.health_chart = QChartView(HealthCorrelationChart())

        for chart in [self.growth_chart, self.nutrition_chart, self.health_chart]:
            chart.setMinimumSize(400, 300)

        chart_layout.addWidget(self.growth_chart)
        chart_layout.addWidget(self.nutrition_chart)
        chart_layout.addWidget(self.health_chart)

        layout.addLayout(stats)
        layout.addLayout(chart_layout)
        self.tabs.addTab(self.dash_tab, "📈 Dashboard")

        # Weight tab
        self.weight_tab = QWidget()
        self.weight_tab.setObjectName("WeightTab")
        weight_layout = QVBoxLayout(self.weight_tab)

        form = QHBoxLayout()
        self.date_input = QDateEdit(calendarPopup=True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setMaximumDate(QDate.currentDate())
        self.weight_input = QLineEdit(placeholderText="Weight")
        self.weight_input.setValidator(QDoubleValidator(0.1, 50.0, 2))
        self.notes_input = QLineEdit(placeholderText="Notes")
        self.add_weight_btn = QPushButton("➕ Add Entry", clicked=self.add_weight)

        for w in [self.date_input, self.weight_input, self.notes_input, self.add_weight_btn]:
            form.addWidget(w)

        self.weight_table = self._create_table(["Date", "Weight", "Notes"])
        weight_layout.addLayout(form)
        weight_layout.addWidget(self.weight_table)
        self.tabs.addTab(self.weight_tab, "⚖️ Weight")

        # Meals tab
        self.diet_tab = QWidget()
        self.diet_tab.setObjectName("DietTab")
        diet_layout = QVBoxLayout(self.diet_tab)

        form = QHBoxLayout()
        self.meal_type = QComboBox()
        self.meal_type.addItems(["Breakfast 🍳", "Lunch 🥩", "Dinner 🍗", "Snack 🥛"])
        self.food_input = QLineEdit(placeholderText="Food item")
        self.brand_input = QLineEdit(placeholderText="Brand")
        self.amount_input = QLineEdit(placeholderText="Grams")
        self.amount_input.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.log_meal_btn = QPushButton("📝 Log Meal", clicked=self.log_meal)

        for w in [self.meal_type, self.food_input, self.brand_input, self.amount_input, self.log_meal_btn]:
            form.addWidget(w)

        self.diet_table = self._create_table(["Timestamp", "Meal Type", "Food", "Brand", "Amount (g)", "Notes"])
        diet_layout.addLayout(form)
        diet_layout.addWidget(self.diet_table)
        self.tabs.addTab(self.diet_tab, "🍴 Meals")

        status = self.statusBar()
        self.animal_combo = QComboBox()
        self.animal_combo.currentIndexChanged.connect(self.update_meal_types)
        self.add_animal_btn = QPushButton("➕ New Animal", clicked=self.add_animal)
        self.unit_btn = QPushButton("Switch to lbs", clicked=self.toggle_units)
        self.export_btn = QPushButton("💾 Export CSV", clicked=self.export_data)
        self.backup_btn = QPushButton("💾 Backup", clicked=self.db.create_backup)

        status.addPermanentWidget(QLabel("Current Animal:"))
        status.addPermanentWidget(self.animal_combo)
        status.addPermanentWidget(self.add_animal_btn)
        status.addPermanentWidget(self.unit_btn)
        status.addPermanentWidget(self.export_btn)
        status.addPermanentWidget(self.backup_btn)

        self.test_btn = QPushButton("🧪 Generate Test Data", clicked=self.create_test_data)
        self.clear_btn = QPushButton("🗑️ Clear Data", clicked=self.clear_test_data)
        for btn in [self.test_btn, self.clear_btn]:
            btn.setStyleSheet("background: #FFA726; padding: 5px;")
            status.addPermanentWidget(btn)

    def _on_tab_moved(self, old_index, new_index):
        self._save_tab_order()

    def _save_tab_order(self):
        import json
        tab_count = self.tabs.count()
        order = []
        for i in range(tab_count):
            w = self.tabs.widget(i)
            order.append(w.objectName())

        data = {"tab_order": order}
        try:
            with open(self.tab_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Could not save tab order: {str(e)}")

    def _load_tab_order(self):
        import json
        if not self.tab_config_path.exists():
            return
        try:
            with open(self.tab_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_order = data.get("tab_order", [])
        except Exception as e:
            print(f"Could not load tab order: {str(e)}")
            return

        name_to_index = {}
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            name_to_index[w.objectName()] = i

        for i, obj_name in enumerate(saved_order):
            if obj_name not in name_to_index:
                continue
            current_index = self.tabs.indexOf(self.tabs.findChild(QWidget, obj_name))
            if current_index != -1 and current_index != i:
                self.tabs.tabBar().moveTab(current_index, i)

            name_to_index.clear()
            for j in range(self.tabs.count()):
                w = self.tabs.widget(j)
                name_to_index[w.objectName()] = j

    def _create_table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet("background: #2E2E2E;")
        table.setSortingEnabled(True)
        return table

    def _create_card(self, title, value, color):
        card = QWidget(styleSheet=f"background: {color}; border-radius: 10px; padding: 15px;")
        layout = QVBoxLayout(card)
        layout.addWidget(QLabel(title, styleSheet="color: rgba(255,255,255,0.8); font-size: 16px;"))
        value_label = QLabel(value, styleSheet="color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)
        return card

    def load_data(self):
        animal_id = self.current_animal_id()
        self.weight_table.setUpdatesEnabled(False)
        self.diet_table.setUpdatesEnabled(False)

        try:
            self.weight_table.setRowCount(0)
            self.diet_table.setRowCount(0)

            if not animal_id:
                self._show_empty_state()
                return

            weight_data = self.db.get_weight_data(animal_id)
            for date, weight, notes in weight_data:
                row = self.weight_table.rowCount()
                self.weight_table.insertRow(row)
                self.weight_table.setItem(row, 0, DateTimeTableWidgetItem(date))
                self.weight_table.setItem(row, 1, QTableWidgetItem(f"{weight:.2f}"))
                self.weight_table.setItem(row, 2, QTableWidgetItem(notes))

            diet_logs = self.db.get_diet_logs(animal_id)
            for record in diet_logs:
                # record => (timestamp, meal_type, food_item, brand, amount, notes)
                row = self.diet_table.rowCount()
                self.diet_table.insertRow(row)
                self.diet_table.setItem(row, 0, DateTimeTableWidgetItem(record[0]))
                self.diet_table.setItem(row, 1, QTableWidgetItem(record[1]))
                self.diet_table.setItem(row, 2, QTableWidgetItem(record[2]))
                self.diet_table.setItem(row, 3, QTableWidgetItem(record[3]))
                self.diet_table.setItem(row, 4, QTableWidgetItem(f"{record[4]:.1f} g"))
                self.diet_table.setItem(row, 5, QTableWidgetItem(record[5]))

            self.growth_chart.chart().update_chart(weight_data, self.unit)
            nutrition_data = self.db.get_daily_nutrition(animal_id)
            self.nutrition_chart.chart().update_chart(nutrition_data, self.nutrition_goal)
            self.health_chart.chart().update_chart(nutrition_data, weight_data)

            if weight_data:
                current_weight = weight_data[-1][1] * (2.20462 if self.unit == 'lbs' else 1)
                self.current_weight.layout().itemAt(1).widget().setText(f"{current_weight:.2f} {self.unit}")

                if len(weight_data) > 7:
                    weekly_gain = (weight_data[-1][1] - weight_data[-8][1]) \
                                  * (2.20462 if self.unit == 'lbs' else 1)
                    self.weekly_gain.layout().itemAt(1).widget().setText(f"{weekly_gain:+.2f} {self.unit}")

            animal_info = self.db.conn.cursor().execute(
                "SELECT birthdate FROM animals WHERE id=?", (animal_id,)
            ).fetchone()
            if animal_info and animal_info[0]:
                try:
                    birthdate = QDate.fromString(animal_info[0], "yyyy-MM-dd")
                    age_days = birthdate.daysTo(QDate.currentDate())
                    years = age_days // 365
                    days = age_days % 365
                    age_text = f"{years}y {days}d" if years > 0 else f"{days}d"
                    self.age_card.layout().itemAt(1).widget().setText(age_text)
                except:
                    self.age_card.layout().itemAt(1).widget().setText("N/A")

        finally:
            self.weight_table.setUpdatesEnabled(True)
            self.diet_table.setUpdatesEnabled(True)
            self.weight_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
            self.diet_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _show_empty_state(self):
        self.weight_table.setRowCount(0)
        self.diet_table.setRowCount(0)
        self.current_weight.layout().itemAt(1).widget().setText("N/A")
        self.weekly_gain.layout().itemAt(1).widget().setText("N/A")
        self.age_card.layout().itemAt(1).widget().setText("N/A")
        self.growth_chart.chart().update_chart([], self.unit)
        self.nutrition_chart.chart().update_chart([], self.nutrition_goal)
        QMessageBox.information(self, "No Animal", "Please select or add an animal to continue")

    def toggle_units(self):
        self.unit = 'lbs' if self.unit == 'kg' else 'kg'
        self.unit_btn.setText(f"Switch to {'kg' if self.unit == 'lbs' else 'lbs'}")
        self.load_data()

    def add_weight(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "Error", "Select an animal first!")
            return

        try:
            date = self.date_input.date().toString("yyyy-MM-dd")
            weight = float(self.weight_input.text())
            notes = self.notes_input.text()

            if self.db.add_weight(animal_id, date, weight, notes):
                self.load_data()
                self.weight_input.clear()
                self.notes_input.clear()
                self._flash_table_row(self.weight_table, 0)
            else:
                QMessageBox.warning(self, "Error", "Duplicate entry for this date!")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid weight")

    def log_meal(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "Error", "Select an animal first!")
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meal_type = self.meal_type.currentText()
            food = self.food_input.text().strip() or "Generic Food"
            brand = self.brand_input.text().strip() or "No Brand"
            amount = float(self.amount_input.text())

            if self.db.add_meal(animal_id, timestamp, meal_type, food, brand, amount):
                self.load_data()
                self.food_input.clear()
                self.brand_input.clear()
                self.amount_input.clear()
                self._flash_table_row(self.diet_table, 0)
            else:
                QMessageBox.warning(self, "Error", "Failed to save meal!")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Enter valid amount")

    def _flash_table_row(self, table, row):
        table.scrollToItem(table.item(row, 0))
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setBackground(QColor("#4CAF50"))
        QTimer.singleShot(300, lambda: self._reset_table_colors(table, row))

    def _reset_table_colors(self, table, row):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setBackground(QColor("#2E2E2E"))

    def update_goal(self):
        try:
            self.nutrition_goal = float(self.goal_input.text())
            self.load_data()
        except ValueError:
            QMessageBox.warning(self, "Invalid Goal", "Please enter a valid number")

    def add_animal(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Animal")
        layout = QVBoxLayout()

        name_input = QLineEdit(placeholderText="Name")
        type_input = QComboBox()
        type_input.addItems(["Cat", "Dog", "Other"])
        birthdate_input = QDateEdit(calendarPopup=True)
        birthdate_input.setDate(QDate.currentDate())

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)

        layout.addWidget(QLabel("Name:"))
        layout.addWidget(name_input)
        layout.addWidget(QLabel("Type:"))
        layout.addWidget(type_input)
        layout.addWidget(QLabel("Birthdate:"))
        layout.addWidget(birthdate_input)
        layout.addWidget(btn_box)
        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted and name_input.text().strip():
            self.db._exec(
                "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
                (name_input.text(), type_input.currentText(),
                 birthdate_input.date().toString("yyyy-MM-dd"))
            )
            self._refresh_animal_list()

    def _refresh_animal_list(self):
        self.animal_combo.clear()
        animals = self.db.conn.cursor().execute("SELECT id, name FROM animals").fetchall()
        for animal_id, name in animals:
            self.animal_combo.addItem(name, animal_id)
        if animals:
            self.animal_combo.setCurrentIndex(0)
            self.load_data()

    def current_animal_id(self):
        if self.animal_combo.currentIndex() == -1:
            return None
        return self.animal_combo.currentData()

    def update_meal_types(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            return
        row = self.db.conn.cursor().execute(
            "SELECT animal_type FROM animals WHERE id=?", (animal_id,)
        ).fetchone()
        if not row:
            return

        animal_type = row[0]
        self.meal_type.clear()
        if animal_type == "Cat":
            self.meal_type.addItems(["Wet Food 🐟", "Dry Food 🥣", "Treat 🍗", "Medicine 💊"])
        elif animal_type == "Dog":
            self.meal_type.addItems(["Kibble 🦴", "Raw Meat 🥩", "Dental Chew 🦷", "Puppy Formula"])
        else:
            self.meal_type.addItems(["Regular Meal", "Special Diet", "Vitamin", "Custom Feed"])

    def toggle_dev_mode(self, enabled):
        if enabled:
            QMessageBox.information(self, "Dev Mode On", "Now using dev DB.")
            self.db.conn.close()
            self.db = KittenDatabase(production=False)
        else:
            QMessageBox.information(self, "Dev Mode Off", "Now using production DB.")
            self.db.conn.close()
            self.db = KittenDatabase(production=True)
        self._refresh_animal_list()

    def create_test_data(self):
        try:
            self.db.clear_test_data()
            cursor = self.db.conn.cursor()

            # Insert a single test animal
            cursor.execute(
                "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
                ("Whiskers", "Cat", "2022-06-15")
            )
            animal_id = cursor.lastrowid

            base_date = datetime.now() - timedelta(days=365)
            max_weight = 4.2
            growth_rate = 0.015
            midpoint_day = 180
            seasonal_amplitude = 0.15
            weekly_noise = 0.03

            for day in range(365):
                logistic = max_weight / (1 + np.exp(-growth_rate * (day - midpoint_day)))
                seasonal = 1 + seasonal_amplitude * np.sin(day / 58)
                weekly = 1 + 0.05 * np.sin(day / 3.5)
                noise = 1 + random.uniform(-weekly_noise, weekly_noise)
                weight = logistic * seasonal * weekly * noise
                date_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                note = self._generate_weight_note(day, weight)
                self.db.add_weight(animal_id, date_str, round(weight, 3), note)

            meal_types = {
                "Morning Meal 🍳": {
                    "times": (7, 9),
                    "foods": [
                        ("Chicken Pâté", 30, "Fancy Feast"),
                        ("Salmon Flakes", 40, "Blue Buffalo"),
                        ("Kitten Formula", 35, "Vet Recommended")
                    ],
                    "notes": [
                        "Ate enthusiastically",
                        "Left some crumbs",
                        "Finished quickly",
                        "Played with food first"
                    ]
                },
                "Afternoon Snack 🥩": {
                    "times": (12, 14),
                    "foods": [
                        ("Tuna Treat", 15, "Delectables"),
                        ("Dental Chew", 10, "Greenies"),
                        ("Chicken Jerky", 20, "PureBites")
                    ],
                    "notes": [
                        "Midday munchies",
                        "Shared with neighbor cat",
                        "Ate while birdwatching",
                        "Left some for later"
                    ]
                },
                "Evening Feast 🍗": {
                    "times": (17, 19),
                    "foods": [
                        ("Turkey Dinner", 60, "Wellness Core"),
                        ("Salmon Supper", 55, "Instinct"),
                        ("Weight Management", 50, "Hill's Science Diet")
                    ],
                    "notes": [
                        "Cleaned the bowl!",
                        "Begged for seconds",
                        "Ate while purring",
                        "Took a nap after"
                    ]
                },
                "Night Cap 🥛": {
                    "times": (21, 23),
                    "foods": [
                        ("Catnip Tea", 5, "Organic"),
                        ("Lickable Treat", 10, "Churu"),
                        ("Warm Goat Milk", 15, "Homemade")
                    ],
                    "notes": [
                        "Bedtime ritual",
                        "Midnight craving",
                        "Dreamy nibbles",
                        "Moonlight snack"
                    ]
                }
            }

            special_dates = {
                "2023-12-25": "Christmas Extra Treat! 🎄",
                "2023-07-04": "Fireworks Anxiety Meal 💥",
                "2023-10-31": "Halloween Pumpkin Mix 🎃",
                "2023-03-17": "Green-Themed Food 🍀"
            }

            for day in range(365):
                current_date = base_date + timedelta(days=day)
                date_str = current_date.strftime("%Y-%m-%d")
                special_note = special_dates.get(date_str, None)

                for meal_name, details in meal_types.items():
                    hour = random.randint(details["times"][0], details["times"][1])
                    minute = random.randint(0, 59)
                    food, base_amount, brand = random.choice(details["foods"])
                    amount_variation = random.gauss(1, 0.1)
                    amount = round(base_amount * amount_variation, 1)
                    note_parts = [random.choice(details["notes"]), f"Weather: {self._random_weather()}"]
                    if special_note:
                        note_parts.append(special_note)
                    final_notes = " | ".join(note_parts)

                    timestamp = current_date.replace(hour=hour, minute=minute).strftime("%Y-%m-%d %H:%M:%S")
                    self.db.add_meal(
                        animal_id, timestamp, meal_name, food, brand, amount, notes=final_notes
                    )

                if date_str == "2023-06-15":
                    self.db.add_meal(
                        animal_id,
                        current_date.replace(hour=12, minute=0).strftime("%Y-%m-%d %H:%M:%S"),
                        "Birthday Feast 🎂",
                        "Special Salmon Cake",
                        "Homemade",
                        80,
                        "1st birthday celebration! 🥳"
                    )

            self.db.conn.commit()
            self._refresh_animal_list()
            self.load_data()
            QMessageBox.information(self, "Test Data Created", "Inserted 1-year cat data successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Test data failed: {str(e)}")

    def _generate_weight_note(self, day, weight):
        milestones = {
            30: "First month growth",
            90: "3-month adolescent surge",
            180: "6-month teenage phase",
            270: "9-month young adult",
            365: "1-year anniversary"
        }
        if day in milestones:
            return f"{milestones[day]} | Weight: {weight:.2f}kg"

        events = [
            ("Discovered birds", 0.15),
            ("New food introduced", 0.1),
            ("Playtime increase", 0.1),
            ("Vet visit", 0.05),
            ("Grooming session", 0.08)
        ]
        for event, prob in events:
            if random.random() < prob:
                return f"{event} | Weight: {weight:.2f}kg"
        return f"Daily check | Weight: {weight:.2f}kg"

    def _random_weather(self):
        seasons = [
            ("❄️ Winter", ["Snowy", "Frigid", "Icy", "Crisp"]),
            ("🌱 Spring", ["Rainy", "Misty", "Sunny", "Breezy"]),
            ("☀️ Summer", ["Hot", "Humid", "Stormy", "Dry"]),
            ("🍂 Fall", ["Cool", "Windy", "Foggy", "Chilly"])
        ]
        season_idx = (datetime.now().month % 12) // 3
        season = seasons[season_idx]
        return f"{season[0]} - {random.choice(season[1])}"

    def clear_test_data(self):
        self.db.clear_test_data()
        self.load_data()
        QMessageBox.information(self, "Data Cleared", "All test data was removed from the current DB.")

    def export_data(self):
        """
        Exports weight data to CSV, then shows a custom message box with "Open Folder" or "OK."
        """
        animal_id = self.current_animal_id()
        if not animal_id:
            return

        # We'll save the CSV in the same folder as the DB, just like before.
        filename = f"weight_data_{animal_id}.csv"
        csv_path = self.db.get_data_folder() / filename

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Weight', 'Notes'])
            writer.writerows(self.db.get_weight_data(animal_id))

        box = QMessageBox()
        box.setWindowTitle("Export Complete")
        box.setText(f"Data saved to {filename}")
        box.setIcon(QMessageBox.Icon.Information)

        open_folder = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)

        box.exec()

        if box.clickedButton() == open_folder:
            # Attempt to open the folder containing the CSV
            folder = self.db.get_data_folder()
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])







if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KittenTracker()
    window.show()
    sys.exit(app.exec())