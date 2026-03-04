# 1. GRAPHICS & WINDOW CONFIGURATION
from kivy.config import Config
# Removing hardcoded small sizes to allow the OS/Mobile to decide, 
# but setting a minimum for Desktop stability.
Config.set('graphics', 'multisamples', '0')
Config.set('graphics', 'minimum_width', '360')
Config.set('graphics', 'minimum_height', '640')

import os
import time
import sqlite3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.uix.image import Image
from plyer import battery, notification

# ---------------- DATABASE (From hoperescue logic) ----------------
conn = sqlite3.connect("charging_pro.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE, 
    password TEXT)
""")
conn.commit()

# ================= REGISTER SCREEN (First Screen) =================
class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.clearcolor = (0.05, 0.08, 0.15, 1)
        layout = BoxLayout(orientation="vertical", padding=50, spacing=20)

        layout.add_widget(Image(source='logo.png', size_hint=(1, 0.4)))
        layout.add_widget(Label(text="Create Account", font_size=24, bold=True))

        self.username = TextInput(hint_text="Username", multiline=False, size_hint_y=None, height=50)
        self.password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=None, height=50)
        self.status = Label(text="", color=(1, 0.3, 0.3, 1))

        reg_btn = Button(text="REGISTER", size_hint_y=None, height=60, background_color=(0.1, 0.7, 0.3, 1))
        reg_btn.bind(on_press=self.register_user)
        
        login_link = Button(text="Already have an account? Login", size_hint_y=None, height=40, background_color=(0,0,0,0))
        login_link.bind(on_press=lambda x: setattr(self.manager, 'current', 'login'))

        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(reg_btn)
        layout.add_widget(login_link)
        layout.add_widget(self.status)
        self.add_widget(layout)

    def register_user(self, instance):
        user = self.username.text.strip()
        pwd = self.password.text.strip()
        if not user or not pwd:
            self.status.text = "Fields cannot be empty"
            return
        try:
            cursor.execute("INSERT INTO users(username, password) VALUES(?,?)", (user, pwd))
            conn.commit()
            self.manager.current = 'login'
        except sqlite3.IntegrityError:
            self.status.text = "Username already exists"

# ================= LOGIN SCREEN =================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=50, spacing=20)
        
        layout.add_widget(Image(source='logo.png', size_hint=(1, 0.4)))
        layout.add_widget(Label(text="Login to Charging Pro", font_size=24, bold=True))

        self.username = TextInput(hint_text="Username", multiline=False, size_hint_y=None, height=50)
        self.password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=None, height=50)
        self.status = Label(text="", color=(1, 0.3, 0.3, 1))

        login_btn = Button(text="LOGIN", size_hint_y=None, height=60, background_color=(0.2, 0.6, 1, 1))
        login_btn.bind(on_press=self.login_user)

        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(login_btn)
        layout.add_widget(self.status)
        self.add_widget(layout)

    def login_user(self, instance):
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (self.username.text, self.password.text))
        if cursor.fetchone():
            self.manager.current = 'battery'
        else:
            self.status.text = "Invalid Credentials"

# ================= BATTERY SCREEN =================
class BatteryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=40, spacing=20)
        
        self.status_label = Label(text="Checking Battery Status...", font_size=22)
        self.time_label = Label(text="Estimating charge time...", font_size=18, color=(0.3, 0.8, 1, 1))
        
        self.layout.add_widget(self.status_label)
        self.layout.add_widget(self.time_label)
        self.add_widget(self.layout)

        # Sound loading
        self.alarm = SoundLoader.load("alarm.mp3") if os.path.exists("alarm.mp3") else None
        
        self.prev_percent = None
        self.charge_start_time = None

    def on_enter(self):
        Clock.schedule_interval(self.update_battery, 5)

    def update_battery(self, dt):
        try:
            status = battery.status
            percent = status.get('percentage', 0)
            is_charging = status.get('isCharging', False)
            
            self.status_label.text = f"Battery: {percent}% [{'Charging' if is_charging else 'Discharging'}]"
            
            # --- ALARM LOGIC ---
            if is_charging and percent >= 100:
                self.status_label.text = "⚡ FULLY CHARGED! UNPLUG NOW."
                if self.alarm and not self.alarm.state == 'play':
                    self.alarm.play()
                notification.notify(title="Battery Full", message="Please unplug your charger.")

            # --- TIME ESTIMATION LOGIC ---
            if is_charging and percent < 100:
                # Basic estimation: if we gained 1% in X seconds, 
                # remaining time = (100 - current) * X
                if self.prev_percent is not None and percent > self.prev_percent:
                    elapsed = time.time() - self.charge_start_time
                    rate_per_percent = elapsed / (percent - self.prev_percent)
                    remaining_mins = (rate_per_percent * (100 - percent)) / 60
                    self.time_label.text = f"Estimated Full in: {int(remaining_mins)} mins"
                
                if self.prev_percent != percent:
                    self.prev_percent = percent
                    self.charge_start_time = time.time()
            else:
                self.time_label.text = "Not charging / Calculating..."
                self.prev_percent = None

        except Exception as e:
            self.status_label.text = "Battery Data Unavailable"

# ================= MAIN APP =================
class ChargingSavePro(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(BatteryScreen(name="battery"))
        return sm

if __name__ == "__main__":
    ChargingSavePro().run()
