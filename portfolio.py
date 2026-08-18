"""Estado de situación del portafolio.

Lee las operaciones desde data/trades.csv (y las conversiones de divisa desde
data/forex.csv), calcula posiciones abiertas y P&G con criterio FIFO — con las
comisiones incluidas en la base de coste, igual que el extracto del bróker — y
valora las posiciones a precio de mercado vía yfinance.

Moneda principal: EUR (configurable a USD en la barra lateral). Pestañas:
Resumen, Rendimiento (P&G diaria y comparación con benchmark), Riesgo
(atribución por sector, volatilidad, drawdown) y Operaciones.

Para actualizar los datos: editar data/trades.csv en GitHub (un commit
redespliega la app en Streamlit Community Cloud), o subir un CSV desde la
barra lateral para una consulta puntual.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import yfinance as yf

    HAS_YF = True
except ImportError:
    HAS_YF = False

# Paleta validada: azul (slot 1) = serie principal / positivo, naranja (slot 2)
# = serie secundaria, rojo = negativo (par divergente azul↔rojo).
BLUE = "#2a78d6"
ORANGE = "#eb6834"
RED = "#e34948"
GRID = "rgba(137, 135, 129, 0.25)"
MUTED = "#898781"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

BASE_DIR = Path(__file__).parent
TRADES_CSV = BASE_DIR / "data" / "trades.csv"
FOREX_CSV = BASE_DIR / "data" / "forex.csv"
SECTORS_CSV = BASE_DIR / "data" / "sectors.csv"

TRADE_COLUMNS = {"symbol", "datetime", "quantity", "price", "fee"}

BENCHMARKS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Mundo (VT)": "VT",
}

st.set_page_config(page_title="Mi Portafolio", page_icon="📊", layout="wide")


# ---------------------------------------------------------------- datos

def parse_trades(raw: pd.DataFrame) -> pd.DataFrame:
    missing = TRADE_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(
            "Faltan columnas en el CSV de operaciones: " + ", ".join(sorted(missing))
        )
    trades = raw.dropna(subset=["symbol"]).copy()
    trades["symbol"] = trades["symbol"].astype(str).str.strip().str.upper()
    trades["datetime"] = pd.to_datetime(trades["datetime"])
    for col in ("quantity", "price", "fee"):
        trades[col] = pd.to_numeric(trades[col])
    trades["fee"] = trades["fee"].fillna(0.0).abs()
    return trades.sort_values("datetime").reset_index(drop=True)


def load_forex() -> pd.DataFrame | None:
    if not FOREX_CSV.exists():
        return None
    fx = pd.read_csv(FOREX_CSV)
    fx["datetime"] = pd.to_datetime(fx["datetime"])
    return fx


def load_sectors() -> dict[str, str]:
    if not SECTORS_CSV.exists():
        return {}
    sectors = pd.read_csv(SECTORS_CSV).dropna()
    return dict(
        zip(sectors["symbol"].str.strip().str.upper(), sectors["sector"].str.strip())
    )


@st.cache_data(ttl=86400, show_spinner=False)
def lookup_sector(symbol: str) -> str | None:
    if not HAS_YF:
        return None
    try:
        return yf.Ticker(symbol).info.get("sector")
    except Exception:
        return None


def fifo_summary(trades: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Por símbolo: cantidad abierta, coste FIFO (comisiones incluidas),
    P&G realizada y comisiones acumuladas. Todo en USD."""
    rows: list[dict] = []
    warnings: list[str] = []
    for symbol, ops in trades.groupby("symbol", sort=True):
        lots: list[list[float]] = []  # [cantidad restante, coste unitario]
        realized = 0.0
        fees = 0.0
        for op in ops.sort_values("datetime").itertuples():
            fees += op.fee
            if op.quantity > 0:
                unit_cost = (op.quantity * op.price + op.fee) / op.quantity
                lots.append([op.quantity, unit_cost])
            elif op.quantity < 0:
                to_close = -op.quantity
                proceeds = to_close * op.price - op.fee
                matched_cost = 0.0
                while to_close > 1e-9 and lots:
                    take = min(lots[0][0], to_close)
                    matched_cost += take * lots[0][1]
                    lots[0][0] -= take
                    to_close -= take
                    if lots[0][0] <= 1e-9:
                        lots.pop(0)
                if to_close > 1e-9:
                    warnings.append(
                        f"{symbol}: la venta del {op.datetime:%Y-%m-%d} supera lo "
                        "comprado hasta esa fecha; se ignora el exceso."
                    )
                    proceeds -= to_close * op.price
                realized += proceeds - matched_cost
        qty = sum(lot[0] for lot in lots)
        cost = sum(lot[0] * lot[1] for lot in lots)
        rows.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "cost_basis": cost,
                "avg_cost": cost / qty if qty > 1e-9 else float("nan"),
                "realized": realized,
                "fees": fees,
            }
        )
    return pd.DataFrame(rows), warnings


# ---------------------------------------------------------------- precios

@st.cache_data(ttl=600, show_spinner=False)
def fetch_prices(symbols: tuple[str, ...]) -> dict[str, float]:
    if not HAS_YF or not symbols:
        return {}
    prices: dict[str, float] = {}
    try:
        closes = yf.download(
            list(symbols), period="5d", progress=False, auto_adjust=True
        )["Close"]
        if isinstance(closes, pd.Series):
            closes = closes.to_frame(symbols[0])
        last = closes.ffill().iloc[-1]
        for sym in symbols:
            value = last.get(sym)
            if value is not None and pd.notna(value):
                prices[sym] = float(value)
    except Exception:
        pass
    for sym in symbols:
        if sym in prices:
            continue
        try:
            prices[sym] = float(yf.Ticker(sym).fast_info["last_price"])
        except Exception:
            pass
    return prices


@st.cache_data(ttl=600, show_spinner=False)
def fetch_eurusd() -> float | None:
    rates = fetch_prices(("EURUSD=X",))
    return rates.get("EURUSD=X")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history(symbols: tuple[str, ...], start: str) -> pd.DataFrame:
    if not HAS_YF or not symbols:
        return pd.DataFrame()
    try:
        closes = yf.download(
            list(symbols), start=start, progress=False, auto_adjust=True
        )["Close"]
    except Exception:
        return pd.DataFrame()
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(symbols[0])
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    return closes.dropna(how="all")


def daily_position_value(trades: pd.DataFrame, closes: pd.DataFrame) -> pd.Series:
    idx = closes.index
    total = pd.Series(0.0, index=idx)
    for symbol, ops in trades.groupby("symbol"):
        if symbol not in closes.columns:
            continue
        qty = ops.set_index("datetime")["quantity"].sort_index().cumsum()
        qty.index = qty.index.normalize()
        qty = qty[~qty.index.duplicated(keep="last")]
        daily_qty = (
            qty.reindex(idx.union(qty.index)).ffill().reindex(idx).fillna(0.0)
        )
        total = total + daily_qty * closes[symbol].ffill().fillna(0.0)
    return total


def daily_flows(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    """Flujo externo diario en USD: dinero que entra (+) o sale (−) de las
    posiciones, comisiones incluidas — para netear la P&G diaria y el TWR."""
    flows = (trades["quantity"] * trades["price"] + trades["fee"]).groupby(
        trades["datetime"].dt.normalize()
    ).sum()
    aligned = pd.Series(0.0, index=idx)
    for date, value in flows.items():
        pos = idx.searchsorted(date)
        if pos >= len(idx):
            pos = len(idx) - 1
        aligned.iloc[pos] += value
    return aligned


def twr_index(values: pd.Series, flows: pd.Series) -> pd.Series:
    """Índice de rentabilidad ponderada por tiempo (base 100), con los flujos
    asumidos a inicio de día."""
    out = pd.Series(index=values.index, dtype=float)
    level = 100.0
    prev = 0.0
    for date, value in values.items():
        base = prev + flows.get(date, 0.0)
        if base > 1e-9:
            level *= 1 + (value - base) / base
        out[date] = level
        prev = value
    return out


def period_return(index: pd.Series, start: pd.Timestamp) -> float | None:
    window = index[index.index >= start]
    if len(window) < 2:
        return None
    return window.iloc[-1] / window.iloc[0] - 1


# ---------------------------------------------------------------- gráficos

def style_figure(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=MUTED, size=13),
        showlegend=False,
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        hoverlabel=dict(font_family=FONT),
    )
    return fig


def hbar_chart(
    labels: pd.Series, values: pd.Series, texts: list[str], colors
) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors, cornerradius=4),
            width=0.55,
            text=texts,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:,.2f}<extra></extra>",
        )
    )
    low = min(float(values.min()), 0.0)
    high = max(float(values.max()), 0.0)
    span = max(abs(low), abs(high), 1e-9)
    fig.update_xaxes(
        title=None,
        showticklabels=False,
        showgrid=False,
        zeroline=True,
        range=[low - span * 0.38, high + span * 0.38],
    )
    return style_figure(fig, height=max(220, 40 * len(labels) + 60))


def line_chart(series: pd.Series, unit: str, color: str = BLUE) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            line=dict(color=color, width=2),
            hovertemplate="%{x|%d %b %Y}: %{y:,.2f} " + unit + "<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(showgrid=False)
    return style_figure(fig, height=300)


def pnl_bars(series: pd.Series, unit: str) -> go.Figure:
    colors = [BLUE if value >= 0 else RED for value in series.values]
    fig = go.Figure(
        go.Bar(
            x=series.index,
            y=series.values,
            marker=dict(color=colors),
            hovertemplate="%{x|%d %b %Y}: %{y:+,.2f} " + unit + "<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat=",.0f", zeroline=True)
    fig.update_xaxes(showgrid=False)
    return style_figure(fig, height=300)


def grouped_weight_risk(
    labels: list[str], weights: list[float], risks: list[float]
) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        y=labels,
        x=weights,
        orientation="h",
        name="Peso",
        marker=dict(color=BLUE, cornerradius=4),
        hovertemplate="%{y} · peso: %{x:.1f}%<extra></extra>",
    )
    fig.add_bar(
        y=labels,
        x=risks,
        orientation="h",
        name="Contribución al riesgo",
        marker=dict(color=ORANGE, cornerradius=4),
        hovertemplate="%{y} · riesgo: %{x:.1f}%<extra></extra>",
    )
    style_figure(fig, height=max(240, 52 * len(labels) + 80))
    fig.update_layout(
        barmode="group",
        bargap=0.35,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(ticksuffix="%", showgrid=True)
    return fig


# ---------------------------------------------------------------- app

st.title("📊 Mi Portafolio")
st.caption(
    "Posiciones y P&G calculadas a partir de las operaciones (FIFO, comisiones "
    "incluidas en la base de coste). Precios de mercado vía Yahoo Finance."
)

with st.sidebar:
    st.header("Ajustes")
    currency = st.radio("Moneda principal", ["EUR", "USD"], horizontal=True)
    eurusd_live = fetch_eurusd() if HAS_YF else None
    eurusd = st.number_input(
        "EUR/USD",
        min_value=0.5,
        max_value=2.0,
        value=round(eurusd_live, 4) if eurusd_live else 1.15,
        step=0.0001,
        format="%.4f",
        help="Se obtiene de Yahoo Finance; puedes ajustarlo a mano.",
    )
    if not eurusd_live:
        st.caption("⚠️ Sin cotización EUR/USD en vivo; ajusta el tipo a mano.")
    benchmark_name = st.selectbox("Benchmark", list(BENCHMARKS))
    st.divider()
    st.header("Datos")
    source = st.radio(
        "Fuente de operaciones",
        ["CSV del repositorio", "Subir CSV"],
        help="El CSV del repositorio es data/trades.csv. Para actualizarlo de "
        "forma permanente, edítalo en GitHub y haz commit.",
    )
    uploaded = None
    if source == "Subir CSV":
        uploaded = st.file_uploader(
            "CSV con columnas: symbol, datetime, quantity, price, fee",
            type="csv",
        )
    if st.button("🔄 Actualizar precios"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Consulta: {dt.datetime.now():%Y-%m-%d %H:%M}")

SYM = "€" if currency == "EUR" else "$"


def to_main(value_usd: float) -> float:
    return value_usd / eurusd if currency == "EUR" else value_usd


def fmt(value_usd: float, signed: bool = False) -> str:
    template = "{:+,.2f} {}" if signed else "{:,.2f} {}"
    return template.format(to_main(value_usd), SYM)


# Cargar operaciones
try:
    if uploaded is not None:
        base_trades = parse_trades(pd.read_csv(uploaded))
    elif TRADES_CSV.exists():
        base_trades = parse_trades(pd.read_csv(TRADES_CSV))
    else:
        st.error("No se encontró data/trades.csv en el repositorio.")
        st.stop()
except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"No se pudo leer el CSV de operaciones: {exc}")
    st.stop()

# Aplicar los cambios hechos en el editor de la pestaña Operaciones (el
# widget guarda sus ediciones en session_state; el script entero se
# re-ejecuta con ellas ya disponibles).
EDITOR_KEY = f"trades_editor_{source}"


def apply_editor_edits(base: pd.DataFrame, state: dict) -> pd.DataFrame:
    df = base.copy()
    for row, changes in state.get("edited_rows", {}).items():
        for col, value in changes.items():
            df.iloc[int(row), df.columns.get_loc(col)] = value
    if state.get("added_rows"):
        df = pd.concat(
            [df, pd.DataFrame(state["added_rows"])], ignore_index=True
        )
    if state.get("deleted_rows"):
        df = df.drop(df.index[[int(i) for i in state["deleted_rows"]]])
    return df


trades = base_trades
editor_state = st.session_state.get(EDITOR_KEY)
if editor_state:
    try:
        trades = parse_trades(apply_editor_edits(base_trades, editor_state))
    except (ValueError, TypeError, IndexError, KeyError):
        trades = base_trades

summary, fifo_warnings = fifo_summary(trades)
for message in fifo_warnings:
    st.warning(message)

open_positions = summary[summary["quantity"] > 1e-9].copy()
symbols = tuple(open_positions["symbol"])

with st.spinner("Obteniendo precios de mercado…"):
    prices = fetch_prices(symbols) if HAS_YF else {}

missing_prices = [sym for sym in symbols if sym not in prices]
if not HAS_YF:
    st.warning("yfinance no está instalado: las posiciones se valoran al coste.")
elif missing_prices:
    st.warning(
        "Sin precio de mercado para: "
        + ", ".join(missing_prices)
        + ". Esas posiciones se valoran al coste medio."
    )

open_positions["price"] = open_positions["symbol"].map(prices)
open_positions["live"] = open_positions["price"].notna()
open_positions["price"] = open_positions["price"].fillna(open_positions["avg_cost"])
open_positions["market_value"] = open_positions["quantity"] * open_positions["price"]
open_positions["unrealized"] = (
    open_positions["market_value"] - open_positions["cost_basis"]
)
open_positions["unrealized_pct"] = (
    open_positions["unrealized"] / open_positions["cost_basis"] * 100
)
total_value = open_positions["market_value"].sum()
open_positions["weight"] = (
    open_positions["market_value"] / total_value * 100 if total_value else 0.0
)

summary = summary.merge(
    open_positions[["symbol", "unrealized"]], on="symbol", how="left"
)

total_cost = open_positions["cost_basis"].sum()
total_unrealized = open_positions["unrealized"].sum()
total_realized = summary["realized"].sum()
total_fees = summary["fees"].sum()
total_pnl = total_unrealized + total_realized

# Fórex y efectivo estimado
forex = load_forex()
eur_contributed = fx_fees = avg_rate = None
cash_usd = 0.0
if forex is not None and not forex.empty:
    eur_converted = -forex["eur_quantity"].sum()
    usd_received = forex["usd_amount"].sum()
    fx_fees = forex["fee_eur"].abs().sum()
    eur_contributed = eur_converted + fx_fees
    avg_rate = usd_received / eur_converted if eur_converted else None
    trade_cashflow = (-(trades["quantity"] * trades["price"]) - trades["fee"]).sum()
    cash_usd = usd_received + trade_cashflow

# Histórico (posiciones + benchmark + EUR/USD) para rendimiento y riesgo
benchmark = BENCHMARKS[benchmark_name]
history = pd.DataFrame()
if HAS_YF and len(trades):
    all_symbols = tuple(sorted(set(trades["symbol"]))) + (benchmark, "EURUSD=X")
    history = fetch_history(
        all_symbols, trades["datetime"].min().strftime("%Y-%m-%d")
    )

values_main = flows_main = fx_hist = None
bench_hist = None
if not history.empty:
    position_columns = [c for c in history.columns if c in set(trades["symbol"])]
    if "EURUSD=X" in history.columns:
        fx_hist = history["EURUSD=X"].ffill().bfill()
    else:
        fx_hist = pd.Series(eurusd, index=history.index)
    if benchmark in history.columns:
        bench_hist = history[benchmark].ffill()
    values_usd = daily_position_value(trades, history[position_columns])
    flows_usd = daily_flows(trades, history.index)
    if currency == "EUR":
        values_main = values_usd / fx_hist
        flows_main = flows_usd / fx_hist
        if bench_hist is not None:
            bench_hist = bench_hist / fx_hist
    else:
        values_main = values_usd
        flows_main = flows_usd

tab_resumen, tab_rendimiento, tab_riesgo, tab_operaciones = st.tabs(
    ["📊 Resumen", "📈 Rendimiento", "⚠️ Riesgo", "📒 Operaciones"]
)

# ================================================================ RESUMEN
with tab_resumen:
    k1, k2, k3, k4, k5 = st.columns(5)
    if currency == "EUR" and eur_contributed:
        eur_value_now = (total_value + cash_usd) / eurusd
        eur_pnl = eur_value_now - eur_contributed
        k1.metric(
            "Valor actual",
            f"{eur_value_now:,.2f} €",
            help=f"Posiciones {total_value:,.2f} $ + efectivo estimado "
            f"{cash_usd:,.2f} $, al tipo {eurusd:.4f}.",
        )
        k2.metric(
            "EUR aportados",
            f"{eur_contributed:,.2f} €",
            help="EUR netos convertidos a USD, incluidas comisiones de cambio "
            f"({fx_fees:,.2f} €). Tipo medio de compra: {avg_rate:.4f}.",
        )
        k3.metric(
            "P&G total",
            f"{eur_pnl:+,.2f} €",
            delta=f"{eur_pnl / eur_contributed * 100:+.2f}%",
            help="Valor actual − EUR aportados. Incluye el efecto del tipo "
            "de cambio y todas las comisiones.",
        )
        k4.metric("P&G no realizada", fmt(total_unrealized, signed=True))
        k5.metric("P&G realizada", fmt(total_realized, signed=True))
    else:
        k1.metric("Valor de mercado", fmt(total_value))
        k2.metric("Coste posiciones abiertas", fmt(total_cost))
        k3.metric(
            "P&G no realizada",
            fmt(total_unrealized, signed=True),
            delta=f"{total_unrealized / total_cost * 100:+.2f}%" if total_cost else None,
        )
        k4.metric("P&G realizada", fmt(total_realized, signed=True))
        k5.metric(
            "P&G total",
            fmt(total_pnl, signed=True),
            help=f"No realizada + realizada. Comisiones: {fmt(total_fees)}.",
        )

    st.subheader("Posiciones abiertas")
    positions_view = open_positions.sort_values(
        "market_value", ascending=False
    ).assign(
        cost_main=lambda d: d["cost_basis"].map(to_main),
        value_main=lambda d: d["market_value"].map(to_main),
        unrealized_main=lambda d: d["unrealized"].map(to_main),
    )[
        [
            "symbol",
            "quantity",
            "avg_cost",
            "price",
            "cost_main",
            "value_main",
            "unrealized_main",
            "unrealized_pct",
            "weight",
        ]
    ]
    st.dataframe(
        positions_view,
        hide_index=True,
        use_container_width=True,
        column_config={
            "symbol": st.column_config.TextColumn("Símbolo"),
            "quantity": st.column_config.NumberColumn("Cantidad", format="%.2f"),
            "avg_cost": st.column_config.NumberColumn("Precio medio $", format="%.2f"),
            "price": st.column_config.NumberColumn("Precio actual $", format="%.2f"),
            "cost_main": st.column_config.NumberColumn(f"Coste {SYM}", format="%.2f"),
            "value_main": st.column_config.NumberColumn(f"Valor {SYM}", format="%.2f"),
            "unrealized_main": st.column_config.NumberColumn(
                f"P&G no real. {SYM}", format="%.2f"
            ),
            "unrealized_pct": st.column_config.NumberColumn("P&G %", format="%.2f"),
            "weight": st.column_config.NumberColumn("Peso %", format="%.1f"),
        },
    )
    if not open_positions.empty and not open_positions["live"].all():
        st.caption("⚠️ Las posiciones sin precio de mercado figuran valoradas al coste.")

    if not open_positions.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Distribución por valor")
            data = open_positions.sort_values("market_value")
            texts = [
                f"{to_main(v):,.0f} {SYM} · {v / total_value:.1%}" if total_value else ""
                for v in data["market_value"]
            ]
            st.plotly_chart(
                hbar_chart(
                    data["symbol"], data["market_value"].map(to_main), texts, BLUE
                ),
                use_container_width=True,
            )
        with c2:
            st.subheader("P&G por símbolo")
            st.caption("Realizada + no realizada. Azul = ganancia, rojo = pérdida.")
            data = summary.assign(
                total=summary["unrealized"].fillna(0) + summary["realized"]
            ).sort_values("total")
            st.plotly_chart(
                hbar_chart(
                    data["symbol"],
                    data["total"].map(to_main),
                    [fmt(v, signed=True) for v in data["total"]],
                    [BLUE if v >= 0 else RED for v in data["total"]],
                ),
                use_container_width=True,
            )

    closed = summary[summary["realized"].abs() > 1e-9]
    if not closed.empty:
        st.subheader("P&G realizada por símbolo")
        st.dataframe(
            closed.assign(
                realized_main=lambda d: d["realized"].map(to_main),
                fees_main=lambda d: d["fees"].map(to_main),
            )[["symbol", "realized_main", "fees_main"]].sort_values(
                "realized_main", ascending=False
            ),
            hide_index=True,
            column_config={
                "symbol": st.column_config.TextColumn("Símbolo"),
                "realized_main": st.column_config.NumberColumn(
                    f"P&G realizada {SYM}", format="%.2f"
                ),
                "fees_main": st.column_config.NumberColumn(
                    f"Comisiones {SYM}", format="%.2f"
                ),
            },
        )

# ============================================================ RENDIMIENTO
with tab_rendimiento:
    if values_main is None or len(values_main) < 2:
        st.info(
            "El análisis de rendimiento necesita el histórico de precios "
            "(Yahoo Finance). Vuelve a intentarlo con «Actualizar precios»."
        )
    else:
        daily_pnl = values_main.diff() - flows_main
        daily_pnl.iloc[0] = values_main.iloc[0] - flows_main.iloc[0]

        twr = twr_index(values_main, flows_main)
        last_day = daily_pnl.index[-1]

        r1, r2, r3 = st.columns(3)
        r1.metric(
            f"P&G del último día ({last_day:%d %b})",
            f"{daily_pnl.iloc[-1]:+,.2f} {SYM}",
        )
        best = daily_pnl.idxmax()
        worst = daily_pnl.idxmin()
        r2.metric(
            "Mejor día", f"{daily_pnl.max():+,.2f} {SYM}", help=f"{best:%d %b %Y}"
        )
        r3.metric(
            "Peor día", f"{daily_pnl.min():+,.2f} {SYM}", help=f"{worst:%d %b %Y}"
        )

        st.subheader("P&G por periodo")
        granularity = st.radio(
            "Agrupar por",
            ["Diario", "Semanal", "Mensual"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if granularity == "Semanal":
            pnl_series = daily_pnl.resample("W-FRI").sum()
        elif granularity == "Mensual":
            pnl_series = daily_pnl.resample("ME").sum()
        else:
            pnl_series = daily_pnl
        st.caption(
            f"Variación del valor en {SYM}, neta de compras/ventas — solo el "
            "efecto del mercado (y de la divisa, en EUR)."
        )
        st.plotly_chart(pnl_bars(pnl_series, SYM), use_container_width=True)

        st.subheader("Evolución del valor de las posiciones")
        st.plotly_chart(line_chart(values_main, SYM), use_container_width=True)

        st.subheader(f"Rentabilidad vs {benchmark_name}")
        st.caption(
            "Índice base 100 desde la primera operación. La rentabilidad del "
            "portafolio es TWR (ponderada por tiempo): ignora el momento de los "
            f"aportes, comparable con el benchmark. Benchmark en {currency}."
        )
        fig = go.Figure()
        fig.add_scatter(
            x=twr.index,
            y=twr.values,
            mode="lines",
            name="Portafolio",
            line=dict(color=BLUE, width=2),
            hovertemplate="%{x|%d %b %Y}: %{y:,.1f}<extra>Portafolio</extra>",
        )
        if bench_hist is not None and len(bench_hist.dropna()) > 1:
            bench_norm = bench_hist.dropna()
            bench_norm = bench_norm / bench_norm.iloc[0] * 100
            fig.add_scatter(
                x=bench_norm.index,
                y=bench_norm.values,
                mode="lines",
                name=benchmark_name,
                line=dict(color=ORANGE, width=2),
                hovertemplate="%{x|%d %b %Y}: %{y:,.1f}<extra>"
                + benchmark_name
                + "</extra>",
            )
        style_figure(fig, height=320)
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de rentabilidades por periodo
        today = twr.index[-1]
        periods = {
            "1 semana": today - pd.Timedelta(days=7),
            "1 mes": today - pd.DateOffset(months=1),
            "3 meses": today - pd.DateOffset(months=3),
            "YTD": pd.Timestamp(today.year, 1, 1),
            "Total": twr.index[0],
        }
        bench_norm_full = (
            bench_hist.dropna() if bench_hist is not None else pd.Series(dtype=float)
        )
        rows = []
        for label, start in periods.items():
            row = {"Periodo": label}
            value = period_return(twr, start)
            row["Portafolio"] = f"{value:+.2%}" if value is not None else "—"
            value = (
                period_return(bench_norm_full, start)
                if len(bench_norm_full)
                else None
            )
            row[benchmark_name] = f"{value:+.2%}" if value is not None else "—"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# ================================================================= RIESGO
with tab_riesgo:
    if open_positions.empty:
        st.info("No hay posiciones abiertas.")
    else:
        sectors = load_sectors()
        open_positions["sector"] = [
            sectors.get(sym) or lookup_sector(sym) or "Otros"
            for sym in open_positions["symbol"]
        ]
        unknown = open_positions.loc[
            open_positions["sector"] == "Otros", "symbol"
        ].tolist()
        if unknown:
            st.caption(
                "Sin sector asignado (añádelo en data/sectors.csv): "
                + ", ".join(unknown)
            )

        # Métricas de riesgo sobre el histórico (retornos diarios en la
        # moneda principal, últimos ~90 días de mercado)
        risk_share = None
        vol_annual = beta = max_dd = None
        drawdown = None
        if values_main is not None and len(values_main) > 20 and not history.empty:
            position_columns = [
                c for c in history.columns if c in set(open_positions["symbol"])
            ]
            prices_main = history[position_columns].ffill()
            if currency == "EUR" and fx_hist is not None:
                prices_main = prices_main.div(fx_hist, axis=0)
            returns = prices_main.pct_change().dropna(how="all").tail(90)
            weights = (
                open_positions.set_index("symbol")["market_value"]
                .reindex(position_columns)
                .fillna(0.0)
            )
            weights = weights / weights.sum() if weights.sum() else weights
            if len(returns) >= 20:
                cov = returns.cov() * 252
                w = weights.values
                port_var = float(w @ cov.values @ w)
                if port_var > 0:
                    vol_annual = float(np.sqrt(port_var))
                    contrib = w * (cov.values @ w) / port_var
                    risk_share = pd.Series(
                        contrib * 100, index=position_columns
                    )

            twr = twr_index(values_main, flows_main)
            twr_returns = twr.pct_change().dropna()
            drawdown = twr / twr.cummax() - 1
            max_dd = float(drawdown.min())
            if bench_hist is not None:
                bench_returns = bench_hist.dropna().pct_change().dropna()
                joined = pd.concat([twr_returns, bench_returns], axis=1).dropna()
                if len(joined) > 20 and joined.iloc[:, 1].var() > 0:
                    beta = float(
                        joined.iloc[:, 0].cov(joined.iloc[:, 1])
                        / joined.iloc[:, 1].var()
                    )

        hhi = float(((open_positions["weight"] / 100) ** 2).sum())
        top_weight = float(open_positions["weight"].max())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Volatilidad anualizada",
            f"{vol_annual:.1%}" if vol_annual else "—",
            help="Sobre los retornos diarios de los últimos ~90 días de mercado, "
            f"en {currency}.",
        )
        m2.metric(
            f"Beta vs {benchmark.upper()}",
            f"{beta:.2f}" if beta is not None else "—",
            help="Sensibilidad del portafolio a los movimientos del benchmark.",
        )
        m3.metric(
            "Drawdown máximo",
            f"{max_dd:.1%}" if max_dd is not None else "—",
            help="Mayor caída desde un máximo del índice TWR.",
        )
        m4.metric(
            "Concentración (HHI)",
            f"{hhi:.2f}",
            help="Índice Herfindahl de los pesos (0 = muy diversificado, "
            f"1 = una sola posición). Mayor posición: {top_weight:.1f}%.",
        )

        st.subheader("Peso vs contribución al riesgo por posición")
        st.caption(
            "Una posición cuya barra naranja supera a la azul aporta más riesgo "
            "que peso: concentra la volatilidad de la cartera."
        )
        if risk_share is not None:
            frame = pd.DataFrame(
                {
                    "weight": weights * 100,
                    "risk": risk_share.reindex(weights.index).fillna(0.0),
                }
            ).sort_values("weight")
            st.plotly_chart(
                grouped_weight_risk(
                    list(frame.index),
                    list(frame["weight"]),
                    list(frame["risk"]),
                ),
                use_container_width=True,
            )

            st.subheader("Peso vs contribución al riesgo por sector")
            sector_map = open_positions.set_index("symbol")["sector"]
            by_sector = frame.assign(sector=sector_map.reindex(frame.index))
            sector_frame = (
                by_sector.groupby("sector")[["weight", "risk"]]
                .sum()
                .sort_values("weight")
            )
            st.plotly_chart(
                grouped_weight_risk(
                    list(sector_frame.index),
                    list(sector_frame["weight"]),
                    list(sector_frame["risk"]),
                ),
                use_container_width=True,
            )
        else:
            st.info(
                "La atribución de riesgo necesita el histórico de precios "
                "(Yahoo Finance)."
            )
            st.subheader("Distribución por sector")
            sector_weights = (
                open_positions.groupby("sector")["market_value"]
                .sum()
                .sort_values()
            )
            texts = [
                f"{v / total_value:.1%}" if total_value else ""
                for v in sector_weights
            ]
            st.plotly_chart(
                hbar_chart(
                    pd.Series(sector_weights.index),
                    sector_weights.map(to_main),
                    texts,
                    BLUE,
                ),
                use_container_width=True,
            )

        if drawdown is not None:
            st.subheader("Drawdown del portafolio")
            st.plotly_chart(
                line_chart(drawdown * 100, "%", color=RED),
                use_container_width=True,
            )

# ============================================================ OPERACIONES
with tab_operaciones:
    st.subheader("Operaciones")
    st.caption(
        "Los cambios aquí recalculan todo al instante pero no se guardan. "
        "Para que sean permanentes, edita `data/trades.csv` en GitHub."
    )
    st.data_editor(
        base_trades,
        num_rows="dynamic",
        use_container_width=True,
        key=EDITOR_KEY,
        column_config={
            "symbol": st.column_config.TextColumn("Símbolo", required=True),
            "datetime": st.column_config.DatetimeColumn("Fecha/Hora", required=True),
            "quantity": st.column_config.NumberColumn(
                "Cantidad", help="Positiva = compra, negativa = venta"
            ),
            "price": st.column_config.NumberColumn("Precio (USD)", format="%.4f"),
            "fee": st.column_config.NumberColumn("Comisión (USD)", format="%.2f"),
        },
    )

    if forex is not None and not forex.empty:
        st.subheader("Conversiones de divisa (EUR→USD)")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("EUR convertidos (neto)", f"{eur_converted:,.2f} €")
        f2.metric("USD obtenidos", f"{usd_received:,.2f} $")
        f3.metric("Tipo medio de compra", f"{avg_rate:.4f}" if avg_rate else "—")
        f4.metric(
            "Comisiones de cambio",
            f"{fx_fees:,.2f} €",
            help=f"Efectivo USD estimado tras compras/ventas: {cash_usd:,.2f} $.",
        )
        with st.expander("Detalle de conversiones"):
            st.dataframe(forex, hide_index=True, use_container_width=True)
    else:
        st.caption(
            "Añade data/forex.csv con las conversiones EUR→USD para ver los "
            "aportes y la P&G real en euros."
        )

st.divider()
st.caption(
    "Los precios pueden llevar ~15 min de retraso. Este panel es informativo, "
    "no asesoramiento financiero."
)
