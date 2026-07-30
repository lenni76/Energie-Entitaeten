# Leistung zu Energie

Custom Integration für Home Assistant zur Umrechnung von Leistung (mW, W, kW oder MW) in Energie (kWh).

## Funktionen

- Mehrere Leistungssensoren in einem Integrationseintrag
- Je Quelle: Gesamt-, Tages-, Wochen-, Monats- und Jahresenergie
- Direkte Zuordnung der erzeugten Entitäten zum Gerät des Quellsensors
- Negative Werte: nur positiv, Betrag oder vorzeichenbehaftet
- Integrationsmethoden: links, rechts oder trapezförmig
- Schutz vor falscher Nachberechnung nach langen Datenlücken
- Einstellbare tägliche Reset-Stunde und einstellbarer Wochenbeginn
- Persistente Zählerstände, Langzeitstatistiken und Diagnosedownload
- Automatische Migration von Version 1.x

## Installation über HACS

1. Dieses Repository öffentlich auf GitHub veröffentlichen.
2. In HACS unter **Benutzerdefinierte Repositories** die Repository-URL eintragen.
3. Kategorie **Integration** wählen und installieren.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Leistung zu Energie** suchen.

## Manuelle Installation

Den Ordner `custom_components/leistung_zu_energie` nach `/config/custom_components/` kopieren und Home Assistant neu starten.

## Hinweise zur Messung

Die Methode **Links** ist für viele Leistungssensoren mit stufenförmigen Messwerten sinnvoll. Bei langen Datenlücken wird das Intervall nicht nachträglich berechnet; dadurch werden unrealistische Energiesprünge vermieden.

## Update von 1.x

Die Konfiguration und vorhandenen Zählerstände des bisherigen einzelnen Leistungssensors werden beim ersten Start automatisch übernommen. Vor dem Update sollte trotzdem ein Home-Assistant-Backup erstellt werden.
