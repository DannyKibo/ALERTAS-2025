import requests
import time
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN 🔧
# ────────────────────────────────────────────────────────────────────────────────

API_SPORTS_KEY     = "2cb99e086c768fcadcad714a3a395c90"
TELEGRAM_BOT_TOKEN = "7724085291:AAGo84StQsVgIdDDsuP5t4-5eP61lcQkPQs"
TELEGRAM_CHAT_ID   = "1269910384"
CHECK_INTERVAL     = 60  # segundos entre cada revisión
alerted_games      = set()  # para no enviar dos veces alerta del mismo juego en el Q3


# ────────────────────────────────────────────────────────────────────────────────
# Función para enviar un mensaje a Telegram
# ────────────────────────────────────────────────────────────────────────────────
def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram devolvió código {resp.status_code} │ Respuesta: {resp.text}")
    except Exception as ex:
        print(f"[ERROR] No se pudo enviar mensaje a Telegram: {ex}")


# ────────────────────────────────────────────────────────────────────────────────
# Función para obtener TODOS los partidos de HOY y luego filtrarlos por Q3
# ────────────────────────────────────────────────────────────────────────────────
def get_live_games():
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url_fecha = f"https://v1.basketball.api-sports.io/games?date={hoy}"
    headers = {
        "x-apisports-key": API_SPORTS_KEY
    }
    try:
        response = requests.get(url_fecha, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("response", [])
        else:
            print(f"[ERROR] Código HTTP {response.status_code} al pedir juegos por fecha.")
            return []
    except Exception as e:
        print(f"[ERROR] Excepción al obtener datos de API-Sports: {e}")
        return []


# ────────────────────────────────────────────────────────────────────────────────
# Función para obtener las cuotas Over/Under de un partido
# ────────────────────────────────────────────────────────────────────────────────
def get_game_over_under(game_id: int):
    url = f"https://v1.basketball.api-sports.io/odds"
    headers = {
        "x-apisports-key": API_SPORTS_KEY
    }
    params = {
        "game_id": game_id  # Aseguramos que pasamos el game_id para obtener la cuota
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            odds = data.get("response", [])
            if odds:
                over_under = odds[0].get("over_under", {})
                return over_under
            else:
                print(f"[ERROR] No se encontraron datos de cuotas para el juego con ID={game_id}.")
        else:
            print(f"[ERROR] Código HTTP {response.status_code} al pedir cuotas Over/Under.")
    except Exception as e:
        print(f"[ERROR] Excepción al obtener cuotas Over/Under: {e}")
    return {}


# ────────────────────────────────────────────────────────────────────────────────
# Función principal: detecta partidos en TERCER CUARTO (Q3) y envía alerta
# ────────────────────────────────────────────────────────────────────────────────
def main():
    send_telegram_alert("✅ El script de alerta de basket (API-Sports) ha iniciado correctamente.")
    print("✅ Script iniciado correctamente.")
    print(f"⏳ Revisando partidos cada {CHECK_INTERVAL} segundos.")

    while True:
        print("\n[INFO] 🔄 Ejecutando chequeo de partidos en vivo (filtrando por fecha)…")
        live_games = get_live_games()
        print(f"[INFO] 📡 {len(live_games)} partidos recuperados desde API-Sports (todos de hoy).")

        print("📋 Partidos de hoy:")
        for game in live_games:
            home_name = game.get("teams", {}).get("home", {}).get("name", "Equipo Local")
            away_name = game.get("teams", {}).get("away", {}).get("name", "Equipo Visitante")
            status_long = game.get("status", {}).get("long", "Sin estado")
            timer = game.get("status", {}).get("timer", "None")
            print(f" 🏀 {home_name} vs {away_name} | Estado: {status_long} | Timer: {timer}")

        third_quarter_found = False

        for game in live_games:
            game_id = game.get("id")
            status_info = game.get("status", {})
            quarter_num = status_info.get("quarter")
            status_short = (status_info.get("short") or "").upper()
            status_long = status_info.get("long", "")
            timer = status_info.get("timer", "")
            scores = game.get("scores", {})

            status_lower = status_long.lower()
            is_third = (
                quarter_num == 3
                or status_short == "3Q"
                or status_lower.startswith("3rd")
                or status_lower.startswith("quarter 3")
                or status_lower.startswith("q3")
            )

            if is_third:
                third_quarter_found = True
                print(f"[PARTIDO] ID: {game_id}, Estado: {status_long}, Timer: {timer}")

                try:
                    if timer:
                        if ":" in timer:
                            minutes_elapsed = int(timer.split(":")[0])
                        else:
                            minutes_elapsed = int(timer)
                        third_quarter_elapsed = minutes_elapsed
                    else:
                        third_quarter_elapsed = 0

                    if 0 <= third_quarter_elapsed <= 10:
                        elapsed = third_quarter_elapsed
                        minutes_remaining = 10 - elapsed
                        print(f"[DEBUG] ⏱ Minutos transcurridos del 3er cuarto: {elapsed} (faltan {minutes_remaining})")

                        if 3 <= elapsed <= 8:
                            home_scores = scores.get("home", {})
                            away_scores = scores.get("away", {})

                            q1_home = int(home_scores.get("quarter_1", 0) or 0)
                            q1_away = int(away_scores.get("quarter_1", 0) or 0)
                            q1_total = q1_home + q1_away

                            q2_home = int(home_scores.get("quarter_2", 0) or 0)
                            q2_away = int(away_scores.get("quarter_2", 0) or 0)
                            q2_total = q2_home + q2_away

                            # Obtener el valor Over/Under
                            over_under = get_game_over_under(game_id)
                            if over_under:
                                # Supongamos que el Over/Under es la proyección de puntos total
                                projected_total = over_under.get("total_points", 0)

                                # Proyección de Q3 y Q4
                                # Proyección de Q3: Tomamos los puntos del tercer cuarto (Q3)
                                q3_home = int(home_scores.get("quarter_3", 0) or 0)
                                q3_away = int(away_scores.get("quarter_3", 0) or 0)
                                q3_total = q3_home + q3_away

                                # Usamos el comportamiento de Q1, Q2 y Q3 para proyectar Q4
                                avg_points_per_quarter = (q1_total + q2_total + q3_total) / 3
                                projected_q4 = avg_points_per_quarter  # Proyectamos que Q4 será similar al promedio

                                # Proyección total del partido
                                projected_game_total = q1_total + q2_total + q3_total + projected_q4

                                # Calcular la tendencia
                                if projected_game_total > projected_total:
                                    trend = "al alza"
                                else:
                                    trend = "a la baja"

                                # Calcular la potencia de la tendencia
                                difference = abs(projected_game_total - projected_total)
                                trend_strength = "alta" if difference > 10 else "moderada"

                                home_team = game.get("teams", {}).get("home", {}).get("name", "Equipo Local")
                                away_team = game.get("teams", {}).get("away", {}).get("name", "Equipo Visitante")

                                # Calcular el umbral
                                threshold = (q1_total + q2_total) / 16.0

                                mensaje = (
                                    "🏀 ALERTA BASKET (API-Sports)\n"
                                    f"📌 Partido: {home_team} 🆚 {away_team}\n"
                                    f"🆔 ID: {game_id}\n"
                                    f"⏱ Cuarto: 3 | Minutos transcurridos en Q3: {elapsed} (faltan {minutes_remaining})\n"
                                    f"📊 Umbral (Q1+Q2)/16: {threshold:.2f}\n"
                                    f"🔢 Q1: {q1_total} | Q2: {q2_total}\n"
                                    f"🔻 Q3 ➤ {home_team}: {home_scores.get('quarter_3', 0)} | {away_team}: {away_scores.get('quarter_3', 0)}\n"
                                    f"📈 Tendencia Over/Under: {trend} | Potencia de la tendencia: {trend_strength}\n"
                                    f"📊 Puntos proyectados totales: {projected_game_total} | Cuota Over/Under: {projected_total}"
                                )
                                send_telegram_alert(mensaje)
                                alerted_games.add(game_id)
                                print(f"[ALERTA] 🚨 Mensaje enviado para el partido ID={game_id}")
                        else:
                            print(f"[DEBUG] ⏱ Minutos transcurridos ({elapsed}) fuera de la ventana crítica 3–8.")
                    else:
                        print(f"[DEBUG] ⏱ Minutos transcurridos ({third_quarter_elapsed}) no están en 0–10 del Q3.")
                except Exception as e:
                    print(f"[ERROR] Procesando partido ID={game_id}. Timer: {timer} | Error: {e}")

        if not third_quarter_found:
            print("[INFO] ℹ️ No hay partidos actualmente en el tercer cuarto.")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
