from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import execute, init_db, query_df

st.set_page_config(
    page_title="Tutor & Market Tracker",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

DAY_TH = {
    0: "จันทร์",
    1: "อังคาร",
    2: "พุธ",
    3: "พฤหัสบดี",
    4: "ศุกร์",
    5: "เสาร์",
    6: "อาทิตย์",
}
DAY_ORDER = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main-title {
            font-size: 2.4rem;
            font-weight: 900;
            letter-spacing: -0.04em;
            margin-bottom: 0.2rem;
        }
        .soft-card {
            border-radius: 24px;
            padding: 1.1rem 1.2rem;
            background: linear-gradient(135deg, rgba(255,119,198,0.16), rgba(120,115,245,0.12), rgba(0,212,255,0.10));
            border: 1px solid rgba(255,255,255,0.20);
            box-shadow: 0 14px 40px rgba(31,38,135,0.10);
        }
        .mini-muted { color: #777; font-size: 0.9rem; }
        .big-number { font-size: 2rem; font-weight: 850; }
        div[data-testid="stMetricValue"] { font-weight: 850; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(v: float) -> str:
    return f"฿{v:,.2f}"


def to_date_str(d: date) -> str:
    return d.isoformat()


def duration_hours(start: time, end: time, break_minutes: int = 0) -> float:
    base = datetime.combine(date.today(), start)
    finish = datetime.combine(date.today(), end)
    if finish <= base:
        finish += timedelta(days=1)
    hours = (finish - base).total_seconds() / 3600 - (break_minutes / 60)
    return max(round(hours, 2), 0)


def load_teaching() -> pd.DataFrame:
    df = query_df(
        """
        SELECT *
        FROM teaching_sessions
        ORDER BY session_date DESC, start_time DESC
        """
    )
    if not df.empty:
        df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
        df["month"] = pd.to_datetime(df["session_date"]).dt.to_period("M").astype(str)
        df["year"] = pd.to_datetime(df["session_date"]).dt.year
    return df


def load_runs() -> pd.DataFrame:
    df = query_df(
        """
        SELECT
            r.run_id,
            r.shop_date,
            r.title,
            r.note,
            COUNT(i.item_id) AS item_count,
            COALESCE(SUM(i.qty * i.unit_price), 0) AS total_amount,
            COALESCE(SUM(CASE WHEN i.picked THEN 1 ELSE 0 END), 0) AS picked_count,
            MAX(r.created_at) AS created_at
        FROM shopping_runs r
        LEFT JOIN shopping_items i ON r.run_id = i.run_id
        GROUP BY r.run_id, r.shop_date, r.title, r.note
        ORDER BY r.shop_date DESC, created_at DESC
        """
    )
    if not df.empty:
        df["shop_date"] = pd.to_datetime(df["shop_date"]).dt.date
        df["month"] = pd.to_datetime(df["shop_date"]).dt.to_period("M").astype(str)
        df["year"] = pd.to_datetime(df["shop_date"]).dt.year
    return df


def load_items(run_id: str | None = None) -> pd.DataFrame:
    if run_id:
        df = query_df(
            """
            SELECT item_id, run_id, item_name, category, qty, unit, unit_price, picked,
                   qty * unit_price AS line_total, created_at
            FROM shopping_items
            WHERE run_id = ?
            ORDER BY created_at ASC
            """,
            [run_id],
        )
    else:
        df = query_df(
            """
            SELECT i.item_id, i.run_id, r.shop_date, r.title, i.item_name, i.category,
                   i.qty, i.unit, i.unit_price, i.picked, i.qty * i.unit_price AS line_total
            FROM shopping_items i
            JOIN shopping_runs r ON i.run_id = r.run_id
            ORDER BY r.shop_date DESC, i.created_at ASC
            """
        )
    return df


def header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="main-title">{title}</div>', unsafe_allow_html=True)
    st.caption(subtitle)


def metric_card(label: str, value: str, helper: str = "") -> None:
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="mini-muted">{label}</div>
            <div class="big-number">{value}</div>
            <div class="mini-muted">{helper}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_dashboard() -> None:
    header("✨ Dashboard รวม", "สรุปชั่วโมงสอน รายรับจากสอน และค่าใช้จ่ายจ่ายตลาดแบบดูง่าย")
    teaching = load_teaching()
    runs = load_runs()
    items = load_items()

    min_d = date(date.today().year, 1, 1)
    max_d = date.today()
    col_a, col_b = st.columns([1, 1])
    with col_a:
        start_d = st.date_input("เริ่มวันที่", value=min_d, key="dash_start")
    with col_b:
        end_d = st.date_input("ถึงวันที่", value=max_d, key="dash_end")

    if not teaching.empty:
        teaching = teaching[(teaching["session_date"] >= start_d) & (teaching["session_date"] <= end_d)]
    if not runs.empty:
        runs = runs[(runs["shop_date"] >= start_d) & (runs["shop_date"] <= end_d)]
    if not items.empty and "shop_date" in items.columns:
        items["shop_date"] = pd.to_datetime(items["shop_date"]).dt.date
        items = items[(items["shop_date"] >= start_d) & (items["shop_date"] <= end_d)]

    total_hours = 0 if teaching.empty else teaching["duration_hours"].sum()
    total_sessions = 0 if teaching.empty else len(teaching)
    total_students = 0 if teaching.empty else teaching["student_name"].nunique()
    total_spend = 0 if runs.empty else runs["total_amount"].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("ชั่วโมงสอนรวม", f"{total_hours:,.1f} ชม.", f"จาก {total_sessions} ครั้ง")
    with c2:
        metric_card("จำนวนนักเรียน", f"{total_students:,} คน", "นับชื่อไม่ซ้ำ")
    with c3:
        earning = 0 if teaching.empty else teaching["earning"].sum()
        metric_card("รายรับประมาณ", money(earning), "จาก hourly rate ที่กรอก")
    with c4:
        metric_card("ค่าใช้จ่ายตลาด", money(total_spend), f"จาก {0 if runs.empty else len(runs)} ครั้ง")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("🌈 ชั่วโมงสอนแยกตามวัน")
        if teaching.empty:
            st.info("ยังไม่มีข้อมูลสอนในช่วงนี้")
        else:
            day_sum = teaching.groupby("day_name", as_index=False)["duration_hours"].sum()
            day_sum["day_name"] = pd.Categorical(day_sum["day_name"], DAY_ORDER, ordered=True)
            day_sum = day_sum.sort_values("day_name")
            fig = px.bar(
                day_sum,
                x="day_name",
                y="duration_hours",
                color="duration_hours",
                color_continuous_scale="Plasma",
                labels={"day_name": "วัน", "duration_hours": "ชั่วโมงรวม"},
                text="duration_hours",
            )
            fig.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("💸 ค่าใช้จ่ายแต่ละครั้ง")
        if runs.empty:
            st.info("ยังไม่มีประวัติจ่ายตลาดในช่วงนี้")
        else:
            spend = runs.sort_values("shop_date")
            fig = px.line(
                spend,
                x="shop_date",
                y="total_amount",
                markers=True,
                color="title",
                labels={"shop_date": "วันที่", "total_amount": "ยอดรวม", "title": "รอบซื้อของ"},
            )
            fig.update_traces(line_shape="spline")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), legend_title_text="รอบซื้อของ")
            st.plotly_chart(fig, use_container_width=True)

    left2, right2 = st.columns(2)
    with left2:
        st.subheader("👩‍🏫 ชั่วโมงสอนแยกตามเด็ก")
        if teaching.empty:
            st.info("ยังไม่มีข้อมูล")
        else:
            by_student = teaching.groupby("student_name", as_index=False)["duration_hours"].sum().sort_values("duration_hours", ascending=False)
            fig = px.bar(
                by_student,
                x="duration_hours",
                y="student_name",
                orientation="h",
                color="duration_hours",
                color_continuous_scale="Turbo",
                labels={"student_name": "นักเรียน", "duration_hours": "ชั่วโมงรวม"},
            )
            fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with right2:
        st.subheader("🧺 สัดส่วนค่าใช้จ่ายตามหมวด")
        if items.empty:
            st.info("ยังไม่มีข้อมูล")
        else:
            by_cat = items.groupby("category", as_index=False)["line_total"].sum().sort_values("line_total", ascending=False)
            fig = px.pie(
                by_cat,
                names="category",
                values="line_total",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.RdPu,
            )
            fig.update_layout(height=430, legend_title_text="หมวดสินค้า", margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)


def page_teaching_add() -> None:
    header("🕒 จดเวลาสอนพิเศษ", "กรอกวัน เวลา ชื่อนักเรียน แล้วระบบคำนวณชั่วโมงให้อัตโนมัติ")

    with st.form("add_teaching", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            session_date = st.date_input("วันที่สอน", value=date.today())
            student_name = st.text_input("ชื่อนักเรียน *", placeholder="เช่น น้องมิ้นท์")
        with c2:
            subject = st.text_input("วิชา/หัวข้อ", placeholder="เช่น คณิต ม.2")
            hourly_rate = st.number_input("ค่าเรียนต่อชั่วโมง (ไม่กรอกได้)", min_value=0.0, step=50.0, value=0.0)
        with c3:
            start = st.time_input("เวลาเริ่ม", value=time(17, 0))
            end = st.time_input("เวลาเลิก", value=time(18, 30))
            break_minutes = st.number_input("พักกี่นาที", min_value=0, max_value=240, step=5, value=0)

        note = st.text_area("โน้ตเพิ่มเติม", placeholder="เช่น วันนี้ทำโจทย์เรื่องสมการ")
        hours = duration_hours(start, end, break_minutes)
        st.info(f"คำนวณได้ประมาณ {hours:.2f} ชั่วโมง | รายรับประมาณ {money(hours * hourly_rate)}")
        submitted = st.form_submit_button("💾 บันทึกเวลาสอน", use_container_width=True)

    if submitted:
        if not student_name.strip():
            st.error("กรุณากรอกชื่อนักเรียน")
        elif hours <= 0:
            st.error("เวลาไม่ถูกต้อง หรือพักนานเกินเวลาสอน")
        else:
            execute(
                """
                INSERT INTO teaching_sessions
                (id, session_date, day_name, student_name, subject, start_time, end_time,
                 break_minutes, duration_hours, hourly_rate, earning, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    to_date_str(session_date),
                    DAY_TH[session_date.weekday()],
                    student_name.strip(),
                    subject.strip(),
                    start.strftime("%H:%M:%S"),
                    end.strftime("%H:%M:%S"),
                    int(break_minutes),
                    float(hours),
                    float(hourly_rate),
                    float(hours * hourly_rate),
                    note.strip(),
                ],
            )
            st.success("บันทึกเรียบร้อยแล้ว ✨")

    st.subheader("รายการล่าสุด")
    df = load_teaching().head(8)
    if df.empty:
        st.caption("ยังไม่มีข้อมูล")
    else:
        st.dataframe(
            df[["session_date", "day_name", "student_name", "subject", "start_time", "end_time", "duration_hours", "earning", "note"]],
            use_container_width=True,
            hide_index=True,
        )


def page_teaching_history() -> None:
    header("📚 ประวัติการสอน", "ย้อนดูได้ว่าผ่านไปเดือนนึงหรือปีนึงสอนเด็กคนไหน วันไหนบ้าง")
    df = load_teaching()
    if df.empty:
        st.info("ยังไม่มีประวัติการสอน")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        years = ["ทั้งหมด"] + sorted(df["year"].dropna().astype(int).unique().tolist(), reverse=True)
        year = st.selectbox("ปี", years)
    with c2:
        months = ["ทั้งหมด"] + sorted(df["month"].dropna().unique().tolist(), reverse=True)
        month = st.selectbox("เดือน", months)
    with c3:
        students = ["ทั้งหมด"] + sorted(df["student_name"].dropna().unique().tolist())
        student = st.selectbox("นักเรียน", students)

    filtered = df.copy()
    if year != "ทั้งหมด":
        filtered = filtered[filtered["year"] == int(year)]
    if month != "ทั้งหมด":
        filtered = filtered[filtered["month"] == month]
    if student != "ทั้งหมด":
        filtered = filtered[filtered["student_name"] == student]

    st.metric("ชั่วโมงรวมตาม filter", f"{filtered['duration_hours'].sum():,.2f} ชม.")
    st.dataframe(
        filtered[["session_date", "day_name", "student_name", "subject", "start_time", "end_time", "duration_hours", "hourly_rate", "earning", "note"]],
        use_container_width=True,
        hide_index=True,
    )

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ ดาวน์โหลด CSV", csv, "teaching_history.csv", "text/csv")

    with st.expander("🗑️ ลบรายการที่กรอกผิด"):
        labels = {
            f"{r.session_date} | {r.student_name} | {r.start_time}-{r.end_time} | {r.duration_hours:.2f} ชม.": r.id
            for r in filtered.itertuples()
        }
        chosen = st.selectbox("เลือกรายการที่จะลบ", ["-"] + list(labels.keys()))
        if st.button("ลบรายการนี้", type="secondary", disabled=chosen == "-"):
            execute("DELETE FROM teaching_sessions WHERE id = ?", [labels[chosen]])
            st.success("ลบแล้ว")
            st.rerun()


def page_shopping() -> None:
    header("🛒 To-do list จ่ายตลาด", "ทำลิสต์ของที่จะซื้อ กดติ๊กเมื่อหยิบแล้ว พร้อมกรอกราคาและรวมยอด")
    runs = load_runs()

    with st.expander("➕ สร้างรอบซื้อของใหม่", expanded=runs.empty):
        with st.form("new_run", clear_on_submit=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                shop_date = st.date_input("วันที่ซื้อ", value=date.today())
            with c2:
                title = st.text_input("ชื่อรอบซื้อของ *", value=f"จ่ายตลาด {date.today().strftime('%d/%m/%Y')}")
            note = st.text_area("โน้ตรอบนี้", placeholder="เช่น ซื้อของเข้าบ้าน / ทำอาหารคลีน")
            ok = st.form_submit_button("สร้างรอบซื้อของ", use_container_width=True)
        if ok:
            if not title.strip():
                st.error("กรุณากรอกชื่อรอบซื้อของ")
            else:
                execute(
                    "INSERT INTO shopping_runs (run_id, shop_date, title, note) VALUES (?, ?, ?, ?)",
                    [str(uuid.uuid4()), to_date_str(shop_date), title.strip(), note.strip()],
                )
                st.success("สร้างรอบซื้อของแล้ว")
                st.rerun()

    runs = load_runs()
    if runs.empty:
        st.info("เริ่มจากสร้างรอบซื้อของก่อนนะ")
        return

    run_options = {
        f"{r.shop_date} | {r.title} | {money(r.total_amount)}": r.run_id
        for r in runs.itertuples()
    }
    selected_label = st.selectbox("เลือกรอบซื้อของ", list(run_options.keys()))
    run_id = run_options[selected_label]

    st.subheader("เพิ่มสินค้า")
    with st.form("add_item", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([2, 1.3, 1, 1, 1])
        with c1:
            item_name = st.text_input("สินค้า *", placeholder="เช่น ไข่ไก่")
        with c2:
            category = st.selectbox("หมวด", ["อาหารสด", "ผักผลไม้", "เครื่องปรุง", "ของใช้บ้าน", "ขนม/เครื่องดื่ม", "อื่น ๆ"])
        with c3:
            qty = st.number_input("จำนวน", min_value=0.0, value=1.0, step=1.0)
        with c4:
            unit = st.text_input("หน่วย", value="ชิ้น")
        with c5:
            unit_price = st.number_input("ราคาต่อหน่วย", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("เพิ่มเข้าลิสต์", use_container_width=True)
    if submitted:
        if not item_name.strip():
            st.error("กรุณากรอกชื่อสินค้า")
        else:
            execute(
                """
                INSERT INTO shopping_items
                (item_id, run_id, item_name, category, qty, unit, unit_price, picked)
                VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)
                """,
                [str(uuid.uuid4()), run_id, item_name.strip(), category, float(qty), unit.strip(), float(unit_price)],
            )
            st.success("เพิ่มสินค้าแล้ว")
            st.rerun()

    st.subheader("Checklist รอบนี้")
    items = load_items(run_id)
    if items.empty:
        st.caption("ยังไม่มีสินค้าในรอบนี้")
        return

    picked_count = int(items["picked"].sum())
    total_count = len(items)
    st.progress(picked_count / total_count if total_count else 0, text=f"หยิบแล้ว {picked_count}/{total_count} รายการ")

    display_cols = ["picked", "item_name", "category", "qty", "unit", "unit_price", "line_total"]
    edited = st.data_editor(
        items[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "picked": st.column_config.CheckboxColumn("หยิบแล้ว ✅"),
            "item_name": st.column_config.TextColumn("สินค้า"),
            "category": st.column_config.TextColumn("หมวด"),
            "qty": st.column_config.NumberColumn("จำนวน", min_value=0.0, step=1.0),
            "unit": st.column_config.TextColumn("หน่วย"),
            "unit_price": st.column_config.NumberColumn("ราคาต่อหน่วย", min_value=0.0, step=1.0, format="฿ %.2f"),
            "line_total": st.column_config.NumberColumn("รวม", format="฿ %.2f", disabled=True),
        },
        disabled=["line_total"],
        key=f"editor_{run_id}",
    )

    csave, ctotal, cpicked = st.columns([1.2, 1, 1])
    with csave:
        if st.button("💾 บันทึกสถานะ/ราคา", use_container_width=True):
            for idx, row in edited.iterrows():
                item_id = items.iloc[idx]["item_id"]
                execute(
                    """
                    UPDATE shopping_items
                    SET picked = ?, item_name = ?, category = ?, qty = ?, unit = ?, unit_price = ?
                    WHERE item_id = ?
                    """,
                    [
                        bool(row["picked"]),
                        str(row["item_name"]).strip(),
                        str(row["category"]).strip(),
                        float(row["qty"]),
                        str(row["unit"]).strip(),
                        float(row["unit_price"]),
                        item_id,
                    ],
                )
            st.success("บันทึกแล้ว")
            st.rerun()
    with ctotal:
        st.metric("ยอดรวมทั้งลิสต์", money(float((edited["qty"] * edited["unit_price"]).sum())))
    with cpicked:
        picked_total = float((edited.loc[edited["picked"], "qty"] * edited.loc[edited["picked"], "unit_price"]).sum())
        st.metric("ยอดของที่หยิบแล้ว", money(picked_total))

    with st.expander("🗑️ ลบสินค้าที่ไม่ใช้"):
        del_labels = {f"{r.item_name} | {money(r.line_total)}": r.item_id for r in items.itertuples()}
        selected = st.multiselect("เลือกรายการที่จะลบ", list(del_labels.keys()))
        if st.button("ลบสินค้าที่เลือก", disabled=not selected):
            for label in selected:
                execute("DELETE FROM shopping_items WHERE item_id = ?", [del_labels[label]])
            st.success("ลบแล้ว")
            st.rerun()


def page_shopping_history() -> None:
    header("📅 ประวัติซื้อของ", "กดดูย้อนหลังเป็นวันที่ พร้อมสรุปยอดและรายการที่ซื้อ")
    runs = load_runs()
    if runs.empty:
        st.info("ยังไม่มีประวัติซื้อของ")
        return

    selected_date = st.date_input("🗓️ เลือกวันที่เพื่อดูประวัติ", value=date.today())
    day_runs = runs[runs["shop_date"] == selected_date]

    if day_runs.empty:
        st.warning("วันนี้ยังไม่มีรอบซื้อของ ลองเลือกวันอื่นได้เลย")
    else:
        for run in day_runs.itertuples():
            with st.expander(f"🧾 {run.title} — {money(run.total_amount)}", expanded=True):
                st.caption(f"วันที่ {run.shop_date} | หยิบแล้ว {int(run.picked_count)}/{int(run.item_count)} รายการ")
                if run.note:
                    st.write(run.note)
                items = load_items(run.run_id)
                if not items.empty:
                    st.dataframe(
                        items[["picked", "item_name", "category", "qty", "unit", "unit_price", "line_total"]],
                        use_container_width=True,
                        hide_index=True,
                    )

    st.divider()
    st.subheader("สรุปรวมตามช่วงเวลา")
    c1, c2 = st.columns(2)
    with c1:
        start_d = st.date_input("จากวันที่", value=min(runs["shop_date"]), key="hist_shop_start")
    with c2:
        end_d = st.date_input("ถึงวันที่", value=max(runs["shop_date"]), key="hist_shop_end")

    filtered_runs = runs[(runs["shop_date"] >= start_d) & (runs["shop_date"] <= end_d)]
    st.metric("ยอดรวมตามช่วง", money(float(filtered_runs["total_amount"].sum())))
    st.dataframe(
        filtered_runs[["shop_date", "title", "item_count", "picked_count", "total_amount", "note"]],
        use_container_width=True,
        hide_index=True,
    )

    csv = filtered_runs.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ ดาวน์โหลด CSV", csv, "shopping_runs.csv", "text/csv")

    with st.expander("🗑️ ลบรอบซื้อของทั้งรอบ"):
        labels = {f"{r.shop_date} | {r.title} | {money(r.total_amount)}": r.run_id for r in filtered_runs.itertuples()}
        chosen = st.selectbox("เลือกรอบที่จะลบ", ["-"] + list(labels.keys()))
        if st.button("ลบรอบนี้และสินค้าทั้งหมด", type="secondary", disabled=chosen == "-"):
            selected_run_id = labels[chosen]
            execute("DELETE FROM shopping_items WHERE run_id = ?", [selected_run_id])
            execute("DELETE FROM shopping_runs WHERE run_id = ?", [selected_run_id])
            st.success("ลบแล้ว")
            st.rerun()


def page_backup() -> None:
    header("🧰 Backup / Export", "สำรองข้อมูลออกเป็น CSV เผื่อย้ายฐานข้อมูลหรือเก็บเอง")
    teaching = load_teaching()
    runs = load_runs()
    items = load_items()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "ดาวน์โหลด teaching_sessions.csv",
            teaching.to_csv(index=False).encode("utf-8-sig"),
            "teaching_sessions.csv",
            "text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "ดาวน์โหลด shopping_runs.csv",
            runs.to_csv(index=False).encode("utf-8-sig"),
            "shopping_runs.csv",
            "text/csv",
            use_container_width=True,
        )
    with c3:
        st.download_button(
            "ดาวน์โหลด shopping_items.csv",
            items.to_csv(index=False).encode("utf-8-sig"),
            "shopping_items.csv",
            "text/csv",
            use_container_width=True,
        )
    st.success("ตอนนี้ข้อมูลหลักบันทึกอยู่ใน Google Sheets แล้วค่ะ ✨ หน้านี้ยังใช้ export CSV เผื่อ backup เพิ่มเติม")


def seed_demo_data() -> None:
    teaching = load_teaching()
    runs = load_runs()
    if teaching.empty:
        today = date.today()
        demo = [
            (today - timedelta(days=1), "น้องมิ้นท์", "คณิต", time(17, 0), time(18, 30), 350),
            (today - timedelta(days=2), "น้องพี", "อังกฤษ", time(18, 0), time(19, 0), 300),
            (today - timedelta(days=5), "น้องมิ้นท์", "คณิต", time(17, 0), time(19, 0), 350),
            (today - timedelta(days=7), "น้องบีม", "วิทย์", time(10, 0), time(12, 0), 400),
        ]
        for d, student, subject, start, end, rate in demo:
            h = duration_hours(start, end)
            execute(
                """
                INSERT INTO teaching_sessions
                (id, session_date, day_name, student_name, subject, start_time, end_time,
                 break_minutes, duration_hours, hourly_rate, earning, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [str(uuid.uuid4()), to_date_str(d), DAY_TH[d.weekday()], student, subject, start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"), 0, h, rate, h * rate, "demo"],
            )
    if runs.empty:
        run_id = str(uuid.uuid4())
        execute("INSERT INTO shopping_runs (run_id, shop_date, title, note) VALUES (?, ?, ?, ?)", [run_id, to_date_str(date.today()), "จ่ายตลาดเข้าบ้าน", "demo"])
        for name, cat, qty, unit, price, picked in [
            ("ไข่ไก่", "อาหารสด", 1, "แผง", 120, True),
            ("อกไก่", "อาหารสด", 2, "กก.", 95, False),
            ("ผักสลัด", "ผักผลไม้", 1, "ถุง", 79, True),
            ("น้ำยาล้างจาน", "ของใช้บ้าน", 1, "ขวด", 45, False),
        ]:
            execute(
                """
                INSERT INTO shopping_items (item_id, run_id, item_name, category, qty, unit, unit_price, picked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [str(uuid.uuid4()), run_id, name, cat, qty, unit, price, picked],
            )


inject_css()

with st.sidebar:
    st.title("🧡 Tutor & Market")
    st.caption("เว็บจดสอนพิเศษ + จ่ายตลาด | Google Sheets")
    page = st.radio(
        "เมนู",
        [
            "✨ Dashboard",
            "🕒 จดเวลาสอน",
            "📚 ประวัติการสอน",
            "🛒 To-do จ่ายตลาด",
            "📅 ประวัติซื้อของ",
            "🧰 Backup / Export",
        ],
    )
    st.divider()
    if st.button("เติมข้อมูลตัวอย่าง", use_container_width=True):
        seed_demo_data()
        st.success("เติมข้อมูล demo แล้ว")
        st.rerun()

if page == "✨ Dashboard":
    page_dashboard()
elif page == "🕒 จดเวลาสอน":
    page_teaching_add()
elif page == "📚 ประวัติการสอน":
    page_teaching_history()
elif page == "🛒 To-do จ่ายตลาด":
    page_shopping()
elif page == "📅 ประวัติซื้อของ":
    page_shopping_history()
elif page == "🧰 Backup / Export":
    page_backup()
