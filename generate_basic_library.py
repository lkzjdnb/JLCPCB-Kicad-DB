import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    To add :
    - Inductors
    - MOSFETs
    - Diodes
    """)
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import json
    import logging

    logger = logging.getLogger()
    return json, logger, mo, pl


@app.cell
def _(json, logger, pl):
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
        "SOT-323": "SOT-323_SC-70"
    }

    def extract_category(category: None | str = None, subcategory: None | str = None, footprint_prefix: str | None = None, device: str | None = None, basic: bool = True, preferred: bool = True):
        conds = []
        if category:
            conds += [f"ct.category = '{category}'",]
        if subcategory:
            conds += [f"ct.subcategory = '{subcategory}'",]

        basic_pref = []
        if basic:
            basic_pref += ["c.basic = 1",]
        if preferred:
            basic_pref += ["c.preferred = 1",]
        conds += [f"({" OR ".join(basic_pref)})",]

        query = f"""
            SELECT c.*
            FROM components c
            JOIN components_fts f ON c.lcsc = f.lcsc
            JOIN categories ct ON c.category_id = ct.id
            WHERE {" AND ".join(conds)}
        """

        df = pl.read_database_uri(query, "sqlite://jlcpcb-components.sqlite3")

        footprint_map = {k: f"{footprint_prefix}{v}" for k,v in FOOTPRINT_MAP.items()}

        attrs = []
        if len(df.select(pl.col("extra"))) > 0:
            attrs = list(json.loads(df.select(pl.col("extra").str.json_path_match(r"$.attributes").drop_nulls())["extra"][0]).keys())
            attrs_dtype = pl.Struct([
                pl.Field(k, pl.String) for k in attrs
            ])

            df = df.with_columns(pl.col("extra").str.json_path_match(r"$.attributes").str.json_decode(attrs_dtype)).unnest("extra")

        df = df.select(["lcsc", "mfr", "package", "stock", "price", "basic"] + attrs)
        df = df.with_columns(pl.col("price").str.json_path_match(r"$[0].price"))

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
    inductors = extract_category(category="Inductors/Coils/Transformers", footprint_prefix="Inductor_SMD:L_", device="Device:L")

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
def _(extract_category, pl):
    from functools import reduce

    fets = extract_category(subcategory="MOSFETs", footprint_prefix="Package_TO_SOT_SMD:", device="Device:Q")

    regex_map = {
        r"(?i)P.Channel": "Device:Q_PMOS",
        r"(?i)N.Channel": "Device:Q_NMOS",
    }

    expr = reduce(
        lambda acc, kv: acc.when(pl.col("Type").str.contains(kv[0])).then(pl.lit(kv[1])),
        regex_map.items(),
        pl.when(pl.lit(False)).then(None)
    ).otherwise(None)

    fets.write_database(table_name="MOSFETs", connection="sqlite:///jlcpcb-basic-kicad.sqlite3", if_table_exists="replace")

    fets.with_columns(expr.alias("Symbols"))
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
