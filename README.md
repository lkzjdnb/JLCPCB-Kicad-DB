# JLCPCB-Kicad-DB

A KiCad database library of JLCPCB **Basic** and **Preferred** components.

## Overview

This project turns the JLCPCB parts database into a ready-to-use [KiCad Database Library](https://docs.kicad.org/). It extracts the Basic and Preferred components (the cheap ones, with no extended-part fee at JLCPCB) into a compact SQLite database, together with a `.kicad_dbl` config that maps each part to its KiCad symbol, footprint, value and JLC part number.

The result: you can search and place JLCPCB Basic parts straight from KiCad's symbol chooser, with stock, price, MPN and JLC ID attached.

## Features

- Covers **Capacitors, Resistors, Inductors, Diodes, MOSFETs, Crystals and LEDs**.
- Automatic JLC package → KiCad footprint mapping and per-category symbol assignment.
- Live stock, price, MPN and JLC (LCSC) part number fields.
- JSON attributes (voltage rating, tolerance, current, …) flattened into queryable columns.
- Scrapes jlcpcb.com for MOSFET data missing from the source database.
- Rebuilt automatically every day via GitHub Actions.

## How it works

```
source DB (jlcpcb-components.sqlite3)
        │  generate_basic_library.py  (marimo notebook)
        ▼
jlcpcb-basic-kicad.sqlite3   +   jlcpcb-basic.kicad_dbl
        │  ODBC DSN "JLCPCBDB"
        ▼
      KiCad
```

## Repository layout

| Path | Description |
| --- | --- |
| `generate_basic_library.py` | Marimo notebook that generates the KiCad-ready database. |
| `jlcpcb-basic.kicad_dbl` | KiCad database-library config (tables, columns, symbol/footprint fields). |
| `.github/workflows/update-db.yml` | CI job that regenerates and publishes the database daily. |
| `jlcpcb-basic-kicad.sqlite3` | Generated output (not committed; published to GitHub Pages). |

## Requirements

- Python **3.13+** and [uv](https://docs.astral.sh/uv/)
- KiCad with an ODBC driver (for using the library in KiCad)

## Quick start

Regenerate the database locally:

```bash
# 1. Install dependencies
uv sync

# 2. Download the source database
wget https://cdfer.github.io/jlcpcb-parts-database/jlcpcb-components.sqlite3

# 3. Generate the KiCad-ready database
uv run python generate_basic_library.py
```

This produces `jlcpcb-basic-kicad.sqlite3` with one table per component category.

To explore or edit the generator, open it as a notebook:

```bash
uv run marimo edit generate_basic_library.py
```

## Using in KiCad

1. Configure an ODBC DSN named **`JLCPCBDB`** pointing at `jlcpcb-basic-kicad.sqlite3`.
2. In KiCad, open **Preferences → Manage Symbol/Footprint Libraries** (Database Libraries) and add `jlcpcb-basic.kicad_dbl`.

## Automation

The GitHub Actions workflow (`.github/workflows/update-db.yml`) runs on a daily schedule (03:00 UTC), on pushes to `master`, and manually via `workflow_dispatch`. It downloads the latest source database, runs the generator, and deploys `jlcpcb-basic-kicad.sqlite3` to GitHub Pages.

## Credits

Component data comes from [cdfer/jlcpcb-parts-database](https://github.com/cdfer/jlcpcb-parts-database), sourced from [JLCPCB](https://jlcpcb.com/).
