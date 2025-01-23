import numpy as np
import sys
import csv
import random
import sqlite3
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDateTime, QDate, QPoint
from PyQt6.QtGui import QColor, QDoubleValidator, QPainter, QPen, QPixmap, QPolygon, QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QTabWidget, QDateEdit, QComboBox, QDialog, QDialogButtonBox)
from PyQt6.QtCharts import (QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis,
                            QBarSeries, QBarSet, QBarCategoryAxis, QScatterSeries)

# ================= DATABASE =================
class KittenDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('kitten_tracker.db')
        self._exec('''CREATE TABLE IF NOT EXISTS animals 
                    (id INTEGER PRIMARY KEY, name TEXT, animal_type TEXT, birthdate TEXT)''')
        self._exec('''CREATE TABLE IF NOT EXISTS weight_data 
                    (id INTEGER PRIMARY KEY, animal_id INTEGER, date TEXT, weight REAL, notes TEXT,
                     FOREIGN KEY(animal_id) REFERENCES animals(id))''')
        self._exec('''CREATE TABLE IF NOT EXISTS diet_logs 
                    (id INTEGER PRIMARY KEY, animal_id INTEGER, timestamp TEXT, meal_type TEXT, 
                     food_item TEXT, amount REAL, FOREIGN KEY(animal_id) REFERENCES animals(id))''')

    def _exec(self, query, params=()):
        try:
            self.conn.cursor().execute(query, params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.warning(None, "Database Error", f"An error occurred: {e}")
            return False

    def get_weight_data(self, animal_id):  # 👈 Add animal_id parameter
        return self.conn.cursor().execute(
            "SELECT date, weight, notes FROM weight_data WHERE animal_id=? ORDER BY date",
            (animal_id,)
        ).fetchall()
    
    def get_daily_nutrition(self, animal_id):
        return self.conn.cursor().execute(
            "SELECT DATE(timestamp) as day, SUM(amount) FROM diet_logs WHERE animal_id=? GROUP BY day ORDER BY day",
            (animal_id,)
        ).fetchall()

    def get_diet_logs(self, animal_id):  # 👈 Add animal_id parameter
        return self.conn.cursor().execute(
            "SELECT timestamp, meal_type, food_item, amount FROM diet_logs WHERE animal_id=? ORDER BY timestamp",
            (animal_id,)
        ).fetchall()

    def add_weight(self, animal_id, date, weight, notes):  # 👈 Add animal_id
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

# ================= CHARTS =================
class GrowthChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Weight Growth")
        self.scatter = QScatterSeries()
        self.scatter.setName("Measurements")
        self.scatter.setColor(QColor("#4CAF50"))
        self.trend = QLineSeries()
        self.trend.setPen(QPen(QColor("#26C6DA"), 2))
        self.addSeries(self.scatter)
        self.addSeries(self.trend)
        self._setup_axes()

    def _setup_axes(self):
        self.x_axis = QDateTimeAxis()
        self.y_axis = QValueAxis()
        for axis in [self.x_axis, self.y_axis]:
            axis.setTitleBrush(QColor("#FFFFFF"))
            axis.setLabelsBrush(QColor("#FFFFFF"))
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
        if not data: return

        dates = [datetime.strptime(d[0], "%Y-%m-%d") for d in data]
        weights = [d[1] * (2.20462 if unit == 'lbs' else 1) for d in data]
        timestamps = [int(d.timestamp() * 1000) for d in dates]  # Convert to milliseconds

        for ts, w in zip(timestamps, weights):
            self.scatter.append(ts, w)

                # Use days since first measurement for stability
        days_since_start = [(d - dates[0]).days for d in dates]
        try:
            slope, intercept = np.polyfit(days_since_start, weights, 1)
            # Convert days back to timestamps for plotting
            self.trend.append(dates[0].timestamp() * 1000, intercept)
            self.trend.append(dates[-1].timestamp() * 1000, slope * days_since_start[-1] + intercept)
        except:
            pass  # Fallback if numpy isn't installed

        self.x_axis.setRange(QDateTime.fromMSecsSinceEpoch(min(timestamps)), 
                             QDateTime.fromMSecsSinceEpoch(max(timestamps)))
        self.y_axis.setRange(min(weights) * 0.95, max(weights) * 1.05)

class NutritionChart(QChart):
    def __init__(self):
        super().__init__()
        self.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.setTitle("Nutrition Intake")
        self.bars = QBarSeries()
        self.goal_line = QLineSeries()
        self.goal_line.setPen(QPen(QColor("#FF5252"), 2))
        self.addSeries(self.bars)
        self.addSeries(self.goal_line)
        self._setup_axes()

    def _setup_axes(self):
        self.x_axis = QBarCategoryAxis()
        self.y_axis = QValueAxis()
        for axis in [self.x_axis, self.y_axis]:
            axis.setTitleBrush(QColor("#FFFFFF"))
            axis.setLabelsBrush(QColor("#FFFFFF"))
        self.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)
        self.bars.attachAxis(self.x_axis)
        self.bars.attachAxis(self.y_axis)
        self.goal_line.attachAxis(self.x_axis)
        self.goal_line.attachAxis(self.y_axis)

    def update_chart(self, data, goal=80):
        self.bars.clear()
        self.goal_line.clear()
        if not data: return

        bar_set = QBarSet("Intake")
        bar_set.setLabelColor(QColor("#FFFFFF"))
        categories = []
        amounts = []
        for date_str, amount in data:
            categories.append(date_str)
            amounts.append(amount)

        bar_set.append(amounts)
        self.bars.append(bar_set)
        self.x_axis.clear()
        self.x_axis.append(categories)
        self.y_axis.setRange(0, max(amounts + [goal]) * 1.2)

        if categories:
            self.goal_line.append(0, goal)
            self.goal_line.append(len(categories), goal)
            

# ================= MAIN APP =================
class KittenTracker(QMainWindow):

    def generate_random_icon(self):
        """Create a QIcon with random emoji combination"""
        # Create a pixmap to draw on
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Random background shape
        bg_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        painter.setBrush(bg_color)
        
        shape_choice = random.choice(["circle", "square", "triangle"])
        if shape_choice == "circle":
            painter.drawEllipse(4, 4, 56, 56)
        elif shape_choice == "square":
            painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        else:  # triangle
            poly = QPolygon([QPoint(32, 8), QPoint(58, 56), QPoint(6, 56)])
            painter.drawPolygon(poly)

        # Random emoji combination
        emojis = random.sample([
            "😺", "🐾", "🐱", "🎀", "🦴", "🍗", "🐟", "🥛",
            "🌟", "⚡", "❤️", "🌈", "🍎", "🐭", "🧶", "🎈"
        ], 2)
        
        # Draw emojis
        font = painter.font()
        font.setPointSize(24)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        
        for i, emoji in enumerate(emojis):
            painter.drawText(
                random.randint(8, 32),
                random.randint(32, 48) + i*16,
                emoji
            )
        
        painter.end()
        return QIcon(pixmap)

    def random_window_title(self):
        """Generate fun random window title"""
        adjectives = ["Fluffy", "Playful", "Majestic", "Cuddly", "Adorable"]
        nouns = ["Companion", "Friend", "Pal", "Buddy", "Maine Coon"]
        return f"{random.choice(adjectives)} {random.choice(nouns)} Tracker 🐾"

    def __init__(self):
        super().__init__()
        self.db = KittenDatabase()
        self.unit = 'kg'
        self.nutrition_goal = 80
        self.setup_ui()
        self.load_data()
        self.toggle_dev_mode(False)

        # Set random icon and title
        self.setWindowIcon(self.generate_random_icon())
        self.setWindowTitle(self.random_window_title())

    def export_data(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            return
            
        with open('weight_data.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Weight', 'Notes'])
            writer.writerows(self.db.get_weight_data(animal_id))  # 👈 Add animal_id  

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
        self.age_card = self._create_card("Age", "N/A", "#7E57C2")  # 👈 New card (purple)
        stats.addWidget(self.current_weight)
        stats.addWidget(self.weekly_gain)
        stats.addWidget(self.age_card)  # 👈 Add this line

        # Add this near the stats layout
        self.goal_input = QLineEdit("80", placeholderText="Daily Goal (g)")
        self.goal_input.setValidator(QDoubleValidator(1, 999, 0))
        self.goal_input.editingFinished.connect(lambda: [ setattr(self, 'nutrition_goal', float(self.goal_input.text())), self.load_data()])
        stats.addWidget(self.goal_input)

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
        form = QHBoxLayout()
        self.date_input = QDateEdit(calendarPopup=True)
        self.weight_input = QLineEdit(placeholderText="Weight")
        self.weight_input.setValidator(QDoubleValidator(0.1, 99.9, 2))
        self.notes_input = QLineEdit(placeholderText="Notes")
        self.date_input.setMaximumDate(QDate.currentDate())  # Prevent future dates
        self.add_weight_btn = QPushButton("➕ Add Entry", clicked=self.add_weight)
        for w in [self.date_input, self.weight_input, self.notes_input, self.add_weight_btn]:
            form.addWidget(w)

        self.weight_table = self._create_table(["Date", "Weight", "Notes"])
        weight_tab.setLayout(QVBoxLayout())
        weight_tab.layout().addLayout(form)
        weight_tab.layout().addWidget(self.weight_table)
        tabs.addTab(weight_tab, "⚖️ Weight")

        # Diet Tab
        diet_tab = QWidget()
        form = QHBoxLayout()
        self.meal_type = QComboBox()
        self.meal_type.addItems(["Breakfast 🍳", "Lunch 🥩", "Dinner 🍗", "Snack 🥛"])
        self.food_input = QLineEdit(placeholderText="Food item")
        self.amount_input = QLineEdit(placeholderText="Grams")
        self.amount_input.setValidator(QDoubleValidator(1, 9999, 1))
        self.log_meal_btn = QPushButton("📝 Log Meal", clicked=self.log_meal)
        for w in [self.meal_type, self.food_input, self.amount_input, self.log_meal_btn]:
            form.addWidget(w)

        self.diet_table = self._create_table(["Timestamp", "Meal Type", "Food", "Amount (g)"])
        diet_tab.setLayout(QVBoxLayout())
        diet_tab.layout().addLayout(form)
        diet_tab.layout().addWidget(self.diet_table)
        tabs.addTab(diet_tab, "🍴 Meals")

        # Animal Selection
        self.animal_combo = QComboBox()
        self.animal_combo.currentIndexChanged.connect(self.load_data)  # Reload data when animal changes
        self.add_animal_btn = QPushButton("➕ New Animal", clicked=self.add_animal)

        # Status Bar (FIXED ORDER)
        self.unit_btn = QPushButton("Switch to lbs", clicked=self.toggle_units)  # 👈 Create first
        self.export_btn = QPushButton("💾 Export CSV", clicked=self.export_data)  # 👈 Then this

        status = self.statusBar()
        status.addPermanentWidget(QLabel("Current Animal:"))
        status.addPermanentWidget(self.animal_combo)
        status.addPermanentWidget(self.add_animal_btn)
        status.addPermanentWidget(self.unit_btn)  # 👈 Now exists
        status.addPermanentWidget(self.export_btn)  # 👈 Now exists

        # Developer menu
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
        return table

    def _create_card(self, title, value, color):
        card = QWidget(styleSheet=f"background: {color}; border-radius: 10px; padding: 15px;")
        layout = QVBoxLayout(card)
        layout.addWidget(QLabel(title, styleSheet="color: rgba(255,255,255,0.8); font-size: 16px;"))
        layout.addWidget(QLabel(value, styleSheet="color: white; font-size: 24px; font-weight: bold;"))
        return card

    def load_data(self):
        # Get currently selected animal
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "Error", "Please select an animal first!")
            return

        # Clear previous data
        self.weight_table.setRowCount(0)
        self.diet_table.setRowCount(0)

        # Load weight data
        weight_data = self.db.get_weight_data(animal_id)
        for row in weight_data:
            self.weight_table.insertRow(self.weight_table.rowCount())
            for col, val in enumerate(row):
                self.weight_table.setItem(self.weight_table.rowCount()-1, col, QTableWidgetItem(str(val)))

        # Load diet data
        diet_logs = self.db.get_diet_logs(animal_id)
        for row in diet_logs:
            self.diet_table.insertRow(self.diet_table.rowCount())
            for col, val in enumerate(row):
                self.diet_table.setItem(self.diet_table.rowCount()-1, col, QTableWidgetItem(str(val)))

        # Update charts
        self.growth_chart.chart().update_chart(weight_data, self.unit)
        self.nutrition_chart.chart().update_chart(
            self.db.get_daily_nutrition(animal_id), 
            self.nutrition_goal
        )

        # Update stats cards
        if weight_data:
            current_weight = weight_data[-1][1] * (2.20462 if self.unit == 'lbs' else 1)
            self.current_weight.layout().itemAt(1).widget().setText(f"{current_weight:.2f} {self.unit}")
            
            if len(weight_data) > 7:
                weekly_gain = (weight_data[-1][1] - weight_data[-8][1]) * (2.20462 if self.unit == 'lbs' else 1)
                self.weekly_gain.layout().itemAt(1).widget().setText(f"{weekly_gain:+.2f} {self.unit}")

        # Age calculation
        animal_info = self.db.conn.cursor().execute(
            "SELECT birthdate FROM animals WHERE id=?", (animal_id,)
        ).fetchone()
        
        if animal_info and animal_info[0]:
            try:
                birthdate = QDate.fromString(animal_info[0], "yyyy-MM-dd")
                today = QDate.currentDate()
                age_days = birthdate.daysTo(today)
                
                years = age_days // 365
                days = age_days % 365
                age_text = f"{years}y {days}d" if years > 0 else f"{days}d"
                self.age_card.layout().itemAt(1).widget().setText(age_text)
            except:
                self.age_card.layout().itemAt(1).widget().setText("N/A")
        else:
            self.age_card.layout().itemAt(1).widget().setText("N/A")

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
            if weight <= 0: return
            if self.db.add_weight(animal_id, date, weight, self.notes_input.text()):
                self.load_data()
                self.weight_input.clear()
                self.notes_input.clear()
            else:
                QMessageBox.warning(self, "Duplicate Entry", "Entry for this date already exists!")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid weight")

    def add_animal(self):
        """Open dialog to add new animal"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Animal")
        layout = QVBoxLayout()
        
        # Inputs
        name_input = QLineEdit(placeholderText="Name")
        type_input = QComboBox()
        type_input.addItems(["Cat", "Dog", "Other"])
        birthdate_input = QDateEdit(calendarPopup=True)
        birthdate_input.setDate(QDate.currentDate())
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        
        # Layout
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(name_input)
        layout.addWidget(QLabel("Type:"))
        layout.addWidget(type_input)
        layout.addWidget(QLabel("Birthdate:"))
        layout.addWidget(birthdate_input)
        layout.addWidget(btn_box)
        dialog.setLayout(layout)
    
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db._exec(
                "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
                (name_input.text(), type_input.currentText(), birthdate_input.date().toString("yyyy-MM-dd"))
            )
            self._refresh_animal_list()

    def _refresh_animal_list(self):
        """Update animal dropdown list"""
        self.animal_combo.clear()
        animals = self.db.conn.cursor().execute("SELECT id, name FROM animals").fetchall()
        for animal_id, name in animals:
            self.animal_combo.addItem(name, animal_id)  # Store ID as userData
        if animals:  # Force load data if animals exist
            self.load_data()

    def current_animal_id(self):
        """Get ID of selected animal"""
        return self.animal_combo.currentData()
    

    def log_meal(self):
        animal_id = self.current_animal_id()
        if not animal_id:
            QMessageBox.warning(self, "Error", "Select an animal first!")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            amount = float(self.amount_input.text())
            if amount <= 0: return
            if self.db.add_meal(
                animal_id,  # 👈 Added animal ID
                timestamp, 
                self.meal_type.currentText(), 
                self.food_input.text(), 
                amount
            ):
                self.load_data()
                self.food_input.clear()
                self.amount_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Enter valid amount")

    def update_meal_types(self):
        """Update meal types based on selected animal's species"""
        animal_id = self.current_animal_id()
        if not animal_id:
            self.meal_type.clear()
            return

        # Get animal type from database
        animal_type = self.db.conn.cursor().execute(
            "SELECT animal_type FROM animals WHERE id=?", (animal_id,)
        ).fetchone()

        if not animal_type:
            return

        self.meal_type.clear()
        
        # Set species-specific meal types
        if animal_type[0] == "Cat":
            self.meal_type.addItems([
                "Wet Food 🐟", 
                "Dry Food 🥣", 
                "Treat 🍗", 
                "Medicine 💊",
                "Kitten Milk"
            ])
        elif animal_type[0] == "Dog":
            self.meal_type.addItems([
                "Kibble 🦴", 
                "Raw Meat 🥩", 
                "Dental Chew 🦷", 
                "Puppy Formula",
                "Dog Treat 🍖"
            ])
        else:  # Other animals
            self.meal_type.addItems([
                "Regular Meal", 
                "Special Diet", 
                "Vitamin", 
                "Custom Feed"
            ])

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
        # Clear existing data
        self.db.clear_data()
        
        # Add test animal with direct cursor access
        cursor = self.db.conn.cursor()
        cursor.execute(
            "INSERT INTO animals (name, animal_type, birthdate) VALUES (?, ?, ?)",
            ("Test Kitty", "Cat", "2023-01-01")
        )
        self.db.conn.commit()
        animal_id = cursor.lastrowid
        
        # Refresh animal list and select test animal
        self._refresh_animal_list()
        index = self.animal_combo.findText("Test Kitty")
        if index >= 0:
            self.animal_combo.setCurrentIndex(index)
        
        # Generate test data using proper datetime calculations
        base_date = datetime.now() - timedelta(days=30)
        meals = ["Wet Food 🐟", "Dry Food 🥣", "Treat 🍗"]
        foods = ["Chicken", "Fish", "Kibble"]
        
        # Weight data with proper date formatting
        for d in range(30):
            self.db.add_weight(
                animal_id,
                (base_date + timedelta(days=d)).strftime("%Y-%m-%d"),
                round(1.5 + (d * 0.07) + random.uniform(-0.03, 0.03), 2),
                "Test"
            )
        
        # Meal data with valid timestamps
        for _ in range(100):
            random_date = datetime.now() - timedelta(days=random.randint(0,29))
            self.db.add_meal(
                animal_id,
                random_date.strftime("%Y-%m-%d %H:%M:%S"),
                random.choice(meals),
                random.choice(foods),
                random.randint(20, 100)
            )

        QMessageBox.information(self, "Test Data", "Generated test data!")
        self.load_data()  # Force immediate refresh

    def clear_test_data(self):
        self.db.clear_data()
        self._refresh_animal_list()  # Clear the animal list display
        QMessageBox.information(self, "Data Cleared", "All data has been removed!")
        self.load_data()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KittenTracker()
    window.show()
    sys.exit(app.exec())
