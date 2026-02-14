# Captive Portal Login Scripts

Automatische Login-Scripts für Captive Portals ( öffentliche WLAN-Hotspots).

## Zweck

Diese Scripts automatisieren den Login-Prozess an Captive Portals (z.B. Hotel-WLAN, Flughafen, Telekom Hotspot). Sie prüfen die Internet-Verbindung und loggen sich automatisch ein, wenn ein Captive Portal blockiert.

## Scripts

| Script | Beschreibung |
|--------|--------------|
| `scripts/inetiu.py` | INetiU Captive Portal (Bundeswehr) - benötigt Username/Passwort |
| `scripts/bayernwlan.py` | Generisches BayernWLAN/Vodafone Blueprint |
| `scripts/telekom.py` | Telekom T-Mobile Hotspot |

## Funktionsweise

1. **Connectivity Check**: Prüft mit `http://connectivitycheck.gstatic.com/generate_204` ob Internet erreichbar ist
2. **Portal-Erkennung**: Wenn nicht erreichbar, wird die Portal-Seite geladen
3. **Form-Extraktion**: Parst HTML nach Login-Formularen
4. **Login-Submit**: Sendet Form-Daten an das Portal

## Konfiguration

Die wichtigsten Einstellungen stehen am Anfang jedes Scripts:

```python
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
PROBE_EXPECTED_STATUS = 204
PORTAL_FALLBACK_URL = "https://hotspot.t-mobile.net/"
FORM_ACTION_CONTAINS = "login"
BUTTON_TEXT_CONTAINS = "surf"
DEFAULT_FORM_FIELDS = {}
QUERY_FIELDS_FROM_PORTAL_URL = ["sessionId", "mac", "apMac", "clientMac"]
REQUEST_TIMEOUT = 10
```

## Tipps für neue Portale

1. **PORTAL_FALLBACK_URL**: Die URL des Captive Portals (z.B. `https://hotspot.t-mobile.net/`)
2. **FORM_ACTION_CONTAINS**: Textfragment im `action`-Attribut des Login-Forms
3. **BUTTON_TEXT_CONTAINS**: Text im Submit-Button (z.B. "Jetzt surfen")
4. **DEFAULT_FORM_FIELDS**: Eventuell benötigte Hidden-Felder
5. **QUERY_FIELDS_FROM_PORTAL_URL**: Query-Parameter die durchgereicht werden sollen

## Nutzung

```bash
python3 scripts/telekom.py
```

Oder als Cron-Job für automatischen Re-Login:

```bash
*/5 * * * * /usr/bin/python3 /pfad/zu/telekom.py
```

## Anforderungen

- Python 3.5+
- `requests` Library (`pip install requests`)
