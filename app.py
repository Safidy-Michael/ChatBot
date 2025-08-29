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
        return None, f"Impossible de récupérer la météo : {e}"

def ow_forecast_5d(city: str):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city.strip(), "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr"}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, f"Impossible de récupérer la prévision 5 jours : {e}"

def summarize_forecast(forecast_json):
    summary = []
    for item in forecast_json.get("list", []):
        ts = item["dt"]
        date = dt.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
        desc = item["weather"][0]["description"].capitalize()
        temp = item["main"]["temp"]
        summary.append(f"{date}: {desc}, Temp: {temp}°C")
    return summary[:10]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assistant Agricole Madagascar</title>
<style>
body { font-family: 'Segoe UI', sans-serif; background: #f9f6f2; margin:0; padding:0; }
.container { max-width: 900px; margin: 20px auto; background: #fff; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
h1 { text-align:center; color: #2e7d32; margin-bottom:20px; }
.weather, .forecast, .bot-response { padding:15px; border-radius:12px; margin-bottom:15px; background:#f0f0f0; }
form { display:flex; flex-direction:column; margin-top:10px; }
input[type=text], select { width:100%; padding:12px; border-radius:8px; border:1px solid #ccc; margin-bottom:10px; font-size:16px; }
button { background:#2e7d32; color:white; border:none; padding:12px; border-radius:8px; cursor:pointer; font-size:16px; }
button:hover { background:#1b5e20; }
@media (max-width:600px) {
    .container { padding:15px; }
    input[type=text], select, button { font-size:14px; }
}
</style>
</head>
<body>
<div class="container">
<h1>🌱 Assistant Agricole Madagascar</h1>

{% if weather %}
<div class="weather">
<h3>🌦️ Météo actuelle à {{ city }}</h3>
<p>{{ weather }}</p>
</div>
{% endif %}

{% if forecast %}
<div class="forecast">
<h3>📅 Prévision 5 jours</h3>
<ul>
{% for f in forecast %}
<li>{{ f }}</li>
{% endfor %}
</ul>
</div>
{% endif %}

{% if bot_reply %}
<div class="bot-response">
<h3>🤖 Réponse du bot :</h3>
<p>{{ bot_reply|safe }}</p>
</div>
{% endif %}

<form method="POST">
<select name="lang">
<option value="fr" {% if lang=='fr' %}selected{% endif %}>Français</option>
<option value="mg" {% if lang=='mg' %}selected{% endif %}>Malagasy</option>
</select>
<input type="text" name="message" placeholder="{% if lang=='mg' %}Ohatra: Ahoana ny fambolena karaoty?{% else %}Ex: Comment planter des carottes ?{% endif %}" required>
<button type="submit">{% if lang=='mg' %}Alefa{% else %}Envoyer{% endif %}</button>
</form>

</div>
</body>
</html>
"""

def ask_openai_hf(prompt):
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b:together",
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Erreur lors de l'appel au modèle : {e}"

@app.route("/", methods=["GET","POST"])
def index():
    city = auto_detect_city()
    weather_data, err = ow_current(city)
    forecast_data, _ = ow_forecast_5d(city)
    forecast_summary = summarize_forecast(forecast_data) if forecast_data else []

    weather_info = f"{weather_data['weather'][0]['description'].capitalize()}, Temp: {weather_data['main']['temp']}°C, Humidité: {weather_data['main']['humidity']}%, Vent: {weather_data['wind']['speed']} m/s" if weather_data else err

    lang = request.form.get("lang", "fr")
    bot_reply = None

    if request.method == "POST":
        message = request.form.get("message")
        if message:
            prompt = (
                f"Tu es un assistant agricole pour Madagascar, langue {lang}. "
                f"Météo actuelle à {city}: {weather_info}. "
                "Liste en points simples les cultures possibles aujourd'hui et explique clairement "
                "les étapes: plantation, arrosage, fertilisation, récolte et vente. "
                f"Question de l'utilisateur: {message}"
            )
            bot_reply = ask_openai_hf(prompt)

    return render_template_string(
        HTML_TEMPLATE,
        city=city,
        weather=weather_info,
        forecast=forecast_summary,
        bot_reply=bot_reply,
        lang=lang
    )

if __name__ == "__main__":
    app.run(debug=True)
