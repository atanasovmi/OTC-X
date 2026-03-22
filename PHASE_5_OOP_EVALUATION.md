# Phase 5: OOP Pattern Evaluation & Recommendations

## Executive Summary

After completing the functional modularization of the OTC-X frontend (Phase 3), this document evaluates opportunities for Object-Oriented Programming (OOP) patterns to further enhance code quality, maintainability, and extensibility.

**Recommendation**: The current functional, modular approach is **clean, maintainable, and appropriate** for this application's scale. OOP patterns are documented here for potential future enhancements if complexity increases.

---

## Current Architecture Assessment

### Strengths of Functional Approach

1. **Simplicity**: Functions are easy to understand and test in isolation
2. **Streamlit Compatibility**: Streamlit's functional paradigm aligns well with our approach
3. **Low Overhead**: No class instantiation or state management complexity
4. **Clear Data Flow**: Data passed explicitly through function parameters
5. **Easy Testing**: Pure functions are trivial to unit test

### Current Modular Structure

```
frontend/
├── config.py          # Constants (functional approach ideal)
├── styling.py         # CSS injection (functional approach ideal)
├── utils.py           # Formatting helpers (functional approach ideal)
├── data_client.py     # Data loading (functional with caching)
├── charts.py          # 11 chart functions (could benefit from OOP)
├── components.py      # 4 UI components (functional approach ideal)
└── __init__.py        # Package exports
```

---

## OOP Opportunities Evaluated

### 1. Chart Factory Class Pattern

**Concept**: Encapsulate chart creation logic in a class to reduce code duplication and provide consistent theming.

#### Current Implementation
```python
# charts.py - Functional approach
def _base_layout(**kwargs) -> dict:
    """Base layout with consistent styling"""
    # 60 lines of layout configuration
    pass

def chart_market_activity(df_hist: pd.DataFrame) -> go.Figure:
    fig = make_subplots(...)
    # Chart-specific logic
    fig.update_layout(**_base_layout(height=280, ...))
    return fig
```

#### Potential OOP Pattern
```python
# charts.py - OOP approach
class ChartFactory:
    """Factory for creating consistently-styled Plotly charts"""

    def __init__(self):
        self.theme = {
            "template": "plotly_white",
            "paper_bgcolor": "white",
            "font": {"family": "Inter", "color": "#1A1A2E"},
            # ... theme configuration
        }

    def _create_base_layout(self, **kwargs) -> dict:
        """Create base layout with theme"""
        layout = self.theme.copy()
        layout.update(kwargs)
        return layout

    def create_market_activity(self, df_hist: pd.DataFrame) -> go.Figure:
        """Create market activity chart"""
        fig = make_subplots(...)
        fig.update_layout(**self._create_base_layout(height=280))
        return fig

# Usage in app.py
chart_factory = ChartFactory()
fig = chart_factory.create_market_activity(df_hist)
```

**Pros**:
- Encapsulates theming logic
- Easier to create variations (dark mode, different color schemes)
- State can store theme preferences
- Cleaner separation of concerns

**Cons**:
- Added complexity for marginal benefit at current scale
- Breaks Streamlit's functional idiom
- Requires instantiation before use
- Harder to cache individual charts with `@st.cache_data`

**Recommendation**: **Defer** - Current functional approach with `_base_layout()` helper is sufficient. Consider if:
- Multiple themes are needed
- Chart count exceeds 20+
- Dynamic theme switching becomes a requirement

---

### 2. Enhanced Data Client Class

**Concept**: Upgrade `data_client.py` from functional to class-based for better state management and caching control.

#### Current Implementation
```python
# data_client.py - Functional
@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and process data"""
    path = Path(__file__).parent.parent / "backend" / "data" / "daily_metrics.parquet"
    df = pd.read_parquet(path)
    # Processing...
    return df_hist, latest
```

#### Potential OOP Pattern
```python
# data_client.py - OOP approach
class DataClient:
    """Client for loading and caching OTC-X market data"""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or (Path(__file__).parent.parent / "backend" / "data")
        self._cache = {}

    @st.cache_data(ttl=3600)
    def load_metrics(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load daily metrics with caching"""
        path = self.data_dir / "daily_metrics.parquet"
        df = pd.read_parquet(path)
        return self._process(df)

    def load_securities(self) -> pd.DataFrame:
        """Load securities list"""
        return pd.read_csv(self.data_dir / "securities.csv")

    def load_trades(self, isin: str) -> pd.DataFrame:
        """Load trades for specific ISIN"""
        return pd.read_parquet(self.data_dir / "trades" / f"{isin}.parquet")

    def _process(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Process raw data"""
        # Processing logic
        return df_hist, latest

# Usage in app.py
data_client = DataClient()
df_hist, latest = data_client.load_metrics()
```

**Pros**:
- Centralizes data access logic
- Easy to add new data loading methods
- Path configuration in one place
- Testable with dependency injection

**Cons**:
- Overkill for current single-data-source scenario
- Streamlit caching works better with top-level functions
- Adds ceremony without clear benefit

**Recommendation**: **Defer** - Consider if:
- Multiple data sources are added
- Complex data transformations are needed
- Database connections replace file-based storage

---

### 3. State Management Class

**Concept**: Encapsulate Streamlit session state in a class for better organization.

#### Current Implementation
```python
# app.py - Direct session state
selected_tier = st.session_state.get("anomaly_tier", None)
if st.button("Show Alert"):
    st.session_state["anomaly_tier"] = "Alert"
    st.rerun()
```

#### Potential OOP Pattern
```python
# state.py - OOP approach
class AppState:
    """Manages application session state"""

    def __init__(self):
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'anomaly_tier': None,
                'vol_selected_sector': None,
            }

    @property
    def anomaly_tier(self) -> str | None:
        return st.session_state.app_state['anomaly_tier']

    @anomaly_tier.setter
    def anomaly_tier(self, value: str | None):
        st.session_state.app_state['anomaly_tier'] = value

    def clear_filters(self):
        self.anomaly_tier = None
        self.vol_selected_sector = None

# Usage in app.py
state = AppState()
if st.button("Show Alert"):
    state.anomaly_tier = "Alert"
    st.rerun()
```

**Pros**:
- Type-safe property access
- Centralized state logic
- Easy to add state validation
- Clear state mutation points

**Cons**:
- Streamlit session state is already simple and effective
- Adds boilerplate for minimal benefit
- Property decorators add indirection

**Recommendation**: **Defer** - Current direct session state usage is clean. Consider if:
- State becomes complex (10+ fields)
- State validation rules are needed
- Cross-tab state synchronization becomes challenging

---

### 4. Component Base Class

**Concept**: Create base class for UI components with common rendering logic.

#### Potential OOP Pattern
```python
# components.py - OOP approach
class UIComponent:
    """Base class for UI components"""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def render(self):
        """Override in subclass"""
        raise NotImplementedError

class KPIComponent(UIComponent):
    """KPI card renderer"""

    def render(self):
        total_vol = self.df["volume_today_chf"].sum()
        # ... render logic
        st.markdown(html, unsafe_allow_html=True)

class HeaderComponent(UIComponent):
    """Header renderer"""

    def render(self, latest_date: str):
        st.markdown(f"""<div class="otcx-header">...</div>""")

# Usage
header = HeaderComponent(latest)
header.render("22.03.2026")
```

**Pros**:
- Encapsulates component state
- Could enable component lifecycle hooks
- Cleaner separation if components grow

**Cons**:
- Over-engineering for current 4 components
- Streamlit's functional approach is simpler
- Components don't benefit from shared state

**Recommendation**: **Not Recommended** - Functional component approach is ideal for Streamlit. The current implementation is clean and appropriate.

---

## Recommended Incremental OOP Adoption Path

If future complexity warrants OOP patterns, adopt in this order:

### Stage 1: DataClient Enhancement (Low Priority)
**Trigger**: When adding 3+ new data sources
```python
class DataClient:
    def load_metrics(self) -> tuple[pd.DataFrame, pd.DataFrame]: ...
    def load_securities(self) -> pd.DataFrame: ...
    def load_trades(self, isin: str) -> pd.DataFrame: ...
```

### Stage 2: ChartFactory (Medium Priority)
**Trigger**: When implementing theme switching or chart count >20
```python
class ChartFactory:
    def __init__(self, theme: str = "light"): ...
    def create_market_activity(self, df: pd.DataFrame) -> go.Figure: ...
```

### Stage 3: State Management (Low Priority)
**Trigger**: When session state exceeds 10 fields with validation needs
```python
class AppState:
    @property
    def anomaly_tier(self) -> str | None: ...
```

---

## Phase 5 Conclusion

**The current functional, modular architecture is the right choice** for the OTC-X application. Key reasons:

1. **Appropriate Scale**: 15 modules, 11 charts, 4 components - manageable with functions
2. **Streamlit Alignment**: Functional paradigm matches Streamlit's design philosophy
3. **Simplicity**: Pure functions are easier to test, understand, and maintain
4. **No Premature Optimization**: OOP patterns would add complexity without clear benefit

### When to Reconsider OOP

Re-evaluate if any of these thresholds are reached:
- Chart count exceeds 20 functions
- Data sources multiply (database, APIs, multiple files)
- Theme switching becomes a requirement
- State management complexity increases significantly
- Team size grows and needs stricter contracts

### Current Architecture Score

| Criterion | Score | Justification |
|-----------|-------|---------------|
| **Maintainability** | 9/10 | Clean modules, clear separation |
| **Testability** | 9/10 | Pure functions, easy isolation |
| **Scalability** | 8/10 | Can grow modularly as-is |
| **Simplicity** | 10/10 | Functional approach is straightforward |
| **Readability** | 9/10 | 790-line orchestrator, clear flow |

**Overall Assessment**: The refactored architecture is production-ready and follows best practices for a Streamlit application of this complexity.

---

## Documentation

This evaluation is preserved for future reference. OOP patterns documented here can be implemented incrementally if complexity warrants them. The current functional approach should not be changed without clear requirements driving the need.

---

**Phase 5 Status**: ✅ Complete - OOP evaluation concluded with recommendation to maintain functional architecture.
