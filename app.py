import os
from dotenv import load_dotenv
from flask import Flask, request, render_template_string
from openai import OpenAI
import requests
import datetime as dt

load_dotenv()
app = Flask(__name__)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_API_TOKEN")
)

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

def auto_detect_city():
    try:
        r = requests.get("http://ip-api.com/json", timeout=5)
        r.raise_for_status()
        data = r.json()
        city = data.get("city", "Antananarivo")
        countryCode = data.get("countryCode", "MG")
        return f"{city},{countryCode}"
    except:
        return "Antananarivo,MG"

def ow_current(city: str):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city.strip(), "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr"}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, f"Erreur météo actuelle : {e}"

def ow_forecast(city: str):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city.strip(), "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr", "cnt": 40}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        forecast_list = []
        added_days = set()
        for item in data["list"]:
            day = item["dt_txt"].split(" ")[0]
            if day not in added_days:
                added_days.add(day)
                desc = item["weather"][0]["description"].capitalize()
                temp = round(item["main"]["temp"])
                humidity = item["main"]["humidity"]
                wind = round(item["wind"]["speed"],1)
                forecast_list.append(f"📅 {day} : {desc}, {temp}°C, humidité {humidity}%, vent {wind} m/s")
            if len(forecast_list) >= 5:
                break
        return forecast_list
    except:
        return ["Prévision indisponible"]

def ask_openai_hf(prompt):
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b:together",
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Erreur lors de l'appel au modèle : {e}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Assistant Agricole Madagascar</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; background: #e8f5e9; padding: 10px; }
        .container { max-width: 800px; margin: auto; background: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);}
        input, button { padding: 12px; margin: 10px 0; width: 100%; border-radius: 8px; border: 1px solid #ccc; }
        button { background: #4caf50; color: white; font-weight: bold; cursor: pointer; }
        button:hover { background: #388e3c; }
        .weather, .forecast, .chat { margin-top: 20px; padding: 15px; border-radius: 10px; line-height: 1.6; }
        .weather { background: #fffde7; }
        .forecast { background: #e1f5fe; }
        .chat { background: #f1f8e9; }
        .question { font-weight: bold; margin-top: 10px; }
        .response { margin-top: 10px; white-space: pre-wrap; }
        h1 { text-align: center; color: #2e7d32; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌱 Assistant Agricole Madagascar</h1>
        <div class="weather">
            <h3>🌦️ Météo actuelle à {{ city }}</h3>
            <p>{{ weather }}</p>
        </div>
        <div class="forecast">
            <h3>📅 Prévision météo 5 jours</h3>
            {% for f in forecast %}
                <p>{{ f }}</p>
            {% endfor %}
        </div>
        <div class="chat">
            <div class="question">📝 Ta question :</div>
            <div>{{ question }}</div>
            <div class="response">🤖 Réponse du bot :<br>{{ reply }}</div>
        <form method="POST">
            <input type="text" name="message" placeholder="Pose ta question ici...">
            <button type="submit">Envoyer</button>
        </form>
        {% if question %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    city = auto_detect_city()
    weather_data, err = ow_current(city)
    if weather_data:
        weather_info = f"{weather_data['weather'][0]['description'].capitalize()}, Temp: {weather_data['main']['temp']}°C, Humidité: {weather_data['main']['humidity']}%, Vent: {weather_data['wind']['speed']} m/s"
    else:
        weather_info = err

    forecast = ow_forecast(city)
    reply = ""
    question = ""
    if request.method == "POST":
        question = request.form.get("message")
        if question:
            prompt = f"Tu es un assistant agricole pour Madagascar. La météo actuelle à {city} est: {weather_info}. Donne uniquement une réponse claire pour la question suivante en **points**, avec des emojis, bien espacée, inclure plantation, arrosage, fertilisation, récolte, vente. Pas de tableaux, pas de #, pas de *, aérer le texte. Question: {question}"
            reply = ask_openai_hf(prompt)

    return render_template_string(HTML_TEMPLATE, city=city, weather=weather_info, forecast=forecast, reply=reply, question=question)

if __name__ == "__main__":
    app.run(debug=True)