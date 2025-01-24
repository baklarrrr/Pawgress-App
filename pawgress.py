import os
import numpy as np
import sys
import csv
import random
import sqlite3
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDateTime, QDate, QPoint
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
    def __init__(self):
        self.conn = sqlite3.connect('kitten_tracker.db')
        self._exec("PRAGMA foreign_keys = ON")
        self._exec("PRAGMA journal_mode = WAL")
        self._create_tables()
        
    def _create_tables(self):
        self._exec('''CREATE TABLE IF NOT EXISTS animals 
                    (id INTEGER PRIMARY KEY, name TEXT, 
                     animal_type TEXT, birthdate TEXT)''')
        self._exec('''CREATE TABLE IF NOT EXISTS weight_data 
                    (id INTEGER PRIMARY KEY, animal_id INTEGER, date TEXT, 
                     weight REAL, notes TEXT, UNIQUE(animal_id, date),
                     FOREIGN KEY(animal_id) REFERENCES animals(id))''')
        self._exec('''CREATE TABLE IF NOT EXISTS diet_logs 
                    (id INTEGER PRIMARY KEY, animal_id INTEGER, timestamp TEXT,
                     meal_type TEXT, food_item TEXT, amount REAL,
                     FOREIGN KEY(animal_id) REFERENCES animals(id))''')
        self._exec("CREATE INDEX IF NOT EXISTS idx_weight ON weight_data(animal_id, date)")
        self._exec("CREATE INDEX IF NOT EXISTS idx_meals ON diet_logs(animal_id, timestamp)")

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

    def create_backup(self):
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        try:
            self.conn.execute(f"VACUUM INTO '{backup_name}'")
            return True
        except sqlite3.Error as e:
            QMessageBox.warning(None, "Backup Failed", str(e))
            return False

    def get_weight_data(self, animal_id):
        return self.conn.cursor().execute(
            "SELECT date, weight, notes FROM weight_data WHERE animal_id=? ORDER BY date",
            (animal_id,)
        ).fetchall()
    
    def get_daily_nutrition(self, animal_id):
        return self.conn.cursor().execute(
            "SELECT DATE(timestamp), ROUND(SUM(amount), 1) "  # Fixed column alias
            "FROM diet_logs WHERE animal_id=? GROUP BY DATE(timestamp) ORDER BY DATE(timestamp)",
            (animal_id,)
        ).fetchall()

    def get_diet_logs(self, animal_id):
        return self.conn.cursor().execute(
            "SELECT timestamp, meal_type, food_item, amount FROM diet_logs WHERE animal_id=? ORDER BY timestamp",
            (animal_id,)
        ).fetchall()

    def add_weight(self, animal_id, date, weight, notes):
        return self._exec(
            "INSERT OR IGNORE INTO weight_data (animal_id, date, weight, notes) VALUES (?, ?, ?, ?)", 
            (animal_id, date, weight, notes)
        )

    def add_meal(self, animal_id, timestamp, meal_type, food, amount):
        return self._exec(
            "INSERT INTO diet_logs (animal_id, timestamp, meal_type, food_item, amount) VALUES (?, ?, ?, ?, ?)",
            (animal_id, timestamp, meal_type, food, amount)
        )

    def clear_data(self):
        self._exec("DELETE FROM animals")
        self._exec("DELETE FROM weight_data")
        self._exec("DELETE FROM diet_logs")

# ================= CHARTS (PARTIAL) =================
class GrowthChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Weight Growth")
        
        # Series
        self.scatter = QScatterSeries()
        self.scatter.setName("Measurements")
        self.scatter.setColor(QColor("#4CAF50"))
        self.scatter.setMarkerSize(10)
        
        self.trend = QLineSeries()
        self.trend.setName("Trend Line")
        self.trend.setPen(QPen(QColor("#26C6DA"), 2, Qt.PenStyle.DashLine))
        
        self.addSeries(self.scatter)
        self.addSeries(self.trend)
        
        # Axes
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
            self.trend.append(QDateTime.fromString(data[0][0], "yyyy-MM-dd").toMSecsSinceEpoch(), trend_func(x_vals[0]))
            self.trend.append(QDateTime.fromString(data[-1][0], "yyyy-MM-dd").toMSecsSinceEpoch(), trend_func(x_vals[-1]))

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
        
        # Axes
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
            max_val = max(max_val, clean_total)

        bar_set.append(amounts)
        self.bars.append(bar_set)
        
        self.x_axis.setCategories(categories)
        self.y_axis.setRange(0, max_val * 1.2)
        
        if categories:
            self.goal_line.append(0, goal)
            self.goal_line.append(len(categories)-1, goal)

# ================= MAIN APP (PARTIAL) =================
class KittenTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        if not os.path.exists('kitten_tracker.db'):
            self.show_welcome_message()
        self.db = KittenDatabase()
        self.unit = 'kg'
        self.nutrition_goal = 80
        self.setup_ui()
        self.load_data()
        self.toggle_dev_mode(False)
        self.setWindowIcon(self.generate_random_icon())
        self.setWindowTitle(self.random_window_title())

    def generate_random_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background shape
        bg_color = QColor(random.randint(0,255), random.randint(0,255), random.randint(0,255))
        painter.setBrush(bg_color)
        
        shape = random.choice(["circle", "square", "triangle"])
        if shape == "circle":
            painter.drawEllipse(4, 4, 56, 56)
        elif shape == "square":
            painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        else:
            poly = QPolygon([QPoint(32,8), QPoint(58,56), QPoint(6,56)])
            painter.drawPolygon(poly)
        
        # Emojis
        emojis = random.sample(["😺","🐾","🐱","🎀","🦴","🍗","🐟","🥛","🌟","⚡","❤️","🌈","🍎","🐭","🧶","🎈"], 2)
        font = painter.font()
        font.setPointSize(24)
        painter.setFont(font)
        painter.setPen(QColor(255,255,255))
        
        for i, emoji in enumerate(emojis):
            painter.drawText(
                random.randint(8,32),
                random.randint(32,48) + i*16,
                emoji
            )
        
        painter.end()
        return QIcon(pixmap)

    def random_window_title(self):
        adjectives = ["Fluffy", "Playful", "Majestic", "Cuddly", "Adorable"]
        nouns = ["Companion", "Friend", "Pal", "Buddy", "Maine Coon"]
        return f"{random.choice(adjectives)} {random.choice(nouns)} Tracker 🐾"

    def show_welcome_message(self):
        QMessageBox.information(self, "Welcome",
            "Welcome to Kitten Tracker!\n\n"
            "Start by adding your first animal using the '+' button.")

    def setup_ui(self):
        self.setWindowTitle("Animal Tracker 🐾")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet("background: #1E1E1E; color: white;")

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # Dashboard Tab
        dash_tab = QWidget()
        layout = QVBoxLayout(dash_tab)

        # Stats
        stats = QHBoxLayout()
        self.current_weight = self._create_card("Current Weight", "N/A", "#4CAF50")
        self.weekly_gain = self._create_card("Weekly Trend", "N/A", "#26C6DA")
        self.age_card = self._create_card("Age", "N/A", "#7E57C2")
        stats.addWidget(self.current_weight)
        stats.addWidget(self.weekly_gain)
        stats.addWidget(self.age_card)

        # Goal Input
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

        # Charts
        chart_layout = QHBoxLayout()
        self.growth_chart = QChartView(GrowthChart())
        self.nutrition_chart = QChartView(NutritionChart())
        chart_layout.addWidget(self.growth_chart)
        chart_layout.addWidget(self.nutrition_chart)

        layout.addLayout(stats)
        layout.addLayout(chart_layout)
        tabs.addTab(dash_tab, "📈 Dashboard")

        # Weight Tab
        weight_tab = QWidget()
        weight_layout = QVBoxLayout(weight_tab)
        
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
        tabs.addTab(weight_tab, "⚖️ Weight")        

        # Diet Tab
        diet_tab = QWidget()
        diet_layout = QVBoxLayout(diet_tab)
        
        form = QHBoxLayout()
        self.meal_type = QComboBox()
        self.meal_type.addItems(["Breakfast 🍳", "Lunch 🥩", "Dinner 🍗", "Snack 🥛"])
        self.food_input = QLineEdit(placeholderText="Food item")
        self.amount_input = QLineEdit(placeholderText="Grams")
        self.amount_input.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.log_meal_btn = QPushButton("📝 Log Meal", clicked=self.log_meal)
        
        for w in [self.meal_type, self.food_input, self.amount_input, self.log_meal_btn]:
            form.addWidget(w)
        
        self.diet_table = self._create_table(["Timestamp", "Meal Type", "Food", "Amount (g)"])
        diet_layout.addLayout(form)
        diet_layout.addWidget(self.diet_table)
        tabs.addTab(diet_tab, "🍴 Meals")

        # Status Bar
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

        # Developer Menu
        dev_menu = self.menuBar().addMenu("Developer")
        self.dev_mode = dev_menu.addAction("Development Mode")
        self.dev_mode.setCheckable(True)
        self.dev_mode.triggered.connect(lambda: self.toggle_dev_mode(self.dev_mode.isChecked()))
        self.randomize_ui = dev_menu.addAction("Randomize UI")
        self.randomize_ui.triggered.connect(lambda: [
            self.setWindowIcon(self.generate_random_icon()),
            self.setWindowTitle(self.random_window_title())
        ])

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

            # Load weight data
            weight_data = self.db.get_weight_data(animal_id)
            for date, weight, notes in weight_data:
                row = self.weight_table.rowCount()
                self.weight_table.insertRow(row)
                self.weight_table.setItem(row, 0, DateTimeTableWidgetItem(date))
                self.weight_table.setItem(row, 1, QTableWidgetItem(f"{weight:.2f}"))
                self.weight_table.setItem(row, 2, QTableWidgetItem(notes))

            # Load diet logs
            diet_logs = self.db.get_diet_logs(animal_id)
            for timestamp, meal_type, food, amount in diet_logs:
                row = self.diet_table.rowCount()
                self.diet_table.insertRow(row)
                self.diet_table.setItem(row, 0, DateTimeTableWidgetItem(timestamp))
                self.diet_table.setItem(row, 1, QTableWidgetItem(meal_type))
                self.diet_table.setItem(row, 2, QTableWidgetItem(food))
                self.diet_table.setItem(row, 3, QTableWidgetItem(f"{amount:.1f} g"))

            # Update charts
            self.growth_chart.chart().update_chart(weight_data, self.unit)
            nutrition_data = self.db.get_daily_nutrition(animal_id)
            self.nutrition_chart.chart().update_chart(nutrition_data, self.nutrition_goal)

            # Update stats
            if weight_data:
                current_weight = weight_data[-1][1] * (2.20462 if self.unit == 'lbs' else 1)
                self.current_weight.layout().itemAt(1).widget().setText(f"{current_weight:.2f} {self.unit}")
                
                if len(weight_data) > 7:
                    weekly_gain = (weight_data[-1][1] - weight_data[-8][1]) * (2.20462 if self.unit == 'lbs' else 1)
                    self.weekly_gain.layout().itemAt(1).widget().setText(f"{weekly_gain:+.2f} {self.unit}")

            # Update age
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
            
        date = self.date_input.date().toString("yyyy-MM-dd")
        try:
            weight = float(self.weight_input.text())
            if self.db.add_weight(animal_id, date, weight, self.notes_input.text()):
                self.load_data()
                self.weight_input.clear()
                self.notes_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid weight")

    def log_meal(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "Error", "Select an animal first!")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            amount = float(self.amount_input.text())
            if self.db.add_meal(animal_id, timestamp, 
                              self.meal_type.currentText(), 
                              self.food_input.text(), amount):
                self.load_data()
                self.food_input.clear()
                self.amount_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Enter valid amount")

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
            self.load_data()

    def current_animal_id(self):
        return self.animal_combo.currentData()

    def update_meal_types(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            return
            
        animal_type = self.db.conn.cursor().execute(
            "SELECT animal_type FROM animals WHERE id=?", (animal_id,)
        ).fetchone()[0]

        self.meal_type.clear()
        if animal_type == "Cat":
            self.meal_type.addItems(["Wet Food 🐟", "Dry Food 🥣", "Treat 🍗", "Medicine 💊"])
        elif animal_type == "Dog":
            self.meal_type.addItems(["Kibble 🦴", "Raw Meat 🥩", "Dental Chew 🦷", "Puppy Formula"])
        else:
            self.meal_type.addItems(["Regular Meal", "Special Diet", "Vitamin", "Custom Feed"])

    def toggle_dev_mode(self, enabled):
        if not hasattr(self, 'test_btn'):
            self.test_btn = QPushButton("🧪 Generate Test Data", clicked=self.create_test_data)
            self.clear_btn = QPushButton("🗑️ Clear Data", clicked=self.clear_test_data)
            for btn in [self.test_btn, self.clear_btn]:
                btn.setStyleSheet("background: #FFA726; padding: 5px;")
                self.statusBar().addPermanentWidget(btn)
        self.test_btn.setVisible(enabled)
        self.clear_btn.setVisible(enabled)

    def create_test_data(self):
        self.db.clear_data()
        cursor = self.db.conn.cursor()
        cursor.execute(
            "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
            ("Test Kitty", "Cat", "2023-01-01")
        )
        animal_id = cursor.lastrowid
        
        # Create weight data
        base_date = datetime.now() - timedelta(days=30)
        for d in range(30):
            self.db.add_weight(
                animal_id,
                (base_date + timedelta(days=d)).strftime("%Y-%m-%d"),
                round(1.5 + (d * 0.07) + random.uniform(-0.03, 0.03), 2),
                "Auto-generated"
            )
        
        # Create meal data
        meals = ["Wet Food 🐟", "Dry Food 🥣", "Treat 🍗"]
        foods = ["Chicken", "Fish", "Beef", "Kibble"]
        for _ in range(100):
            random_days = random.randint(0, 29)
            timestamp = (base_date + timedelta(days=random_days)).strftime("%Y-%m-%d %H:%M:%S")
            self.db.add_meal(
                animal_id,
                timestamp,
                random.choice(meals),
                random.choice(foods),
                random.randint(20, 100)
            )
        
        self._refresh_animal_list()
        if self.animal_combo.count() > 0:
            self.animal_combo.setCurrentIndex(0)
        self.load_data()

    def clear_test_data(self):
        self.db.clear_data()
        self._refresh_animal_list()
        self.load_data()

    def export_data(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            return
            
        filename = f"weight_data_{animal_id}.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Weight', 'Notes'])
            writer.writerows(self.db.get_weight_data(animal_id))
        QMessageBox.information(self, "Export Complete", f"Data saved to {filename}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KittenTracker()
    window.show()
    sys.exit(app.exec())        