# ⚡ Lastgang vs. Typenschild

**VR Energieservice GmbH** — Energieberatungs-Tool

Ein Streamlit-basiertes Berechnungstool, das die theoretischen Leistungsangaben
elektrischer Verbraucher (Typenschilddaten) mit realen Lastprofilen (RLM-Lastgang)
vergleicht.

## 🎯 Anwendungsfälle

### Szenario A — Neukunde (kein Lastgang vorhanden)
- Eingabe: Typenschilddaten (Nennleistung, Betriebsstunden, Gleichzeitigkeitsfaktoren)
- Ergebnis: Synthetisches Lastprofil, Jahresenergieschätzung, Tarifempfehlung (SLP/RLM)

### Szenario B — Bestandskunde (RLM-Lastgang vorhanden)
- Eingabe: Typenschilddaten + RLM-Lastgang (CSV, 15-Minuten-Intervalle)
- Ergebnis: Vergleich synthetisch vs. real, Abweichungsanalyse, Anomalieerkennung

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 📖 Verwendung

```bash
streamlit run app.py
```

## 📁 Projektstruktur

```
lastgang-tool/
├── app.py                  # Streamlit Einstiegspunkt
├── requirements.txt
├── core/
│   ├── config.py           # Schwellenwerte und Konfiguration
│   ├── models.py           # Pydantic-Datenmodelle
│   ├── calculator.py       # Synthetisches Lastprofil (Szenario A)
│   ├── comparator.py       # Abweichungsanalyse (Szenario B)
│   └── recommender.py      # Tarifempfehlungslogik
├── ui/
│   ├── scenario_a.py       # UI für Szenario A
│   ├── scenario_b.py       # UI für Szenario B
│   └── components.py       # Wiederverwendbare UI-Komponenten
├── data/
│   ├── generate_sample.py  # Beispieldaten-Generator
│   └── sample_rlm.csv      # Beispiel-RLM-Lastgang
└── utils/
    └── export.py           # Excel-Export
```

## 📊 CSV-Format (RLM-Upload)

Das Tool erkennt automatisch verschiedene RLM-Exportformate:

| Format | Trennzeichen | Dezimalzeichen | Beispiel |
|--------|-------------|----------------|----------|
| Netze BW | Semikolon | Komma | `01.01.2025 00:00;12,34` |
| Bayernwerk | Semikolon | Komma | Ähnlich |
| Generisch | Komma | Punkt | `2025-01-01 00:00,12.34` |

## 🏗️ Architektur

Die Geschäftslogik (`core/`) ist vollständig vom UI (`ui/`) entkoppelt,
um eine spätere Migration auf FastAPI + React zu ermöglichen.

## 📜 Lizenz

Proprietär — VR Energieservice GmbH
