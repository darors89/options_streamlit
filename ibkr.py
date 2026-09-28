"""Descarga del portafolio desde Interactive Brokers (Flex Web Service).

El Flex Web Service permite bajar un informe definido en Account Management
con un token de solo lectura, sin gateway ni login interactivo — por eso es
la única vía de IBKR que funciona en Streamlit Community Cloud.

Son dos llamadas HTTPS:

  1. SendRequest   → devuelve un código de referencia
  2. GetStatement  → devuelve el informe en XML

El XML se traduce a los mismos DataFrames que la app ya usa con los CSV:
operaciones, dividendos, aportes y conversiones de divisa.

Los nombres de los campos dependen de qué columnas marques al definir la
Flex Query. El parser es tolerante: si un atributo no está, usa un valor por
defecto en lugar de fallar, y `missing_fields()` informa de lo que no
encontró para que ajustes la consulta en IBKR.
"""

from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

# La base se puede sobreescribir con IBKR_FLEX_BASE para apuntar a un
# servidor de pruebas; en producción se deja sin definir.
FLEX_BASE = os.environ.get(
    "IBKR_FLEX_BASE",
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService",
)
SEND_REQUEST_URL = f"{FLEX_BASE}/SendRequest"
GET_STATEMENT_URL = f"{FLEX_BASE}/GetStatement"

# IBKR devuelve este código mientras el informe se está generando.
ERROR_GENERATION_IN_PROGRESS = "1019"

USER_AGENT = "portfolio-streamlit/1.0"


class FlexError(RuntimeError):
    """Error devuelto por el Flex Web Service o al interpretar su respuesta."""


def _get(url: str, params: dict[str, str], timeout: int) -> str:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _check_error(root: ET.Element) -> None:
    """Lanza FlexError si la respuesta trae un estado de fallo."""
    status = root.findtext("Status") or root.findtext(".//Status")
    if status and status.strip().lower() == "fail":
        code = (root.findtext("ErrorCode") or root.findtext(".//ErrorCode") or "").strip()
        message = (
            root.findtext("ErrorMessage") or root.findtext(".//ErrorMessage") or ""
        ).strip()
        raise FlexError(f"IBKR {code}: {message}" if code else f"IBKR: {message}")


def request_statement(token: str, query_id: str, timeout: int = 30) -> tuple[str, str]:
    """Pide el informe. Devuelve (código de referencia, URL de descarga)."""
    xml = _get(SEND_REQUEST_URL, {"t": token, "q": query_id, "v": "3"}, timeout)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise FlexError(f"Respuesta ilegible de SendRequest: {exc}") from exc
    _check_error(root)
    reference = (root.findtext("ReferenceCode") or "").strip()
    if not reference:
        raise FlexError("SendRequest no devolvió código de referencia.")
    return reference, (root.findtext("Url") or GET_STATEMENT_URL).strip()


def download_statement(
    token: str,
    reference: str,
    url: str = GET_STATEMENT_URL,
    timeout: int = 60,
    attempts: int = 6,
    wait: float = 5.0,
) -> str:
    """Descarga el informe, reintentando mientras IBKR lo esté generando."""
    last_error: FlexError | None = None
    for attempt in range(attempts):
        xml = _get(url, {"t": token, "q": reference, "v": "3"}, timeout)
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise FlexError(f"Respuesta ilegible de GetStatement: {exc}") from exc
        if root.tag == "FlexQueryResponse":
            return xml
        try:
            _check_error(root)
        except FlexError as exc:
            if ERROR_GENERATION_IN_PROGRESS not in str(exc):
                raise
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(wait)
            continue
        return xml
    raise FlexError(
        "IBKR sigue generando el informe tras varios intentos. "
        f"Último aviso: {last_error}"
    )


def fetch_flex_xml(token: str, query_id: str) -> str:
    """Pide y descarga el informe en una sola llamada."""
    reference, url = request_statement(token, query_id)
    return download_statement(token, reference, url)


# ------------------------------------------------------------------ parseo

def _num(element: ET.Element, *names: str, default: float = 0.0) -> float:
    for name in names:
        value = element.get(name)
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:
                continue
    return default


def _text(element: ET.Element, *names: str, default: str = "") -> str:
    for name in names:
        value = element.get(name)
        if value not in (None, ""):
            return value
    return default


def _timestamp(raw: str) -> pd.Timestamp | None:
    """IBKR fecha como '20260730;093002', '20260730;09:30:02' o '20260730'."""
    if not raw:
        return None
    cleaned = raw.replace(";", " ").replace("-", "").replace(":", "").strip()
    for fmt in ("%Y%m%d %H%M%S", "%Y%m%d %H%M", "%Y%m%d"):
        try:
            return pd.to_datetime(cleaned, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.to_datetime(raw, errors="coerce")


def parse_flex_xml(xml_text: str) -> dict[str, pd.DataFrame]:
    """Traduce el XML de una Flex Query a los DataFrames que usa la app.

    Devuelve un dict con las claves `trades`, `dividends`, `deposits` y
    `forex`, con las mismas columnas que los CSV de data/.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FlexError(f"XML ilegible: {exc}") from exc
    _check_error(root)

    trades: list[dict] = []
    forex: list[dict] = []
    for trade in root.iter("Trade"):
        category = _text(trade, "assetCategory").upper()
        when = _timestamp(_text(trade, "dateTime", "tradeDate"))
        if when is None:
            continue
        quantity = _num(trade, "quantity")
        price = _num(trade, "tradePrice", "price")
        commission = abs(_num(trade, "ibCommission", "commission"))
        symbol = _text(trade, "symbol")
        if category == "CASH":
            # Conversiones de divisa: el símbolo es del tipo EUR.USD y la
            # cantidad va en la divisa base (negativa = EUR vendidos).
            forex.append(
                {
                    "datetime": when,
                    "eur_quantity": quantity,
                    "rate": price,
                    "usd_amount": _num(trade, "proceeds", "tradeMoney"),
                    "fee_eur": commission,
                }
            )
        elif symbol:
            trades.append(
                {
                    "symbol": symbol,
                    "datetime": when,
                    "quantity": quantity,
                    "price": price,
                    "fee": commission,
                }
            )

    dividends: list[dict] = []
    taxes: list[dict] = []
    deposits: list[dict] = []
    for cash in root.iter("CashTransaction"):
        kind = _text(cash, "type").strip().lower()
        when = _timestamp(_text(cash, "dateTime", "settleDate", "reportDate"))
        if when is None:
            continue
        amount = _num(cash, "amount")
        description = _text(cash, "description")
        symbol = _text(cash, "symbol")
        if kind.startswith("dividend") or "lieu of dividend" in kind:
            dividends.append(
                {
                    "date": when.normalize(),
                    "symbol": symbol,
                    "amount_usd": amount,
                    "description": description,
                }
            )
        elif "withholding" in kind:
            taxes.append(
                {"date": when.normalize(), "symbol": symbol, "tax_usd": abs(amount)}
            )
        elif "deposit" in kind or "withdrawal" in kind:
            deposits.append(
                {
                    "date": when.normalize(),
                    "amount_eur": amount,
                    "description": description or "Transferencia",
                }
            )

    dividends_df = pd.DataFrame(
        dividends, columns=["date", "symbol", "amount_usd", "description"]
    )
    taxes_df = pd.DataFrame(taxes, columns=["date", "symbol", "tax_usd"])
    if not dividends_df.empty:
        # La retención llega como apunte aparte; se agrega por símbolo y fecha.
        if not taxes_df.empty:
            taxes_df = taxes_df.groupby(["date", "symbol"], as_index=False)[
                "tax_usd"
            ].sum()
            dividends_df = dividends_df.merge(
                taxes_df, on=["date", "symbol"], how="left"
            )
        else:
            dividends_df["tax_usd"] = 0.0
        dividends_df["tax_usd"] = dividends_df["tax_usd"].fillna(0.0)
        dividends_df["net_usd"] = (
            dividends_df["amount_usd"] - dividends_df["tax_usd"]
        )
        dividends_df = dividends_df[
            ["date", "symbol", "amount_usd", "tax_usd", "net_usd", "description"]
        ].sort_values("date")
    else:
        dividends_df = pd.DataFrame(
            columns=["date", "symbol", "amount_usd", "tax_usd", "net_usd", "description"]
        )

    return {
        "trades": pd.DataFrame(
            trades, columns=["symbol", "datetime", "quantity", "price", "fee"]
        ).sort_values("datetime", ignore_index=True),
        "dividends": dividends_df.reset_index(drop=True),
        "deposits": pd.DataFrame(
            deposits, columns=["date", "amount_eur", "description"]
        ).sort_values("date", ignore_index=True),
        "forex": pd.DataFrame(
            forex, columns=["datetime", "eur_quantity", "rate", "usd_amount", "fee_eur"]
        ).sort_values("datetime", ignore_index=True),
    }


def statement_period(xml_text: str) -> str:
    """Periodo y fecha de generación del informe, para mostrarlos en la app."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    statement = root.find(".//FlexStatement")
    if statement is None:
        return ""
    desde = _text(statement, "fromDate")
    hasta = _text(statement, "toDate")
    generado = _text(statement, "whenGenerated")
    partes = []
    if desde and hasta:
        partes.append(f"{desde} → {hasta}")
    if generado:
        partes.append(f"generado {generado.replace(';', ' ')}")
    return " · ".join(partes)


def missing_sections(data: dict[str, pd.DataFrame]) -> list[str]:
    """Secciones vacías, para avisar de qué falta marcar en la Flex Query."""
    etiquetas = {
        "trades": "operaciones (Trades)",
        "dividends": "dividendos (Cash Transactions → Dividends)",
        "deposits": "transferencias (Cash Transactions → Deposits/Withdrawals)",
        "forex": "conversiones de divisa (Trades con assetCategory CASH)",
    }
    return [etiquetas[k] for k, frame in data.items() if frame.empty]
