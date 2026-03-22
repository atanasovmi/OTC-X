"""
OTC-X Data Ingestion Pipeline
Consolidates and cleans 244+ Swiss trade CSVs into master datasets.
"""
import sys
from pathlib import Path

import polars as pl

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from otcx_paths import DATA_DIR

def build_master_parquet():
    raw_data_dir = DATA_DIR / "trades"
    output_parquet = DATA_DIR / "master_trades.parquet"
    output_csv = DATA_DIR / "master_trades_cleaned.csv"

    print("=" * 60)
    print("OTC-X Data Ingestion Pipeline")
    print("=" * 60)
    print(f"Scanning: {raw_data_dir.resolve()}")

    # 1. Discovery & Filtering
    all_files = list(raw_data_dir.glob("*.csv"))
    valid_files = []
    skipped_count = 0

    for file_path in all_files:
        if file_path.stat().st_size < 100:
            skipped_count += 1
            print(f"  [SKIP] {file_path.name} (empty/header-only)")
        else:
            valid_files.append(file_path)

    print(f"\nFound {len(all_files)} files total.")
    print(f"Processing {len(valid_files)} valid files...")
    print(f"Skipped {skipped_count} empty/header-only files.\n")

    if not valid_files:
        print("ERROR: No valid files to process.")
        return

    # 2. Ingestion
    dfs = []
    for f in valid_files:
        try:
            # Read CSV with all columns as String (safest for dirty data)
            df_temp = pl.read_csv(
                f,
                separator=",",
                has_header=True,
                infer_schema_length=0,  # Force all String types
                ignore_errors=True
            )
            
            # Normalize headers (strip whitespace: " Datum" -> "Datum")
            df_temp.columns = [c.strip() for c in df_temp.columns]
            
            if not df_temp.is_empty():
                dfs.append(df_temp)
                
        except Exception as e:
            print(f"  [ERROR] Failed to read {f.name}: {e}")

    if not dfs:
        print("ERROR: No valid data found after reading files.")
        return

    # Concatenate all dataframes
    df_raw = pl.concat(dfs)
    print(f"Raw rows ingested: {len(df_raw):,}")

    # 3. Scrubbing & Casting
    print("\nApplying data cleaning transformations...")


    df_clean = df_raw.with_columns([
        # Isin: Trim whitespace
        pl.col("Isin").str.strip_chars().alias("Isin"),
        
        # Datum: Parse DD.MM.YYYY to Date
        pl.col("Datum").str.strip_chars().str.strptime(pl.Date, "%d.%m.%Y", strict=False),
        
        # Zeit: Keep as-is (string time)
        pl.col("Zeit").str.strip_chars(),
        
        # Kurs: Clean whitespace -> Remove ' -> Replace , -> Cast
        pl.col("Kurs")
          .str.strip_chars()            # Critical fix: remove leading/trailing spaces
          .str.replace_all("'", "")     # Remove thousands separator
          .str.replace(",", ".")         # Replace comma with dot
          .cast(pl.Float64, strict=False),
        
        # Volumen: Clean whitespace -> Remove ' -> Replace , -> Cast
        pl.col("Volumen")
          .str.strip_chars()            # Critical fix
          .str.replace_all("'", "")
          .str.replace(",", ".")
          .cast(pl.Float64, strict=False),
        
        # Off Book: Boolean conversion (X = True, else False)
        (pl.col("Off Book").str.strip_chars() == "X")
          .fill_null(False)
          .alias("Off Book")
    ])

    # 4. Deduplication
    df_final = df_clean.unique()
    
    
    # Validation: Quality Check
    n_total = len(df_final)
    n_valid_kurs = df_final.filter(pl.col("Kurs").is_not_null()).height
    print(f"Data Quality: {n_valid_kurs}/{n_total} records have valid Price/Volume data ({n_valid_kurs/n_total:.1%})")
    
    print(f"Rows after deduplication: {len(df_final):,}")

    # 5. Dual Output
    print("\nWriting output files...")
    
    # Parquet (binary, compressed) - Keep native types for analytics
    df_final.write_parquet(output_parquet, compression="zstd")
    print(f"  [OK] Parquet: {output_parquet.name} ({output_parquet.stat().st_size / 1024:.1f} KB)")
    
    # CSV (Formatted for "Original" look)
    # We create a display-specific version
    print("  -> Formatting data for CSV output...")
    
    df_display = df_final.with_columns([
        # Datum -> String DD.MM.YYYY
        pl.col("Datum").dt.strftime("%d.%m.%Y"),
        
        # Kurs/Volumen -> String .6f
        pl.col("Kurs").map_elements(lambda x: f"{x:.6f}", return_dtype=pl.String),
        pl.col("Volumen").map_elements(lambda x: f"{x:.6f}", return_dtype=pl.String),
        
        # Off Book -> Map True to "X", False to ""
        pl.when(pl.col("Off Book")).then(pl.lit("X")).otherwise(pl.lit("")).alias("Off Book")
    ])
    
    # Write manually to enforce ", " separator (comma + space)
    with open(output_csv, "w", encoding="utf-8") as f:
        # Write Header with spaces
        header = ["Isin", "Datum", "Zeit", "Kurs", "Volumen", "Off Book"]
        f.write(", ".join(header) + "\n")
        
        # Write rows
        # Using Polars efficient iter_rows is okay for 130k, or we can construct a single csv string column?
        # Constructing a single string column is vectorised and faster.
        
        # Create a single joined string column
        csv_lines = df_display.select(
            pl.concat_str(
                [
                    pl.col("Isin"),
                    pl.col("Datum"),
                    pl.col("Zeit"),
                    pl.col("Kurs"),
                    pl.col("Volumen"),
                    pl.col("Off Book")
                ],
                separator=", "
            ).alias("line")
        )
        
        # Write efficiently
        f.write("\n".join(csv_lines["line"].to_list()))
        f.write("\n") # standard EOF newline

    print(f"  [OK] CSV: {output_csv.name} ({output_csv.stat().st_size / 1024:.1f} KB)")

    # 6. Audit Summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Processed {len(valid_files)} files, Skipped {skipped_count} empty files.")
    print(f"Total rows: {len(df_final):,}")
    print("\nSchema:")
    for col, dtype in df_final.schema.items():
        print(f"  {col:15} {dtype}")
    
    print("\nSample Data (first 5 rows):")
    try:
        print(df_final.head(5))
    except UnicodeEncodeError:
        print("  [Note: Sample display skipped due to console encoding limitations]")
        print(f"  -> View full data in: {output_csv.name}")
    
    print("=" * 60)
    print("Pipeline complete! [SUCCESS]")

if __name__ == "__main__":
    build_master_parquet()
