import os
from dotenv import load_dotenv
from flask import Flask, request, render_template_string
from openai import OpenAI
import requests

load_dotenv()
app = Flask(__name__)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_API_TOKEN")
)

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

chat_history = []

# ------------------------------
# Fonctions météo
# ------------------------------
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

# ------------------------------
# OpenAI
# ------------------------------
def ask_openai_hf(prompt):
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b:together",
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Erreur lors de l'appel au modèle : {e}"

def translate_text_full(text, lang="fr"):
    """Traduction complète FR ↔ MG via OpenAI"""
    if lang == "mg":
        prompt = f"Traduis le texte suivant en malgache de manière naturelle, en gardant les emojis et la mise en page:\n{text}"
        return ask_openai_hf(prompt)
    return text

# ------------------------------
# Template HTML
# ------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Assistant Agricole Madagascar</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="{{ url_for('static', filename='improved_styles.css') }}">
</head>
<body>
    <div class="header">
        <div>
            <h1>🌱 Assistant Agricole Madagascar</h1>
            <div class="weather">{{ weather }}</div>
        </div>
        <form method="POST" style="display:inline;">
            <input type="hidden" name="lang_toggle" value="{{ toggle_lang }}">
            <button class="lang-btn" type="submit">{{ toggle_lang.upper() }}</button>
        </form>
    </div>

    <div class="container">
        <div class="forecast">
            <h3>{{ forecast_title }}</h3>
            {% for f in forecast %}
                <p>{{ f }}</p>
            {% endfor %}
        </div>

        <div class="chat">
            {% for chat in chat_history %}
                <div class="question">📝 {{ chat.question }}</div>
                <div class="response">🤖 {{ chat.reply }}</div>
                <hr>
            {% endfor %}
        </div>

        <div class="input-container">
            <form method="POST">
                <input type="text" name="message" placeholder="Posez votre question agricole ici..." required>
                <button type="submit">Envoyer</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# ------------------------------
# Route principale
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    city = auto_detect_city()
    weather_data, err = ow_current(city)
    if weather_data:
        weather_info = f"{weather_data['weather'][0]['description'].capitalize()}, Temp: {weather_data['main']['temp']}°C, Humidité: {weather_data['main']['humidity']}%, Vent: {weather_data['wind']['speed']} m/s"
    else:
        weather_info = err

    forecast = ow_forecast(city)

    # Gestion langue
    lang = request.form.get("lang_toggle", "fr")
    toggle_lang = "mg" if lang == "fr" else "fr"
    weather_info_trans = translate_text_full(weather_info, lang)
    forecast_title = translate_text_full("Prévision météo 5 jours", lang)

    if request.method == "POST":
        question = request.form.get("message")
        if question:
            prompt = f"""
Tu es un assistant agricole spécialisé pour Madagascar. 
La météo actuelle à {city} est : {weather_info_trans}.  

Règles de réponse :
- Réponds uniquement à la question suivante de manière claire et simple.  
- Utilise des points avec des emojis 🌱💧🌾💰🚜.  
- Aère bien le texte (sauts de ligne entre chaque point).  
- Inclure si possible : plantation, arrosage, fertilisation, récolte et vente.  
- Propose une culture rare ou peu cultivée et explique comment réussir malgré le climat actuel, en proposant des protections ou irrigation si nécessaire.  
- Ne fais pas de tableau, ne mets pas de # ou de *.

Question : {question}
"""
            reply = ask_openai_hf(prompt)
            reply = translate_text_full(reply, lang)
            chat_history.append({"question": question, "reply": reply})

    return render_template_string(
        HTML_TEMPLATE,
        weather=weather_info_trans,
        forecast=forecast,
        chat_history=chat_history,
        forecast_title=forecast_title,
        toggle_lang=toggle_lang
    )

if __name__ == "__main__":
    app.run(debug=True)
