from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import pandas as pd
import requests
import streamlit as st

COLUMNS: dict[str, list[str]] = {
    "teaching_sessions": [
        "id",
        "session_date",
        "day_name",
        "student_name",
        "subject",
        "start_time",
        "end_time",
        "break_minutes",
        "duration_hours",
        "hourly_rate",
        "earning",
        "note",
        "created_at",
    ],
    "shopping_runs": ["run_id", "shop_date", "title", "note", "created_at"],
    "shopping_items": [
        "item_id",
        "run_id",
        "item_name",
        "category",
        "qty",
        "unit",
        "unit_price",
        "picked",
        "created_at",
    ],
}

NUMERIC_COLUMNS = {
    "teaching_sessions": ["break_minutes", "duration_hours", "hourly_rate", "earning"],
    "shopping_runs": [],
    "shopping_items": ["qty", "unit_price"],
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y", "ใช่", "checked"}


def _get_secret_value(*keys: str) -> str | None:
    for key in keys:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    if "apps_script" in st.secrets:
        section = st.secrets["apps_script"]
        for key in keys:
            if key in section:
                return str(section[key]).strip()
    return None


def _show_setup_error() -> None:
    st.error("ยังไม่ได้ตั้งค่า Google Apps Script backend ค่ะ")
    st.markdown(
        """
        เวอร์ชันนี้ไม่ต้องใช้ Google Cloud / JSON key แล้ว ให้สร้าง Apps Script Web App แล้วใส่ URL กับ token ใน `.streamlit/secrets.toml`
        """
    )
    st.code(
        '''[apps_script]
web_app_url = "https://script.google.com/macros/s/XXXXXXXX/exec"
api_token = "ตั้งรหัสลับอะไรก็ได้ให้ตรงกับใน Apps Script"''',
        language="toml",
    )
    st.stop()


@st.cache_resource(show_spinner=False)
def _api_config() -> tuple[str, str]:
    url = _get_secret_value("web_app_url", "APPS_SCRIPT_URL", "apps_script_url")
    token = _get_secret_value("api_token", "APPS_SCRIPT_TOKEN", "token")
    if not url or not token:
        _show_setup_error()
    return url, token


def _api(action: str, **payload: Any) -> Any:
    url, token = _api_config()
    body = {"token": token, "action": action, **payload}
    try:
        res = requests.post(url, json=body, timeout=30)
        res.raise_for_status()
        data = res.json()
    except requests.exceptions.JSONDecodeError as exc:
        st.error("Apps Script ไม่ได้ส่ง JSON กลับมา อาจยังไม่ได้ Deploy เป็น Web app หรือ URL ไม่ใช่ /exec")
        st.exception(exc)
        st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error("เชื่อม Google Apps Script ไม่สำเร็จ")
        st.exception(exc)
        st.stop()

    if not data.get("ok"):
        st.error("Apps Script แจ้ง error")
        st.code(str(data.get("error", data)), language="text")
        st.stop()
    return data.get("data")


def init_db() -> None:
    _api("ensure_tables", columns=COLUMNS)


def _read_table(table: str) -> pd.DataFrame:
    records = _api("read_table", table=table, columns=COLUMNS[table]) or []
    df = pd.DataFrame(records)

    for col in COLUMNS[table]:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS[table]]

    for col in NUMERIC_COLUMNS[table]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if table == "shopping_items":
        df["picked"] = df["picked"].apply(_as_bool)

    return df


def _append_row(table: str, row: dict[str, Any]) -> None:
    _api("append_row", table=table, columns=COLUMNS[table], row=row)


def _delete_by_key(table: str, key_col: str, key_value: Any) -> None:
    _api("delete_by_key", table=table, columns=COLUMNS[table], key_col=key_col, key_value=str(key_value))


def _update_by_key(table: str, key_col: str, key_value: Any, values: dict[str, Any]) -> None:
    _api(
        "update_by_key",
        table=table,
        columns=COLUMNS[table],
        key_col=key_col,
        key_value=str(key_value),
        values=values,
    )


def _with_line_total(items: pd.DataFrame) -> pd.DataFrame:
    if items.empty:
        items["line_total"] = []
        return items
    items = items.copy()
    items["qty"] = pd.to_numeric(items["qty"], errors="coerce").fillna(0)
    items["unit_price"] = pd.to_numeric(items["unit_price"], errors="coerce").fillna(0)
    items["line_total"] = items["qty"] * items["unit_price"]
    return items


def query_df(sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
    """Compatibility layer for the original app queries, now backed by Apps Script + Google Sheets."""
    params = list(params or [])
    normalized = " ".join(sql.lower().split())

    if "from teaching_sessions" in normalized:
        df = _read_table("teaching_sessions")
        if df.empty:
            return df
        return df.sort_values(["session_date", "start_time"], ascending=[False, False], kind="stable").reset_index(drop=True)

    if "from shopping_runs" in normalized and "left join shopping_items" in normalized:
        runs = _read_table("shopping_runs")
        items = _with_line_total(_read_table("shopping_items"))

        base_cols = ["run_id", "shop_date", "title", "note", "item_count", "total_amount", "picked_count", "created_at"]
        if runs.empty:
            return pd.DataFrame(columns=base_cols)

        if items.empty:
            summary = pd.DataFrame(columns=["run_id", "item_count", "total_amount", "picked_count"])
        else:
            summary = (
                items.groupby("run_id", as_index=False)
                .agg(
                    item_count=("item_id", "count"),
                    total_amount=("line_total", "sum"),
                    picked_count=("picked", "sum"),
                )
            )

        df = runs.merge(summary, on="run_id", how="left")
        df["item_count"] = pd.to_numeric(df["item_count"], errors="coerce").fillna(0).astype(int)
        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0.0)
        df["picked_count"] = pd.to_numeric(df["picked_count"], errors="coerce").fillna(0).astype(int)
        return df[base_cols].sort_values(["shop_date", "created_at"], ascending=[False, False], kind="stable").reset_index(drop=True)

    if "from shopping_items" in normalized:
        items = _with_line_total(_read_table("shopping_items"))

        if "where run_id = ?" in normalized:
            run_id = params[0] if params else ""
            df = items[items["run_id"].astype(str) == str(run_id)].copy()
            cols = ["item_id", "run_id", "item_name", "category", "qty", "unit", "unit_price", "picked", "line_total", "created_at"]
            if df.empty:
                return pd.DataFrame(columns=cols)
            return df[cols].sort_values("created_at", ascending=True, kind="stable").reset_index(drop=True)

        if "join shopping_runs" in normalized:
            runs = _read_table("shopping_runs")
            if items.empty:
                return pd.DataFrame(
                    columns=["item_id", "run_id", "shop_date", "title", "item_name", "category", "qty", "unit", "unit_price", "picked", "line_total"]
                )
            df = items.merge(runs[["run_id", "shop_date", "title"]], on="run_id", how="left")
            cols = ["item_id", "run_id", "shop_date", "title", "item_name", "category", "qty", "unit", "unit_price", "picked", "line_total"]
            return (
                df.sort_values(["shop_date", "created_at"], ascending=[False, True], kind="stable")[cols]
                .reset_index(drop=True)
            )

    raise NotImplementedError(f"This query is not supported by the Apps Script backend:\n{sql}")


def execute(sql: str, params: Iterable[Any] | None = None) -> None:
    """Compatibility layer for the original app write operations, now backed by Apps Script + Google Sheets."""
    params = list(params or [])
    normalized = " ".join(sql.lower().split())

    if normalized.startswith("insert into teaching_sessions"):
        keys = [
            "id",
            "session_date",
            "day_name",
            "student_name",
            "subject",
            "start_time",
            "end_time",
            "break_minutes",
            "duration_hours",
            "hourly_rate",
            "earning",
            "note",
        ]
        row = dict(zip(keys, params, strict=False))
        row["created_at"] = _now()
        _append_row("teaching_sessions", row)
        return

    if normalized.startswith("insert into shopping_runs"):
        keys = ["run_id", "shop_date", "title", "note"]
        row = dict(zip(keys, params, strict=False))
        row["created_at"] = _now()
        _append_row("shopping_runs", row)
        return

    if normalized.startswith("insert into shopping_items"):
        keys = ["item_id", "run_id", "item_name", "category", "qty", "unit", "unit_price", "picked"]
        row = dict(zip(keys, params, strict=False))
        if "picked" not in row or row["picked"] == "":
            row["picked"] = False
        row["created_at"] = _now()
        _append_row("shopping_items", row)
        return

    if normalized.startswith("update shopping_items"):
        picked, item_name, category, qty, unit, unit_price, item_id = params
        _update_by_key(
            "shopping_items",
            "item_id",
            str(item_id),
            {
                "picked": bool(picked),
                "item_name": str(item_name),
                "category": str(category),
                "qty": float(qty),
                "unit": str(unit),
                "unit_price": float(unit_price),
            },
        )
        return

    if normalized.startswith("delete from teaching_sessions where id"):
        _delete_by_key("teaching_sessions", "id", params[0])
        return

    if normalized.startswith("delete from shopping_items where item_id"):
        _delete_by_key("shopping_items", "item_id", params[0])
        return

    if normalized.startswith("delete from shopping_items where run_id"):
        _delete_by_key("shopping_items", "run_id", params[0])
        return

    if normalized.startswith("delete from shopping_runs where run_id"):
        _delete_by_key("shopping_runs", "run_id", params[0])
        return

    raise NotImplementedError(f"This write operation is not supported by the Apps Script backend:\n{sql}")
