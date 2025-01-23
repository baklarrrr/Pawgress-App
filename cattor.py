import sys
import random
import sqlite3
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDateTime, QDate
from PyQt6.QtGui import QColor, QDoubleValidator
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QTabWidget, QDateEdit, QComboBox)
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis

class KittenDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('kitten_tracker.db')
        self._exec('''CREATE TABLE IF NOT EXISTS weight_data 
                    (id INTEGER PRIMARY KEY, date TEXT UNIQUE, weight REAL, notes TEXT)''')
        self._exec('''CREATE TABLE IF NOT EXISTS diet_logs 
                    (id INTEGER PRIMARY KEY, timestamp TEXT, meal_type TEXT, food_item TEXT, amount REAL)''')

    def _exec(self, query, params=()):
        try:
            self.conn.cursor().execute(query, params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_weight_data(self):
        return self.conn.cursor().execute("SELECT date, weight, notes FROM weight_data ORDER BY date").fetchall()

    def get_diet_data(self):
        return self.conn.cursor().execute("SELECT timestamp, meal_type, food_item, amount FROM diet_logs ORDER BY timestamp").fetchall()

    def add_weight(self, date, weight, notes):
        return self._exec("INSERT OR IGNORE INTO weight_data (date, weight, notes) VALUES (?, ?, ?)", 
                         (date, weight, notes))

    def add_meal(self, timestamp, meal_type, food, amount):
        return self._exec("INSERT INTO diet_logs (timestamp, meal_type, food_item, amount) VALUES (?, ?, ?, ?)",
                         (timestamp, meal_type, food, amount))

    def clear_data(self):
        self._exec("DELETE FROM weight_data")
        self._exec("DELETE FROM diet_logs")

class GrowthChart(QChartView):
    def __init__(self):
        super().__init__()
        self.chart = QChart()
        self.setChart(self.chart)
        self.series = QLineSeries()
        self.series.setColor(QColor("#4CAF50"))
        self.chart.addSeries(self.series)
        self._setup_axes()

    def _setup_axes(self):
        self.x_axis = QDateTimeAxis()
        self.y_axis = QValueAxis()
        for axis in [self.x_axis, self.y_axis]:
            axis.setTitleBrush(QColor("#FFFFFF"))
            axis.setLabelsColor(QColor("#FFFFFF"))
        self.chart.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.x_axis)
        self.series.attachAxis(self.y_axis)
        self.x_axis.setFormat("MMM d")
        self.chart.setBackgroundBrush(QColor("#2E2E2E"))

    def update_chart(self, data, unit='kg'):
        self.series.clear()
        if not data: return
        
        dates = [datetime.strptime(d[0], "%Y-%m-%d") for d in data]
        weights = [d[1]*2.20462 if unit == 'lbs' else d[1] for d in data]
        
        for date, weight in zip(dates, weights):
            self.series.append(date.timestamp() * 1000, weight)
        
        self.x_axis.setRange(QDateTime(min(dates)), QDateTime(max(dates)))
        self.y_axis.setRange(min(weights)*0.95, max(weights)*1.05)
        self.y_axis.setTitleText(f"Weight ({unit})")

class KittenTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = KittenDatabase()
        self.unit = 'kg'
        self.setup_ui()
        self.load_data()
        self.toggle_dev_mode(False)

    def setup_ui(self):
        self.setWindowTitle("Maine Coon Tracker 🐾")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet("background: #1E1E1E; color: white;")
        
        # Main tabs
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # Dashboard Tab
        dash_tab = QWidget()
        self.setup_dashboard(dash_tab)
        tabs.addTab(dash_tab, "📈 Dashboard")
        
        # Setup other tabs
        tabs.addTab(self._create_weight_tab(), "⚖️ Weight")
        tabs.addTab(self._create_diet_tab(), "🍴 Meals")
        
        # Unit toggle
        self.unit_btn = QPushButton("Switch to lbs")
        self.unit_btn.clicked.connect(self.toggle_units)
        self.statusBar().addPermanentWidget(self.unit_btn)
        
        # Developer menu
        dev_menu = self.menuBar().addMenu("Developer")
        self.dev_mode = dev_menu.addAction("Development Mode")
        self.dev_mode.setCheckable(True)
        self.dev_mode.triggered.connect(lambda: self.toggle_dev_mode(self.dev_mode.isChecked()))

    def _create_weight_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Input form
        self.date_input = QDateEdit(calendarPopup=True)
        
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("Weight")
        self.weight_input.setValidator(QDoubleValidator(0.1, 99.9, 2))
        
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes")
        
        form = self._create_form([
            ("Date:", self.date_input),
            ("Weight:", self.weight_input),
            ("Notes:", self.notes_input),
            (None, self._create_btn("➕ Add Entry", self.add_weight))
        ])
        
        # Table
        self.weight_table = self._create_table(["Date", "Weight", "Notes"])
        layout.addLayout(form)
        layout.addWidget(self.weight_table)
        return tab

    def _create_diet_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.meal_type = QComboBox()
        self.meal_type.addItems(["Breakfast 🍳", "Lunch 🥩", "Dinner 🍗", "Snack 🥛"])
        
        food_input = QLineEdit()
        food_input.setPlaceholderText("Food item")
        
        amount_input = QLineEdit()
        amount_input.setPlaceholderText("Grams")
        amount_input.setValidator(QDoubleValidator(1, 9999, 1))
        
        form = self._create_form([
            ("Meal Type:", self.meal_type),
            ("Food:", food_input),
            ("Amount:", amount_input),
            (None, self._create_btn("📝 Log Meal", self.log_meal))
        ])
        
        self.diet_table = self._create_table(["Time", "Meal", "Food", "Amount"])
        layout.addLayout(form)
        layout.addWidget(self.diet_table)
        return tab

    def setup_dashboard(self, parent):
        layout = QVBoxLayout(parent)
        
        # Stats
        stats = QHBoxLayout()
        self.current_weight = self._create_card("Current Weight", "3.2 kg")
        self.weekly_gain = self._create_card("Weekly Gain", "+0.15 kg")
        stats.addWidget(self.current_weight)
        stats.addWidget(self.weekly_gain)
        
        # Charts
        self.chart = GrowthChart()
        layout.addLayout(stats)
        layout.addWidget(self.chart)

    def _create_form(self, fields):
        form = QHBoxLayout()
        for label, widget in fields:
            if label: form.addWidget(QLabel(label))
            form.addWidget(widget)
        return form

    def _create_btn(self, text, action):
        btn = QPushButton(text)
        btn.clicked.connect(action)
        btn.setStyleSheet("background: #4CAF50; padding: 8px;")
        return btn

    def _create_table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet("background: #2E2E2E;")
        return table

    def _create_card(self, title, value):
        card = QWidget(styleSheet="background: #2E2E2E; border-radius: 10px; padding: 15px;")
        layout = QVBoxLayout(card)
        layout.addWidget(QLabel(title, styleSheet="color: #888; font-size: 16px;"))
        layout.addWidget(QLabel(value, styleSheet="color: #4CAF50; font-size: 24px; font-weight: bold;"))
        return card

    def load_data(self):
        for table, data in [(self.weight_table, self.db.get_weight_data()),
                           (self.diet_table, self.db.get_diet_data())]:
            table.setRowCount(0)
            for row in data:
                self._add_table_row(table, row)
        self.chart.update_chart(self.db.get_weight_data(), self.unit)
        self.update_stats()

    def _add_table_row(self, table, data):
        row = table.rowCount()
        table.insertRow(row)
        for col, value in enumerate(data):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, col, item)

    def toggle_units(self):
        self.unit = 'lbs' if self.unit == 'kg' else 'kg'
        self.unit_btn.setText(f"Switch to {'kg' if self.unit == 'lbs' else 'lbs'}")
        self.load_data()

    def update_stats(self):
        data = self.db.get_weight_data()
        if not data: return
        
        current = data[-1][1] * (2.20462 if self.unit == 'lbs' else 1)
        self.current_weight.layout().itemAt(1).widget().setText(f"{current:.2f} {self.unit}")
        
        if len(data) > 7:
            weekly_gain = (data[-1][1] - data[-8][1]) * (2.20462 if self.unit == 'lbs' else 1)
            self.weekly_gain.layout().itemAt(1).widget().setText(f"{weekly_gain:+.2f} {self.unit}")

    def add_weight(self):
        if not self.db.add_weight(
            self.date_input.date().toString("yyyy-MM-dd"),
            float(self.weight_input.text()),
            self.notes_input.text()
        ):
            self._show_message("Entry for this date already exists!", "warning")
            return
        self.load_data()
        self.weight_input.clear()

    def log_meal(self):
        self.db.add_meal(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.meal_type.currentText(),
            self.sender().parent().findChild(QLineEdit).text(),
            float(self.sender().parent().findChildren(QLineEdit)[1].text())
        )
        self.load_data()

    def toggle_dev_mode(self, enabled):
        if not hasattr(self, 'test_btn'):
            self.test_btn = self._create_btn("🧪 Generate Test Data", self.create_test_data)
            self.clear_btn = self._create_btn("🗑️ Clear Test Data", self.clear_test_data)
            self.statusBar().addPermanentWidget(self.test_btn)
            self.statusBar().addPermanentWidget(self.clear_btn)
        self.test_btn.setVisible(enabled)
        self.clear_btn.setVisible(enabled)

    def create_test_data(self):
        # Generate 30 days of weight data
        base_date = datetime.now() - timedelta(days=30)
        [self.db.add_weight(
            (base_date + timedelta(days=d)).strftime("%Y-%m-%d"),
            round(1.5 + (d * 0.07) + random.uniform(-0.03, 0.03), 2),
            "Test"
        ) for d in range(30)]
        
        # Generate 100 meal entries
        meals = ["Breakfast 🍳", "Lunch 🥩", "Dinner 🍗", "Snack 🥛"]
        foods = ["Chicken", "Turkey", "Beef", "Fish", "Kibble"]
        [self.db.add_meal(
            (datetime.now() - timedelta(days=random.randint(0,29), hours=random.randint(0,23))).strftime("%Y-%m-%d %H:%M:%S"),
            random.choice(meals),
            random.choice(foods),
            random.randint(20, 100)
        ) for _ in range(100)]
        
        self._show_message("Generated test data!")
        self.load_data()

    def clear_test_data(self):
        self.db.clear_data()
        self._show_message("Cleared all data!")
        self.load_data()

    def _show_message(self, text, msg_type="info"):
        msg = QMessageBox(self)
        msg.setText(text)
        msg.setStyleSheet(f"background: {'#4CAF50' if msg_type == 'info' else '#FF4444'}; color: white;")
        msg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KittenTracker()
    window.show()
    sys.exit(app.exec())