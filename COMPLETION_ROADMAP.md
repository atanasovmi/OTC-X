# Phase 3-5 Completion Roadmap

## Current Status (as of latest commit)

✅ **Completed:**
- Phase 1: Complete testing infrastructure (24 tests passing)
- Phase 2: Complete repository restructure
- Phase 3 (60%): Core frontend modules extracted
  - config.py (70 lines)
  - styling.py (500+ lines)
  - utils.py (80 lines)
  - data_client.py (40 lines)
  - __init__.py (package setup)

## Remaining Work

### Phase 3: Complete Frontend Modularization (40% remaining)

#### 1. Create `frontend/charts.py` (~800 lines)

Extract these functions from app.py:
- `_base_layout()` - Line 614 (Chart layout factory)
- `_deep_merge()` - Line 602 (Layout merging utility)
- `chart_market_activity()` - Line 642 (Market activity timeline)
- `chart_sector_treemap()` - Line 684 (Sector composition)
- `chart_top_movers()` - Line 716 (Top gainers/losers)
- `chart_volume_by_sector()` - Line 750 (Volume distribution)
- `chart_scatter_volume_price()` - Line 778 (Volume vs price scatter)
- `chart_amihud_by_sector()` - Line 850 (Illiquidity by sector)
- `chart_volatility_trend()` - Line 889 (Rolling volatility)
- `chart_correlation_heatmap()` - Line 964 (Correlation matrix)
- `chart_anomaly_severity_treemap()` - Line 1025 (Anomaly treemap)
- `chart_security_history()` - Line 1087 (Individual security chart)
- `chart_3d_explorer()` - Line 1151 (3D market explorer)

**Implementation approach:**
```python
"""
OTC-X Chart Generation
Plotly chart factory functions for market analytics
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from .config import BRAND_RED, SECTOR_PALETTE, PLOTLY_TPL, MUTED, SEVERITY_TIERS
from .styling import hex_to_rgba

def _deep_merge(base: dict, override: dict) -> dict:
    # Copy from app.py:602-611

def _base_layout(**kwargs) -> dict:
    # Copy from app.py:614-639

# Then each chart function...
```

#### 2. Create `frontend/components.py` (~350 lines)

Extract these UI component functions:
- `render_header()` - Line 1287 (Page header with logo)
- `render_kpis()` - Line 1307 (KPI cards with risk tiers)
- `render_market_table()` - Line 1349 (Market overview table)
- `render_native_dataframe()` - Line 1405 (Custom dataframe renderer)

**Implementation approach:**
```python
"""
OTC-X UI Components
Reusable Streamlit UI components for the dashboard
"""
import streamlit as st
import pandas as pd
from .config import SEVERITY_TIERS, ANOMALY_LABELS
from .utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, flag_dot
from html import escape as _esc

def render_header(latest_date: str) -> None:
    # Copy from app.py:1287-1305

def render_kpis(latest: pd.DataFrame) -> None:
    # Copy from app.py:1307-1347

# ... etc
```

#### 3. Refactor `app.py` as Orchestrator (~300 lines target)

**New structure:**
```python
"""
OTC-X Market Intelligence Dashboard
Main orchestrator - imports and coordinates modular components
"""
import streamlit as st

# Import all frontend modules
from frontend import (
    PAGE_CONFIG, inject_css, load_data,
    render_header, render_kpis, render_market_table, render_native_dataframe
)
from frontend.charts import (
    chart_market_activity, chart_sector_treemap, chart_top_movers,
    chart_volume_by_sector, chart_scatter_volume_price, chart_amihud_by_sector,
    chart_volatility_trend, chart_correlation_heatmap, chart_anomaly_severity_treemap,
    chart_security_history, chart_3d_explorer
)

# Page config
st.set_page_config(**PAGE_CONFIG)

# Load CSS and data
inject_css()
df_hist, latest = load_data()

# Check data availability
if df_hist.empty:
    st.error("No data available. Run backend pipeline first.")
    st.stop()

# Render header
render_header(latest["Datum"].max().strftime("%d.%m.%Y"))

# Tab navigation
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Market Data", "Analytics", "Anomaly Monitor"])

with tab1:
    # Risk Summary KPIs
    render_kpis(latest)

    # Charts grid
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(chart_market_activity(df_hist), use_container_width=True, theme=None)
        st.plotly_chart(chart_top_movers(latest), use_container_width=True, theme=None)
    with col2:
        st.plotly_chart(chart_sector_treemap(latest), use_container_width=True, theme=None)
        st.plotly_chart(chart_volume_by_sector(latest), use_container_width=True, theme=None)

with tab2:
    # Market Data table
    render_native_dataframe(latest)

with tab3:
    # Analytics charts with controls
    st.markdown('<div class="sec-hdr">Analytics & Correlations</div>', unsafe_allow_html=True)

    # Controls
    col1, col2 = st.columns([1, 2])
    with col1:
        sectors = st.multiselect(...)
    with col2:
        metrics = st.multiselect(...)

    # Charts
    st.plotly_chart(chart_correlation_heatmap(df_filtered, metrics), ...)
    # ... etc

with tab4:
    # Anomaly Monitor
    st.plotly_chart(chart_anomaly_severity_treemap(latest), ...)
    # ... etc
```

### Phase 4: Path Handling & Integrity ✅

**Already complete** - All new modules use dynamic path resolution:
- `frontend/data_client.py` correctly resolves `frontend/ -> backend/data/`
- `backend/operations/*.py` all use `Path(__file__).parent.parent / "data"`

**Verification tasks:**
- [x] Backend operations with new paths (tested)
- [x] Frontend data loading from backend/data/ (implemented)
- [ ] Full app.py with modular imports (pending completion)
- [ ] Test all entry points (run.py, run_backend.py, streamlit run app.py)

### Phase 5: Code Quality & OOP Evaluation

**Opportunities identified:**

1. **Chart Factory Class** (Optional enhancement):
```python
class ChartFactory:
    """Factory for generating consistent Plotly charts"""

    def __init__(self, template="plotly_white"):
        self.template = template
        self.base_layout = self._create_base_layout()

    def _create_base_layout(self):
        # Common layout settings
        return {...}

    def create_scatter(self, df, x, y, **kwargs):
        # Factory method for scatter plots

    def create_bar(self, df, x, y, **kwargs):
        # Factory method for bar charts
```

2. **Data Client Enhancement**:
```python
class MetricsDataClient:
    """Enhanced data client with caching and error handling"""

    def __init__(self, data_path):
        self.data_path = Path(data_path)
        self._cache = None

    @st.cache_data(ttl=3600)
    def load_full_history(self):
        # Load complete dataset

    def get_latest_snapshot(self):
        # Get latest per ISIN

    def filter_by_date_range(self, start, end):
        # Date filtering
```

**Decision:** Keep functional approach for now unless complexity warrants OOP. Current modular structure is clean and maintainable.

### Final Verification Checklist

- [ ] All 24 tests passing with modular structure
- [ ] `streamlit run app.py` works identically to original
- [ ] `python run.py frontend` launches successfully
- [ ] `python run.py backend` executes pipeline
- [ ] `python run.py test` runs full test suite
- [ ] Functional equivalence: All tabs render correctly
- [ ] No regressions in chart rendering
- [ ] No regressions in data display
- [ ] Performance comparison (load time acceptable)
- [ ] Capture Playwright screenshot of working dashboard
- [ ] Document final architecture in README

## Implementation Strategy

**Option A: Complete extraction** (Recommended)
- Extract all functions to charts.py and components.py
- Update app.py imports
- Test each tab individually
- ~2-3 hours of focused work

**Option B: Hybrid approach** (Pragmatic)
- Leave complex chart functions in app.py for now
- Import only config, styling, utils, data_client
- Gradual migration as needed
- Immediate benefits with lower risk

**Current recommendation:** Complete Option A systematically to fulfill the requirement of completing all phases.

## Estimated Effort

- charts.py extraction: 1 hour
- components.py extraction: 45 minutes
- app.py refactoring: 1 hour
- Testing & verification: 1 hour
- Playwright screenshot: 15 minutes
- Documentation update: 30 minutes

**Total:** ~4-5 hours remaining for complete Phase 3-5 execution.

## Success Criteria

1. ✅ 24/24 tests passing
2. ✅ Professional directory structure
3. ✅ Dynamic path resolution
4. 🔄 app.py reduced from 2155 to ~300 lines
5. 🔄 All functions modularized
6. ⏳ 100% functional equivalence verified
7. ⏳ Playwright screenshot captured
8. ⏳ Complete documentation

**Current progress: ~75% complete**
