# CLAUDE.md — Enerlytics

## Projektübersicht

**Enerlytics** (intern: "Lastgang vs. Typenschild") ist ein Streamlit-basiertes Energieberatungs-Tool für **VR Energieservice GmbH**. Es richtet sich ausschließlich an interne Energieberater und ist auf **Streamlit Cloud** gehostet.

**Kernaufgabe:** Aus den Typenschilddaten elektrischer Verbraucher ein synthetisches Lastprofil generieren und dieses optional mit einem realen RLM-Lastgang (CSV-Upload vom Netzbetreiber) vergleichen — um Tarifempfehlungen (SLP vs. RLM) und Optimierungspotenziale (Lastverschiebung, Peak-Shaving) abzuleiten.

---

## Tech-Stack

| Schicht | Technologie |
|--------|-------------|
| UI | Streamlit ≥ 1.30 |
| Berechnungen | NumPy ≥ 1.24, Pandas ≥ 2.0 |
| Visualisierung | Plotly ≥ 5.18 |
| Datenvalidierung | Pydantic v2 |
| Export | OpenPyXL ≥ 3.1 |
| Sprache | Python 3.7+ |

Lokaler Start: `streamlit run app.py` → öffnet automatisch `http://localhost:8501`. Dateiänderungen werden live erkannt (Rerun-Button oben rechts).

---

## UI-Konventionen

**Mobile-First:** Das Tool wird primär auf Mobilgeräten und Tablets genutzt (Energieberater vor Ort beim Kunden). Alle Layouts müssen auf schmalen Screens funktionieren, auf Desktop dürfen sie breiter werden.

- **Spalten:** Maximal **2 Spalten** für Metric-Cards (`st.metric`). Maximal **3 Spalten** für Inhaltsbereiche. Niemals 4+ Spalten für Text oder Zahlen — Labels werden auf Mobilgeräten truncated.
- **Plotly-Charts:** Immer `width="stretch"`, keine feste Pixelbreite. Mindesthöhe 350 px.
- **Expander statt Tabs** für sekundäre Inhalte auf mobil bevorzugen, wenn der Inhalt nicht sofort sichtbar sein muss.

---

## Architektur

```
app.py                  ← Einstiegspunkt, Sidebar-Routing, Custom CSS (VR-Branding)

core/                   ← Reine Geschäftslogik — KEIN Streamlit-Import
  config.py             ← Alle Konstanten & Schwellenwerte (Zeitauflösung, Tarif-Grenzwerte, Branding-Farben, Demo-Maschinen). Enthält SAMPLE_MACHINES (Metallverarbeitung, Szenario A) und SAMPLE_MACHINES_WP (4 Daikin-WPs, Default beider Szenarien)
  models.py             ← Pydantic-Modelle (Machine, MachineSet, LoadProfileMeta, DeviationReport, TariffRecommendation)
  calculator.py         ← Synthetische Lastprofilgenerierung (15-min-Auflösung; Schaltjahre korrekt unterstützt)
  comparator.py         ← RLM-CSV-Parser (Netze BW, Bayernwerk, generisch) + Abweichungsanalyse
  recommender.py        ← Tarifempfehlungs-Engine (SLP vs. RLM, Lastverschiebung, Peak-Shaving)

ui/
  scenario_a.py         ← Szenario A: Neukunde (nur Typenschilddaten)
  scenario_b.py         ← Szenario B: Bestandskunde (Typenschilddaten + RLM-Upload)
  components.py         ← Wiederverwendbare Plotly-Charts und KPI-Karten

utils/
  export.py             ← Excel-Workbook-Generierung (openpyxl, mehrere Sheets)

data/
  sample_rlm.csv        ← Demo-RLM-Lastgang (Netze-BW-Format, ein Jahr, 15-min)
  rlm_2024.csv          ← Echter Lastgang 2024 (4 Daikin-Wärmepumpen, Zähler 50254112622)
  rlm_2025_2026.csv     ← Echter Lastgang Jan 2025 – Mai 2026 (gleicher Zähler)
  generate_sample.py    ← Skript zum Erzeugen synthetischer Demo-CSV-Daten
```

**Designprinzip:** `core/` ist vollständig vom UI entkoppelt — für eine spätere Migration zu **FastAPI + React** vorbereitet. Niemals Streamlit-Imports in `core/`.

---

## Zwei Hauptszenarien

### Szenario A — Neukunde
Kein Lastgang vorhanden. Eingabe: Typenschilddaten pro Maschine.
- Synthese: Bottom-up, 15-min-Auflösung, ganzes Jahr (Schaltjahre korrekt)
- Algorithmus: Betriebsmaske → effektive Leistung → Ramp-up/down an Schichtgrenzen → Gauß'sches Rauschen (±5%) → Wochenprofil über Jahr kacheln
- Ausgabe: KPI-Karten, Wochenprofil-Chart, Jahresthermogramm, Excel-Export
- **Keine** Tarifempfehlung im Frontend — Interpretation obliegt dem Berater

### Szenario B — Bestandskunde
Echter RLM-Lastgang vorhanden. Eingabe: Typenschilddaten + RLM-CSV.
- Parst automatisch: Semikolon/Komma/Tab-Trennzeichen, deutsches/internationales Dezimalformat, 6 Datumsformate
- Jahr wird automatisch aus dem CSV erkannt und als Referenzjahr gesetzt
- Alignment: Beide Serien werden dedupliziert (DST-Duplikate → Mittelwert) und auf ein gemeinsames 15-min-Raster resamplet
- Metriken: MAPE, maximale Abweichung (kW und %), unerklärte Grundlast, Anomalie-Intervalle (>20% Abweichung)
- Ausgabe: Jahresvergleichs-Chart (stündlich aggregiert) + Wochendetail, Abweichungsanalyse, Excel-Export

---

## Datenmodelle (core/models.py)

### Machine
Einzelner elektrischer Verbraucher:
- `rated_power_kw` — Nennleistung vom Typenschild
- `operating_hours_per_day` — Betriebsstunden pro Tag
- `days_per_week` — Betriebstage pro Woche (1–7)
- `simultaneity_factor` — Gleichzeitigkeitsfaktor (0–1), **default 1.0**, optional (in UI unter "Erweiterte Einstellungen")
- `load_factor` — Lastfaktor (0–1), **default 1.0**, optional (in UI unter "Erweiterte Einstellungen")
- `start_hour` — Startzeit (0–24)
- `category` — `production` | `auxiliary` | `building_services`
- Property `effective_power_kw` = `rated_power_kw × simultaneity_factor × load_factor`

### Tarif-Schwellenwerte (core/config.py)
- RLM-Pflicht: > 100.000 kWh/Jahr
- Lastverschiebungs-Flag: Lastfaktor < 30%
- Peak-Shaving-Flag: Spitzenlast > 50 kW
- Anomalie-Schwelle: > 20% Abweichung

---

## CSV-Format (RLM-Upload)

Der Parser (`core/comparator.py`) unterstützt automatisch:

| Format | Trennzeichen | Dezimalzeichen |
|--------|-------------|----------------|
| Netze BW | `;` | `,` |
| Bayernwerk | `;` | `,` |
| Generisch | `,` | `.` |

**Wichtig:** Werte müssen in **kW** vorliegen (nicht kWh). Für Excel-Exporte aus Netzbetreiber-Portalen (die kWh/15min liefern) mit dem Skript `data/generate_sample.py` als Referenz konvertieren (×4).

**Bug behoben (2026-05-16):** Parser hat bei internationalem Dezimalformat (Punkt) fälschlicherweise alle Punkte als Tausendertrennzeichen entfernt → Werte ×100 zu groß. Fix: Dezimalformat wird nun vor dem Parsen erkannt.

**Bug behoben (2026-05-16):** `align_profiles` versagte bei deutschen RLM-CSVs durch doppelte Zeitstempel an der Zeitumstellung (Oktober, Uhren zurück). Fix: Deduplizierung per Mittelwert vor dem Alignment, danach Resampling auf gemeinsames 15-min-Raster statt reinem Index-Join.

**Bug behoben (2026-05-16):** Synthetisches Profil für Schaltjahre (z. B. 2024) wurde auf 35.040 Intervalle truncated → fehlender 31. Dezember. Fix: Truncation entfernt, `date_range` liefert das korrekte Jahresende.

---

## Bekannter Anwendungsfall: Daikin-Wärmepumpen

Erster echter Kundendatensatz (Auftraggeber Marvins, Mai 2026):
- 4 Daikin-VRV-Außengeräte (Baujahr 2007–2008), Kältemittel R410A
- Zähler-ID: 50254112622, OBIS: 1-1:1.29.0 (Entnahme)
- Reale Lastgänge: `data/rlm_2024.csv` (Jahresverbrauch 108.723 kWh) und `data/rlm_2025_2026.csv`
- Anlage ist **RLM-pflichtig** (> 100.000 kWh/Jahr)

Empfohlene Enerlytics-Parameter für die 4 WPs (Szenario B):

| Maschine | Modell | Nennleistung | Basis |
|----------|--------|-------------|-------|
| WP 1 | REYQ14PY1B | 11,2 kW | Typenschild (Mittel Kühlen/Heizen) |
| WP 2 | REYQ12PY1B | 9,0 kW | Typenschild |
| WP 3 | REMQ12P8Y1B | 8,6 kW | Schätzung aus 22,7A |
| WP 4 | REYQ12M8W1BA | 8,8 kW | Schätzung aus 23,3A |

Betrieb: 24h/Tag, 7 Tage/Woche. Lastfaktor und Gleichzeitigkeit auf Default (1,0) lassen.

**Bekannte Modellgrenze:** Das synthetische Profil wird flach (~12,4 kW konstant) sein, da das Modell keine witterungsabhängige Saisonalität kennt. Das reale WP-Profil ist stark saisonal (Jan/Dez bis 50 kW, Sommer teils < 2 kW). Szenario B macht diese Abweichung sichtbar und quantifizierbar.

---

## TODO-Liste

### Hohe Priorität

- [ ] **Typenschild-Foto-Upload mit automatischer Datenerkennung**
  Beim Hinzufügen einer neuen Maschine soll der User ein Foto des Typenschilds hochladen können (`st.file_uploader`, Bildformate). Das Bild wird per Claude Vision API (multimodal) analysiert — das Modell liest Nennleistung, Spannung, Stromstärke, Baujahr, Modellbezeichnung etc. aus und befüllt das Maschinenformular automatisch vor. User kann die erkannten Werte anschließend manuell korrigieren.
  - Relevante Felder: `name` (Modellbezeichnung), `rated_power_kw` (aus Input-kW oder Strom × Spannung × √3 × PF)
  - Implementierung: neuer Hilfsbaustein in `core/` (kein Streamlit-Import), der Bild-Bytes + Prompt an Anthropic API sendet und strukturiertes JSON zurückgibt; UI-Integration in `ui/scenario_a.py` und `ui/scenario_b.py`
  - Fallback: wenn Erkennung unsicher, Felder leer lassen und User warnen

- [ ] **Witterungsabhängiges Verbrauchsmodell für Wärmepumpen**
  Neuer Maschinentyp "Wärmepumpe" in `core/models.py` und `core/calculator.py`. Statt fester Schichtzeiten: Synthese anhand eines Gradtagzahlen-Modells (DWD-Wetterdaten oder vereinfachte Sinuskurve Sommer/Winter). Ziel: saisonale Form der Synthese entspricht der realen WP-Kurve.

- [x] **UX: Maschineneingabe verbessern** *(2026-05-16)*
  Löschen- und Kopieren-Button pro Maschine direkt im Expander. Kopie erhält automatisch Präfix "Kopie: ".

- [ ] **UX: Charts und Visualisierungen verbessern**
  - Monatliche Verbrauchsübersicht als Balkendiagramm (besonders für Szenario B sinnvoll)
  - Im Vergleichs-Chart (Szenario B): Zeitraum-Selektion per Slider (nicht immer ganzes Jahr)
  - Anomalie-Intervalle direkt im Chart hervorheben (farbige Markierungen)

### Mittlere Priorität

- [ ] **Automatische kWh→kW-Konvertierung im CSV-Upload**
  Wenn erkannt wird, dass die hochgeladene CSV kWh-Werte enthält (Spaltenname "kWh" oder Werte dauerhaft < 1/4 der erwarteten kW-Größe), automatisch ×4 umrechnen und User informieren. Aktuell muss dies manuell vorab gemacht werden.

- [ ] **Szenario B: Jahresauswahl für mehrzeitige Lastgänge**
  Die Datei `rlm_2025_2026.csv` enthält Daten über mehrere Jahre. Aktuell filtert der Parser optional nach Jahr — diesen Filter in der UI als Dropdown zugänglich machen.

- [x] **Demo-Maschinen überarbeiten** *(2026-05-16)*
  `SAMPLE_MACHINES_WP` (4 Daikin-WPs) in `core/config.py` ergänzt. Beide Szenarien starten damit als Default. `SAMPLE_MACHINES` (Metallverarbeitung) bleibt erhalten.

- [ ] **Unit-Tests**
  Keine automatisierten Tests vorhanden. Mindest-Coverage:
  - `core/calculator.py`: Jahresenergie-Korrektheit, Schicht-Alignment
  - `core/comparator.py`: CSV-Formate (alle 4), kWh-Erkennung, Grenzfälle (leer, falsches Format)
  - `core/recommender.py`: Grenzwert-Cases (genau 100.000 kWh)

### Niedrige Priorität / Zukunft

- [ ] **FastAPI + React Migration**
  `core/` ist bereits vollständig UI-unabhängig. Nächster Schritt: FastAPI-Router in `api/` anlegen, der `core/`-Funktionen als HTTP-Endpoints exponiert.

- [ ] **Mehrsprachigkeit**
  Tool ist komplett auf Deutsch. Für spätere Internationalisierung `i18n`-Layer vorbereiten.

- [ ] **Konfigurierbare Tarif-Schwellenwerte**
  Aktuell hardcoded in `core/config.py`. Als Admin-Einstellung in der Sidebar oder per `.env`-Datei steuerbar machen.
