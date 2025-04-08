import tkinter as tk
from tkinter import ttk, messagebox
import requests
import geocoder

class WeatherApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Прогноз погоды")
        self.master.geometry("400x400")

        self.city_label = tk.Label(master, text="Выберите город:", font=('Helvetica', 12))
        self.city_label.pack(pady=10)

        self.city_combobox = ttk.Combobox(master, values=[], state='readonly')
        self.city_combobox.pack(pady=5)
        self.city_combobox.bind("<<ComboboxSelected>>", self.get_weather)

        self.weather_info = tk.Text(master, width=50, height=10, font=('Helvetica', 10))
        self.weather_info.pack(pady=10)

        self.get_geolocation()  # Получаем геолокацию при старте
        self.populate_city_combobox()  # Заполняем список городов

        # Устанавливаем Ростов-на-Дону как город по умолчанию
        self.city_combobox.current(self.city_combobox['values'].index("Ростов-на-Дону"))

        self.refresh_button = tk.Button(master, text="Получить погоду", command=self.get_weather)
        self.refresh_button.pack(pady=10)

    def get_geolocation(self):
        g = geocoder.ip('me')
        if g.ok:
            lat = g.latlng[0]
            lon = g.latlng[1]
            self.update_weather(lat, lon)

    def populate_city_combobox(self):
        # Топ 25 городов России по населению
        cities = [
            "Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск",
            "Казань", "Нижний Новгород", "Челябинск", "Ростов-на-Дону",
            "Уфа", "Самара", "Волгоград", "Воронеж",
            "Красноярск", "Пермь", "Тольятти", "Ижевск",
            "Омск", "Братск", "Саратов", "Петрозаводск",
            "Тюмень", "Калуга", "Астрахань", "Липецк",
            "Магнитогорск", "Набережные Челны"
        ]
        self.city_combobox['values'] = cities
        self.city_combobox.current(0)  # Установим первый город по умолчанию

    def get_weather(self, event=None):
        city = self.city_combobox.get()
        lat, lon = self.get_city_coordinates(city)
        if lat and lon:
            self.update_weather(lat, lon)

    def get_city_coordinates(self, city):
        # Координаты топ 25 городов России
        city_coordinates = {
            "Москва": (55.7558, 37.6173),
            "Санкт-Петербург": (59.9343, 30.3351),
            "Екатеринбург": (56.8389, 60.6056),
            "Новосибирск": (55.0084, 82.9357),
            "Казань": (55.8304, 49.0661),
            "Нижний Новгород": (56.2965, 43.9361),
            "Челябинск": (55.1644, 61.4368),
            "Ростов-на-Дону": (47.2226, 39.7189),
            "Уфа": (54.7381, 55.9721),
            "Самара": (53.1959, 50.1002),
            "Волгоград": (48.7080, 44.5133),
            "Воронеж": (51.6640, 39.1858),
            "Красноярск": (56.0153, 92.8526),
            "Пермь": (58.0105, 56.2500),
            "Тольятти": (52.5000, 49.6000),
            "Ижевск": (56.8519, 53.2115),
            "Омск": (54.9885, 73.3242),
            "Братск": (56.1315, 101.6110),
            "Саратов": (51.5823, 45.9642),
            "Петрозаводск": (61.7852, 34.3452),
            "Тюмень": (57.1522, 65.5272),
            "Калуга": (54.5120, 36.2682),
            "Астрахань": (46.3498, 48.0375),
            "Липецк": (52.6090, 39.5730),
            "Магнитогорск": (53.0457, 58.9887),
            "Набережные Челны": (55.7454, 52.2994)
        }
        return city_coordinates.get(city)

    def update_weather(self, lat, lon):
        try:
            # Получение данных о погоде от Open-Meteo
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(url)
            data = response.json()

            # Извлечение информации о погоде
            if 'current_weather' in data:
                weather = data['current_weather']
                temp = weather['temperature']
                wind_speed = weather['windspeed']
                weather_code = weather['weathercode']
                
                weather_description = self.weather_description(weather_code)

                self.weather_info.delete(1.0, tk.END)
                self.weather_info.insert(tk.END, f"Температура: {temp}°C\n")
                self.weather_info.insert(tk.END, f"Скорость ветра: {wind_speed} м/с\n")
                self.weather_info.insert(tk.END, f"Состояние: {weather_description}\n")
            else:
                messagebox.showerror("Ошибка", "Не удалось получить данные о погоде.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

    def weather_description(self, code):
        descriptions = {
            0: "Ясно",
            1: "Дымка",
            2: "Облачно",
            3: "Небольшие облака",
            45: "Туман",
            51: "Небольшой дождь",
            61: "Умеренный дождь",
            80: "Ливневый дождь",
            95: "Гроза",
            99: "Сильная гроза"
        }
        return descriptions.get(code, "Неизвестно")

if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherApp(root)
    root.mainloop()