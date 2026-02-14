# Captive Portal Login Scripts

Automatische Login-Scripts für Captive Portals (öffentliche WLAN-Hotspots).

## Übersicht

Diese Scripts automatisieren den Login-Prozess an Captive Portals wie Hotel-WLAN, Flughafen-WLAN oder öffentlichen Hotspots. Sie prüfen die Internet-Verbindung und loggen sich automatisch ein, wenn ein Captive Portal den Zugriff blockiert.

## Scripts

| Script | Netzwerk | Beschreibung |
|--------|----------|--------------|
| `scripts/inetiu.py` | Bundeswehr INetiU | Legacy-Script für Bundeswehr-Netzwerk |
| `scripts/bayernwlan.py` | @BayernWLAN | BayernWLAN / Vodafone Hotspot |
| `scripts/telekom.py` | Telekom Hotspot | T-Mobile/T-Online Hotspot |

## Unterstützte Netzwerke

### BayernWLAN (@BayernWLAN)
- **Portal**: https://hotspot.vodafone.de/bayern/
- **Login**: Automatisch via "Verbinden"-Button
- **Konfiguration**: Bereits vorkonfiguriert in `scripts/bayernwlan.py`

### Telekom Hotspot
- **Portal**: https://hotspot.t-mobile.net/
- **Login**: Via "Jetzt surfen"-Button
- **Konfiguration**: Bereits vorkonfiguriert in `scripts/telekom.py`

## Installation

### Voraussetzungen

```bash
# Python 3.5+ erforderlich
python3 --version

# requests Library installieren
pip install requests
# oder
pip3 install requests
```

### Clone das Repository

```bash
git clone https://github.com/3x3cut0r/captive-portal-login.git
cd captive-portal-login
```

## manuell Ausführung

```bash
# BayernWLAN
python3 scripts/bayernwlan.py

# Telekom
python3 scripts/telekom.py

# INetiU (Bundeswehr)
python3 scripts/inetiu.py
```

## Automatischer Login mit systemd

### Option 1: Timer (empfohlen)

Die Timer-Variante startet den Login automatisch alle 5 Minuten:

```bash
# Service und Timer installieren
sudo cp systemd/captive-portal.service /etc/systemd/system/
sudo cp systemd/captive-portal.timer /etc/systemd/system/

# Script-Pfad im Service anpassen (Pfad zur .py Datei)
sudo nano /etc/systemd/system/captive-portal.service

# systemd neu laden
sudo systemctl daemon-reload

# Timer aktivieren
sudo systemctl enable --now captive-portal.timer
```

### Option 2: Cron

```bash
# Cronjob hinzufügen (alle 5 Minuten)
crontab -e

# Eintrag:
*/5 * * * * /usr/bin/python3 /PFAD/ZU/captive-portal-login/scripts/telekom.py
```

## Konfiguration

Die wichtigsten Einstellungen stehen am Anfang jedes Scripts:

```python
# Connectivity Check
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
PROBE_EXPECTED_STATUS = 204

# Portal URL (Fallback wenn Captive Portal nicht automatisch erkannt wird)
PORTAL_FALLBACK_URL = "https://hotspot.t-mobile.net/"

# Form-Erkennung
FORM_ID = None                   # ID des Forms (optional)
FORM_ACTION_CONTAINS = "login"   # Text im action-Attribut
BUTTON_TEXT_CONTAINS = "surf"    # Text im Submit-Button

# Erforderliche Form-Felder
DEFAULT_FORM_FIELDS = {}         # Hidden Fields

# Query-Parameter die weitergeleitet werden sollen
QUERY_FIELDS_FROM_PORTAL_URL = ["sessionId", "mac", "apMac", "clientMac"]

# Timeout
REQUEST_TIMEOUT = 10
```

### Eigene Portale hinzufügen

1. Kopiere `scripts/bayernwlan.py` als Vorlage
2. Passe die Konfiguration am Anfang der Datei an
3. Teste mit `python3 scripts/neues_script.py`

## Funktionsweise

1. **Connectivity Check**: Script prüft mit `http://connectivitycheck.gstatic.com/generate_204` ob Internet erreichbar ist
2. **Portal-Erkennung**: Wenn nicht erreichbar, wird die Portal-Seite geladen
3. **Form-Extraktion**: HTML-Parser sucht nach Login-Formular
4. **Login-Submit**: Form-Daten werden an das Portal gesendet
5. **Erfolgskontrolle**: Internet-Verbindung wird erneut geprüft

## systemd Troubleshooting

```bash
# Status prüfen
systemctl status captive-portal.service
systemctl status captive-portal.timer

# Logs anzeigen
journalctl -u captive-portal.service -f

# Manuell starten
systemctl start captive-portal.service

# Timer stoppen
systemctl stop captive-portal.timer
```

## Lizenz

Siehe LICENSE Datei.
