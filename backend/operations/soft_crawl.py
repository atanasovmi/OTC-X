import pandas as pd
import requests
from pathlib import Path

def run_crawl():
    print("Fetching securities dynamically from OTC-X API...")
    url = "https://www.otc-x.ch/api/market/securities"
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'OTC-X-DataProcessor/1.0'
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    items = response.json().get('items', [])
    data = []
    
    for item in items:
        # Extract desired fields
        data.append({
            "NAME": item.get("name", "Unknown"),
            "SEKTOR": item.get("sector", "Unknown"),
            "VALOR": item.get("valor", ""),
            "ISIN": item.get("isin", "")
        })
        
    df = pd.DataFrame(data)
    
    # Define output paths
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    path_sec = data_dir / "securities.csv"
    path_enr = data_dir / "securities_enriched.csv"
    
    # Save to CSV without index so the header is exactly: NAME,SEKTOR,VALOR,ISIN
    df.to_csv(path_sec, index=False)
    df.to_csv(path_enr, index=False)
    
    print(f"Fertig! {len(df)} Valoren extrahiert.")
    print(f"Gespeichert in: {path_sec.resolve()}")
    print(f"Gespeichert in: {path_enr.resolve()}")
    return df

if __name__ == "__main__":
    df = run_crawl()
    print(df.head())
