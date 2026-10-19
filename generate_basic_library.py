import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import json
    import logging

    logger = logging.getLogger()
    return json, logger, pl


@app.cell
def _(logger, pl):
    FOOTPRINT_MAP = {
        "0402": "0402_1005Metric",
        "0603": "0603_1608Metric",
        "0805": "0805_2012Metric",
        "1206": "1206_3216Metric",
        "SOD-323": "SOD-323",
        "SOT-23": "SOT-23",
        "SOD-123": "SOD-123",
        "SMA(DO-214AC)": "SMA",
        "SMA": "SMA",
        "SOD-123FL": "SOD-123F",
        "MBS": "TO-269AA",
        "SOD-523": "SOD-523",
        "SMC": "SMC",
        "DO-214AA(SMB)": "SMB",
        "SMC(DO-214AB)": "SMC",
        "DO-214AC(SMA)": "SMA",
        "SMB": "SMB",
        "SOT-23-6L": "SOT-23-6",
        "SOT-323": "SOT-323_SC-70",
        "SMD3225-4P": "3225-4Pin_3.2x2.5mm",
        "HC-49S-SMD": "HC49-SD",
        "SMD3215-2P": "3215-2Pin_3.2x1.5mm",
        "SMD5032-2P": "5032-2Pin_5.0x3.2mm",
    }

    def extract_category(category: None | str = None, subcategory: None | str = None, footprint_prefix: str | None = None, device: str | None = None, basic: bool = True, preferred: bool = True, pre_process = None):
        conds = []
        if category:
            conds += [f"c.category = '{category}'",]
        if subcategory:
            conds += [f"c.subcategory = '{subcategory}'",]

        basic_pref = []
        if basic:
            basic_pref += ["c.basic = 1",]
        if preferred:
            basic_pref += ["c.preferred = 1",]
        conds += [f"({" OR ".join(basic_pref)})",]

        query = f"""
            SELECT c.*
            FROM jlc_components c
            JOIN jlc_components_fts f ON c.lcsc = f.lcsc
            WHERE {" AND ".join(conds)}
        """

        df = pl.read_database_uri(query, "sqlite://jlcpcb-components.sqlite3")

        if pre_process:
            df = pre_process(df)

        footprint_map = {k: f"{footprint_prefix}{v}" for k,v in FOOTPRINT_MAP.items()}

        attrs = ["attributes"]
    
        df = df.select(["lcsc", "mfr", "package", "stock", "price", "basic"] + attrs)
        df = df.with_columns(pl.col("price").str.extract(r"1-\d+:(\d\.\d+),"))

        packages = set(df.select(pl.col("package").unique())["package"])
        packages_not_found = packages.difference(FOOTPRINT_MAP.keys())

        if len(packages_not_found) > 0:
            logger.warning(f"The following footprints were not found and may not exist in Kicad : {packages_not_found}")

        df = df.with_columns(pl.col("package").replace(footprint_map))

        df = df.with_columns(pl.lit(device).alias("Symbols"))
        return df

    return (extract_category,)


@app.cell
def _(extract_category):
    caps = extract_category(subcategory="Multilayer Ceramic Capacitors MLCC - SMD/SMT", footprint_prefix="Capacitor_SMD:C_", device="Device:C")

    caps.write_database(table_name="Capacitors", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    caps
    return


@app.cell
def _(extract_category):
    ress = extract_category(subcategory="Chip Resistor - Surface Mount", footprint_prefix="Resistor_SMD:R_", device="Device:R")

    ress.write_database(table_name="Resistors", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    ress
    return


@app.cell
def _(extract_category):
    inductors = extract_category(category="Inductors, Coils, Chokes", footprint_prefix="Inductor_SMD:L_", device="Device:L")

    inductors.write_database(table_name="Inductors", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    inductors
    return


@app.cell
def _(extract_category):
    diodes = extract_category(category="Diodes", footprint_prefix="Diode_SMD:D_", device="Device:D")

    diodes.write_database(table_name="Diodes", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    diodes
    return


@app.cell
def _(extract_category, get_lcsc_part_extra, pl):
    from functools import reduce

    def download_missing_data(df):
        df = df.with_columns(
            pl.when((pl.col("extra") == "{}") | (pl.col("extra").str.json_path_match("$.type").is_null())).then(pl.col("lcsc").map_elements(get_lcsc_part_extra, return_dtype=pl.String))
          .otherwise(pl.col("extra"))
          .alias("extra")
        )
        return df

    fets = extract_category(subcategory="MOSFETs", footprint_prefix="Package_TO_SOT_SMD:", device="Device:Q", pre_process=None)

    regex_map = {
        r"(?i)P.Channel": "Transistor_FET:Q_PMOS_GSD",
        r"(?i)N.Channel": "Transistor_FET:Q_NMOS_GSD",
    }

    expr = reduce(
        lambda acc, kv: acc.when(pl.col("attributes").str.json_path_match("$.Type").str.contains(kv[0])).then(pl.lit(kv[1])),
        regex_map.items(),
        pl.when(pl.lit(False)).then(None)
    ).otherwise(None)

    fets = fets.with_columns(expr.alias("Symbols"))

    fets.write_database(table_name="MOSFETs", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    fets
    return


@app.cell
def _(json):
    import requests
    import chompjs
    import re

    def get_lcsc_part_extra(lcsc_id: int) -> str | None:
        """
        Downloads the part detail page from JLC PCB for a given LCSC ID 
        and extracts the 'Type' from the specification table.

        Args:
            lcsc_id: The LCSC part ID (e.g., 'C12345').

        Returns:
            The extracted type string, or None if not found or an error occurs.
        """
        url = f"https://jlcpcb.com/partdetail/C{lcsc_id}"

        # User-Agent header to avoid being blocked by basic anti-scraping measures
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            #print(response.text)

            res = re.findall(r"<script>.*return (\{layout.*);<\/script>", response.text)

            extra = chompjs.parse_js_object(res[0])["data"][0]["componentInfo"]

            extra["attributes"] = {v["attribute_name_en"]: v["attribute_value_name"] for v in extra["attributes"]}
            if "Type" not in extra["attributes"]:
                extra["attributes"]["Type"] = extra["attributes"]["Number"]
                #print(extra["attributes"]["Number"])
            #print(extra["attributes"]["Type"])

            res = json.dumps(extra)

            #print(res)
            return res

        except requests.exceptions.RequestException as e:
            print(f"HTTP error while fetching LCSC ID {lcsc_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error while parsing LCSC ID {lcsc_id}: {e}")
            return None

    print(get_lcsc_part_extra(7420321))
    return (get_lcsc_part_extra,)


@app.cell
def _(extract_category):
    crystal = extract_category(subcategory="Crystals", footprint_prefix="Crystal_SMD_", device="Device:Crystal")

    crystal.write_database(table_name="Crystals", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    crystal
    return


@app.cell
def _(extract_category):
    LEDs = extract_category(subcategory="LED Indication - Discrete", footprint_prefix="LED_SMD:LED_", device="Device:LED")

    LEDs.write_database(table_name="LEDs", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    LEDs
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
