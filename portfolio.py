"""Estado de situación del portafolio.

Lee las operaciones desde data/trades.csv (y las conversiones de divisa desde
data/forex.csv), calcula posiciones abiertas y P&G con criterio FIFO — con las
comisiones incluidas en la base de coste, igual que el extracto del bróker — y
valora las posiciones a precio de mercado vía yfinance.

Para actualizar los datos: editar data/trades.csv en GitHub (un commit
redespliega la app en Streamlit Community Cloud), o subir un CSV desde la
barra lateral para una consulta puntual.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import yfinance as yf

    HAS_YF = True
except ImportError:
    HAS_YF = False

# Paleta validada (par divergente): azul = positivo/magnitud, rojo = negativo.
BLUE = "#2a78d6"
RED = "#e34948"
GRID = "rgba(137, 135, 129, 0.25)"
MUTED = "#898781"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

BASE_DIR = Path(__file__).parent
TRADES_CSV = BASE_DIR / "data" / "trades.csv"
FOREX_CSV = BASE_DIR / "data" / "forex.csv"

TRADE_COLUMNS = {"symbol", "datetime", "quantity", "price", "fee"}

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


def fifo_summary(trades: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Por símbolo: cantidad abierta, coste FIFO (comisiones incluidas),
    P&G realizada y comisiones acumuladas."""
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
    closes = yf.download(
        list(symbols), start=start, progress=False, auto_adjust=True
    )["Close"]
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(symbols[0])
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    return closes


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


def allocation_chart(positions: pd.DataFrame) -> go.Figure:
    data = positions.sort_values("market_value")
    total = data["market_value"].sum()
    labels = [
        f"{value:,.0f} $ · {value / total:.1%}" if total else f"{value:,.0f} $"
        for value in data["market_value"]
    ]
    fig = go.Figure(
        go.Bar(
            x=data["market_value"],
            y=data["symbol"],
            orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            width=0.55,
            text=labels,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:,.2f} $<extra></extra>",
        )
    )
    max_value = data["market_value"].max()
    fig.update_xaxes(
        title=None,
        showticklabels=False,
        showgrid=False,
        range=[0, max_value * 1.35 if max_value else 1],
    )
    return style_figure(fig)


def pnl_chart(summary: pd.DataFrame) -> go.Figure:
    data = summary.assign(total=summary["unrealized"].fillna(0) + summary["realized"])
    data = data.sort_values("total")
    colors = [BLUE if value >= 0 else RED for value in data["total"]]
    fig = go.Figure(
        go.Bar(
            x=data["total"],
            y=data["symbol"],
            orientation="h",
            marker=dict(color=colors, cornerradius=4),
            width=0.55,
            text=[f"{value:+,.2f} $" for value in data["total"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:+,.2f} $<extra></extra>",
        )
    )
    span = max(abs(data["total"].min()), abs(data["total"].max()), 1.0)
    low = min(data["total"].min(), 0.0)
    high = max(data["total"].max(), 0.0)
    fig.update_xaxes(
        title=None,
        showticklabels=False,
        showgrid=False,
        zeroline=True,
        range=[low - span * 0.35, high + span * 0.35],
    )
    return style_figure(fig)


def evolution_chart(series: pd.Series) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            line=dict(color=BLUE, width=2),
            hovertemplate="%{x|%d %b %Y}: %{y:,.2f} $<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(showgrid=False)
    return style_figure(fig, height=300)


# ---------------------------------------------------------------- app

st.title("📊 Mi Portafolio")
st.caption(
    "Posiciones y P&G calculadas a partir de las operaciones (FIFO, comisiones "
    "incluidas en la base de coste). Precios de mercado vía Yahoo Finance."
)

with st.sidebar:
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

with st.expander("✏️ Operaciones — editar para simular (solo esta sesión)"):
    st.caption(
        "Los cambios aquí recalculan todo al instante pero no se guardan. "
        "Para que sean permanentes, edita `data/trades.csv` en GitHub."
    )
    edited = st.data_editor(
        base_trades,
        num_rows="dynamic",
        use_container_width=True,
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

try:
    trades = parse_trades(edited)
except (ValueError, TypeError) as exc:
    st.warning(f"Revisa las operaciones editadas: {exc}. Se usa el CSV original.")
    trades = base_trades

summary, fifo_warnings = fifo_summary(trades)
for message in fifo_warnings:
    st.warning(message)

open_positions = summary[summary["quantity"] > 1e-9].copy()

# Precios
symbols = tuple(open_positions["symbol"])
with st.spinner("Obteniendo precios de mercado…"):
    prices = fetch_prices(symbols) if HAS_YF else {}
    eurusd_live = fetch_eurusd() if HAS_YF else None

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

# ------------------------------------------------ indicadores principales
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Valor de mercado", f"{total_value:,.2f} $")
k2.metric("Coste posiciones abiertas", f"{total_cost:,.2f} $")
k3.metric(
    "P&G no realizada",
    f"{total_unrealized:+,.2f} $",
    delta=f"{total_unrealized / total_cost * 100:+.2f}%" if total_cost else None,
)
k4.metric("P&G realizada", f"{total_realized:+,.2f} $")
k5.metric(
    "P&G total",
    f"{total_pnl:+,.2f} $",
    help=f"No realizada + realizada. Comisiones acumuladas: {total_fees:,.2f} $ "
    "(ya descontadas en ambas).",
)

# ------------------------------------------------ posiciones abiertas
st.subheader("Posiciones abiertas")
positions_view = open_positions.sort_values("market_value", ascending=False)[
    [
        "symbol",
        "quantity",
        "avg_cost",
        "cost_basis",
        "price",
        "market_value",
        "unrealized",
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
        "cost_basis": st.column_config.NumberColumn("Coste $", format="%.2f"),
        "price": st.column_config.NumberColumn("Precio actual $", format="%.2f"),
        "market_value": st.column_config.NumberColumn("Valor $", format="%.2f"),
        "unrealized": st.column_config.NumberColumn("P&G no real. $", format="%.2f"),
        "unrealized_pct": st.column_config.NumberColumn("P&G %", format="%.2f"),
        "weight": st.column_config.NumberColumn("Peso %", format="%.1f"),
    },
)
if not open_positions.empty and not open_positions["live"].all():
    st.caption("⚠️ Las posiciones sin precio de mercado figuran valoradas al coste.")

# ------------------------------------------------ gráficos
if not open_positions.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribución por valor")
        st.plotly_chart(
            allocation_chart(open_positions), use_container_width=True
        )
    with c2:
        st.subheader("P&G por símbolo")
        st.caption("Realizada + no realizada. Azul = ganancia, rojo = pérdida.")
        st.plotly_chart(pnl_chart(summary), use_container_width=True)

    if HAS_YF and prices:
        try:
            history = fetch_history(
                symbols, trades["datetime"].min().strftime("%Y-%m-%d")
            )
            if not history.empty:
                st.subheader("Evolución del valor de las posiciones (USD)")
                st.plotly_chart(
                    evolution_chart(daily_position_value(trades, history)),
                    use_container_width=True,
                )
        except Exception:
            st.caption("No se pudo cargar el histórico de precios.")

# ------------------------------------------------ P&G realizada
closed = summary[summary["realized"].abs() > 1e-9]
if not closed.empty:
    st.subheader("P&G realizada por símbolo")
    st.dataframe(
        closed[["symbol", "realized", "fees"]].sort_values(
            "realized", ascending=False
        ),
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Símbolo"),
            "realized": st.column_config.NumberColumn("P&G realizada $", format="%.2f"),
            "fees": st.column_config.NumberColumn("Comisiones $", format="%.2f"),
        },
    )

# ------------------------------------------------ divisa / visión en EUR
forex = load_forex()
st.subheader("Divisa y visión en EUR")
fx_col1, fx_col2 = st.columns([1, 3])
with fx_col1:
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
        st.caption("⚠️ Sin cotización en vivo; ajusta el tipo manualmente.")

with fx_col2:
    if forex is not None and not forex.empty:
        eur_converted = -forex["eur_quantity"].sum()
        usd_received = forex["usd_amount"].sum()
        fx_fees = forex["fee_eur"].abs().sum()
        eur_contributed = eur_converted + fx_fees
        avg_rate = usd_received / eur_converted if eur_converted else float("nan")
        # Efectivo USD estimado: USD obtenidos en fórex + flujos de las operaciones.
        trade_cashflow = (-(trades["quantity"] * trades["price"]) - trades["fee"]).sum()
        cash_usd = usd_received + trade_cashflow
        eur_value_now = (total_value + cash_usd) / eurusd if eurusd else float("nan")
        eur_pnl = eur_value_now - eur_contributed

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "EUR aportados",
            f"{eur_contributed:,.2f} €",
            help="EUR netos convertidos a USD, incluidas comisiones de cambio "
            f"({fx_fees:,.2f} €).",
        )
        m2.metric("Tipo medio de compra", f"{avg_rate:.4f}")
        m3.metric(
            "Valor actual en EUR",
            f"{eur_value_now:,.2f} €",
            help=f"(Posiciones {total_value:,.2f} $ + efectivo estimado "
            f"{cash_usd:,.2f} $) al tipo actual.",
        )
        m4.metric(
            "P&G total en EUR",
            f"{eur_pnl:+,.2f} €",
            delta=f"{eur_pnl / eur_contributed * 100:+.2f}%" if eur_contributed else None,
            help="Incluye el efecto del tipo de cambio.",
        )
    else:
        st.metric(
            "Valor de mercado en EUR",
            f"{total_value / eurusd:,.2f} €" if eurusd else "—",
        )
        st.caption(
            "Añade data/forex.csv con las conversiones EUR→USD para ver los "
            "aportes y la P&G en euros."
        )

st.divider()
st.caption(
    "Los precios pueden llevar ~15 min de retraso. Este panel es informativo, "
    "no asesoramiento financiero."
)
