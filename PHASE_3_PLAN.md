# Phase 3: Frontend Modularization Plan

## Status: In Progress

## Completed So Far
- ✅ Created `/frontend/config.py` with all constants and configuration
- ✅ Analyzed app.py structure (2155 lines, 30+ functions)

## Module Structure Planned

### 1. config.py (✅ Complete)
- Brand colors and constants
- Sector palette
- Anomaly scoring mappings
- Page configuration

### 2. styling.py (Next)
- `inject_css()` - Main CSS injection
- `_hex_to_rgba()` - Color conversion utility
- All CSS definitions (~500 lines of styles)

### 3. utils.py (Next)
- `fmt_chf()` - Currency formatting
- `fmt_num()` - Number formatting
- `fmt_pct()` - Percentage formatting
- `pct_cls()` - CSS class helper
- `score_badge()` - Anomaly badge HTML
- `_flag_dot()` - Boolean flag indicator

### 4. data_client.py (Next)
- `load_data()` - Main data loading with caching
- Path resolution to backend/data/

### 5. charts.py (Next)
- `_base_layout()` - Chart layout factory
- `_deep_merge()` - Layout merging utility
- `chart_market_activity()` - Market timeline
- `chart_sector_treemap()` - Sector composition
- `chart_top_movers()` - Top gainers/losers
- `chart_volume_by_sector()` - Volume distribution
- `chart_scatter_volume_price()` - Volume/price scatter
- `chart_amihud_by_sector()` - Illiquidity by sector
- `chart_volatility_trend()` - Volatility timeline
- `chart_correlation_heatmap()` - Correlation matrix
- `chart_anomaly_severity_treemap()` - Anomaly treemap
- `chart_security_history()` - Individual security chart
- `chart_3d_explorer()` - 3D market explorer

### 6. components.py (Next)
- `render_header()` - Page header with logo
- `render_kpis()` - KPI cards
- `render_market_table()` - Market overview table
- `render_native_dataframe()` - Custom dataframe renderer

### 7. app.py (Refactored)
- Import all modules
- Streamlit configuration
- Tab navigation logic
- Main orchestration
- Reduced from 2155 lines to ~300 lines

## Benefits of Modularization

1. **Maintainability**: Each module has a single, clear purpose
2. **Testability**: Individual functions can be unit tested
3. **Reusability**: Components can be imported in other projects
4. **Readability**: Developers can quickly navigate to relevant code
5. **Collaboration**: Multiple developers can work on different modules
6. **Performance**: Selective imports reduce memory footprint

## Implementation Notes

- All imports use absolute paths from frontend/
- Path resolution updated for backend/data/ location
- Functions remain functionally identical
- No behavioral changes, only structural
- OOP patterns will be evaluated in Phase 5
