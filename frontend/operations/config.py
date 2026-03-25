"""Shared brand constants, colour palettes, and anomaly classification maps.

This module centralises every visual and domain constant used across the
OTC-X dashboard so that the colour language, anomaly taxonomy, and brand
identity remain consistent in charts, components, and CSS.
"""

# ─────────────────────────────────────────────
#  Brand Constants
# ─────────────────────────────────────────────
BRAND_RED    = "#B22222"
BRAND_DARK   = "#1A1A2E"
GREEN_POS    = "#28A745"
RED_NEG      = "#DC3545"
BORDER_COL   = "#CED4DA"
MUTED        = "#1A1A2E"   # near-black for maximum contrast on white backgrounds
MUTED_SEC    = "#1A1A2E"   # near-black secondary text for maximum contrast
PLOTLY_TPL   = "plotly_white"

SECTOR_PALETTE = {
    "Banken":                         "#B22222",
    "Energie":                        "#F28B00",
    "Immobilien":                     "#2E86AB",
    "Industrie":                      "#5C6BC0",
    "Bergbahnen":                     "#43A047",
    "Beteiligungsgesellschaften":     "#AB47BC",
    "Nahrungsmittel und Getraenke":   "#00ACC1",
    "Tourismus,Freizeit,Sonstiges":   "#FF7043",
    "Transport,Verkehr,Logistik":     "#8D6E63",
    "Medien":                         "#78909C",
}

# Shared anomaly score labels and colours (used in badge helper and distribution chart)
ANOMALY_LABELS: dict[int, str] = {
    0: "Clean", 1: "Watch", 2: "Alert", 3: "Critical",
    4: "Critical", 5: "Severe", 6: "Severe", 7: "Extreme",
}
ANOMALY_COLORS: dict[int, str] = {
    0: "#28A745", 1: "#FFC107", 2: "#FD7E14",
    3: "#DC3545", 4: "#DC3545", 5: "#7D1128",
    6: "#7D1128", 7: "#4A0010",
}

# Severity tier grouping for clickable anomaly categories
SEVERITY_TIERS = {
    "Clean":    [0],
    "Alert":    [1, 2],
    "Critical": [3, 4],
    "Severe":   [5, 6],
    "Extreme":  [7],
}
