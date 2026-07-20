import datetime
import calendar as pycal
import sqlite3
from pathlib import Path

import streamlit as st

# ============================================================
# 기본 설정
# ============================================================
st.set_page_config(page_title="BI 스케줄러", page_icon="🗓️", layout="wide")

MAX_PER_DAY = 2
COLORS = ["#0F766E", "#B45309", "#4338CA", "#BE185D"]
DAY_LABELS = ["월", "화", "수", "목", "금"]
DEFAULT_TEAM = ["팀원1", "팀원2", "팀원3", "팀원4"]
DB_PATH = Path(__file__).parent / "bi_scheduler_data.db"

HOLIDAYS = {
    "2026-01-01": "신정", "2026-02-16": "설날 연휴", "2026-02-17": "설날", "2026-02-18": "설날 연휴",
    "2026-03-02": "대체공휴일(삼일절)", "2026-05-01": "근로자의 날", "2026-05-05": "어린이날",
    "2026-05-25": "대체공휴일(부처님오신날)", "2026-06-03": "전국동시지방선거", "2026-07-17": "제헌절",
    "2026-08-17": "대체공휴일(광복절)", "2026-09-24": "추석 연휴", "2026-09-25": "추석",
    "2026-10-05": "대체공휴일(개천절)", "2026-10-09": "한글날", "2026-12-25": "크리스마스",
    "2027-01-01": "신정", "2027-02-08": "설날 연휴", "2027-02-09": "대체공휴일(설날)",
    "2027-03-01": "삼일절", "2027-05-03": "대체공휴일(노동절)", "2027-05-05": "어린이날",
    "2027-05-13": "부처님오신날", "2027-07-19": "대체공휴일(제헌절)", "2027-08-16": "대체공휴일(광복절)",
    "2027-09-14": "추석 연휴", "2027-09-15": "추석", "2027-09-16": "추석 연휴",
    "2027-10-04": "대체공휴일(개천절)", "2027-10-11": "대체공휴일(한글날)", "2027-12-27": "대체공휴일(크리스마스)",
    "2028-01-26": "설날 연휴", "2028-01-27": "설날", "2028-01-28": "설날 연휴", "2028-03-01": "삼일절",
    "2028-04-12": "국회의원 선거일", "2028-05-01": "노동절", "2028-05-02": "부처님오신날", "2028-05-05": "어린이날",
    "2028-06-06": "현충일", "2028-07-17": "제헌절", "2028-08-15": "광복절", "2028-10-02": "추석 연휴",
    "2028-10-03": "추석·개천절", "2028-10-04": "추석 연휴", "2028-10-05": "대체공휴일(개천절)",
    "2028-10-09": "한글날", "2028-12-25": "크리스마스",
}

# ============================================================
# SQLite 저장소 (구글시트/외부 계정 불필요, 앱 안에서 자체 저장)
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS team (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS bookings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, name TEXT NOT NULL)"
    )
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM team").fetchone()
    if row[0] == 0:
        conn.executemany("INSERT INTO team (name) VALUES (?)", [(n,) for n in DEFAULT_TEAM])
        conn.commit()
    conn.close()


def load_team():
    conn = get_conn()
    rows = conn.execute("SELECT name FROM team ORDER BY id").fetchall()
    conn.close()
    names = [r[0] for r in rows]
    return names[:4] if len(names) >= 4 else (names + DEFAULT_TEAM[len(names):])[:4]


def save_team(names):
    conn = get_conn()
    old_names = load_team()
    conn.execute("DELETE FROM team")
    conn.executemany("INSERT INTO team (name) VALUES (?)", [(n,) for n in names])
    for old, new in zip(old_names, names):
        if old != new:
            conn.execute("UPDATE bookings SET name = ? WHERE name = ?", (new, old))
    conn.commit()
    conn.close()


def load_bookings():
    conn = get_conn()
    rows = conn.execute("SELECT date, name FROM bookings ORDER BY id").fetchall()
    conn.close()
    booked = {}
    for date_str, name in rows:
        booked.setdefault(date_str, []).append(name)
    return booked


def add_booking(date_str, name):
    conn = get_conn()
    conn.execute("INSERT INTO bookings (date, name) VALUES (?, ?)", (date_str, name))
    conn.commit()
    conn.close()


def remove_booking(date_str, name):
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM bookings WHERE date = ? AND name = ? LIMIT 1", (date_str, name)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM bookings WHERE id = ?", (row[0],))
        conn.commit()
    conn.close()


init_db()

# ============================================================
# 날짜 계산
# ============================================================
def month_weeks(year, month):
    first = datetime.date(year, month, 1)
    last = datetime.date(year, month, pycal.monthrange(year, month)[1])
    start = first - datetime.timedelta(days=first.weekday())
    end = last + datetime.timedelta(days=(4 - last.weekday())) if last.weekday() <= 4 \
        else last + datetime.timedelta(days=(7 - last.weekday()))
    weeks, week, d = [], [], start
    while d <= end:
        if d.weekday() <= 4:
            week.append(d)
            if len(week) == 5:
                weeks.append(week)
                week = []
        d += datetime.timedelta(days=1)
    return weeks


def color_for(name, team):
    idx = team.index(name) if name in team else 0
    return COLORS[idx % len(COLORS)]


# ============================================================
# 스타일
# ============================================================
st.markdown(
    """
    <style>
    div.block-container, [data-testid="stAppViewBlockContainer"]{
        max-width:960px;
        min-width:760px;
        margin:0 auto;
        padding-left:1.5rem;
        padding-right:1.5rem;
        overflow-x:auto;
    }
    /* 모바일에서도 5칸 가로 배치를 유지 (기본은 세로로 쌓임) */
    div[data-testid="stHorizontalBlock"]{
        flex-wrap:nowrap !important;
        flex-direction:row !important;
    }
    div[data-testid="column"]{
        min-width:130px !important;
        width:auto !important;
    }
    .day-card{border:1px solid #DDE2EA;border-radius:10px;padding:6px;min-height:112px;background:#fff;}
    .day-card.outside{background:#F0F1F4;opacity:.6;border-style:dashed;}
    .day-card.holiday{background:#FDF2F2;border-color:#E4A5A5;}
    .day-card.full{background:#FCEEDD;border-color:#B45309;}
    .day-num{font-weight:700;font-size:12.5px;}
    .day-num.holiday{color:#B91C1C;}
    .holiday-label{font-size:10.5px;color:#B91C1C;font-weight:700;margin-top:6px;}
    .pill{border-radius:7px;padding:3px 5px;font-size:11px;font-weight:700;color:#fff;margin-top:4px;
          overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .month-title{background:#0F766E;color:#fff;padding:7px 12px;border-radius:8px;
                 font-weight:800;font-size:16px;text-align:center;margin-bottom:10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 상태 초기화
# ============================================================
today = datetime.date.today()
if "cur_year" not in st.session_state:
    st.session_state.cur_year = today.year
    st.session_state.cur_month = today.month

# ============================================================
# 헤더
# ============================================================
st.title("🗓️ BI 스케줄러")
st.caption("주 1회 오후 반차 · 하루 최대 2명까지 신청할 수 있어요 · 로그인 없이 누구나 사용할 수 있어요")

team = load_team()

with st.expander("팀원 이름 수정"):
    cols = st.columns(4)
    new_names = []
    for i, col in enumerate(cols):
        with col:
            st.markdown(
                f'<div style="width:14px;height:14px;border-radius:50%;background:{COLORS[i]};'
                f'display:inline-block;margin-right:6px;"></div>',
                unsafe_allow_html=True,
            )
            new_names.append(st.text_input(f"팀원 {i+1}", value=team[i], key=f"team_input_{i}"))
    if st.button("팀원 이름 저장"):
        save_team(new_names)
        st.success("저장했어요.")
        st.rerun()

# ============================================================
# 월 네비게이션
# ============================================================
nav1, nav2, nav3, nav4 = st.columns([1, 3, 1, 2])
with nav1:
    if st.button("‹ 이전 달"):
        m = st.session_state.cur_month - 1
        y = st.session_state.cur_year
        if m == 0:
            m, y = 12, y - 1
        st.session_state.cur_year, st.session_state.cur_month = y, m
        st.rerun()
with nav3:
    if st.button("다음 달 ›"):
        m = st.session_state.cur_month + 1
        y = st.session_state.cur_year
        if m == 13:
            m, y = 1, y + 1
        st.session_state.cur_year, st.session_state.cur_month = y, m
        st.rerun()
with nav4:
    if st.button("이번달로 이동"):
        st.session_state.cur_year, st.session_state.cur_month = today.year, today.month
        st.rerun()

cur_year, cur_month = st.session_state.cur_year, st.session_state.cur_month
st.markdown(f'<div class="month-title">{cur_year}년 {cur_month}월</div>', unsafe_allow_html=True)

# ============================================================
# 캘린더 렌더링
# ============================================================
bookings = load_bookings()
weeks = month_weeks(cur_year, cur_month)

header_cols = st.columns(5)
for c, label in zip(header_cols, DAY_LABELS):
    c.markdown(f"**{label}**")

for week in weeks:
    cols = st.columns(5)
    for col, date in zip(cols, week):
        date_str = date.isoformat()
        in_month = date.month == cur_month
        holiday_name = HOLIDAYS.get(date_str)
        booked = bookings.get(date_str, [])
        is_full = len(booked) >= MAX_PER_DAY

        css_class = "day-card"
        if not in_month:
            css_class += " outside"
        if holiday_name:
            css_class += " holiday"
        elif is_full:
            css_class += " full"

        with col:
            date_label = f"{date.day}" + ("" if in_month else " (다른달)")
            num_class = "day-num holiday" if holiday_name else "day-num"
            html = f'<div class="{css_class}"><div class="{num_class}">{date_label}</div>'
            if holiday_name:
                html += f'<div class="holiday-label">{holiday_name}</div>'
            else:
                for n in booked:
                    html += f'<div class="pill" style="background:{color_for(n, team)}">{n}</div>'
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

            if not holiday_name:
                for n in booked:
                    if st.button(f"취소: {n}", key=f"cancel-{date_str}-{n}"):
                        remove_booking(date_str, n)
                        st.rerun()
                if len(booked) < MAX_PER_DAY:
                    available = [m for m in team if m not in booked]
                    if available:
                        sel = st.selectbox(
                            "신청자", available, key=f"sel-{date_str}", label_visibility="collapsed"
                        )
                        if st.button("+ 신청", key=f"add-{date_str}"):
                            add_booking(date_str, sel)
                            st.rerun()

st.divider()
st.caption(
    "이 앱은 별도 로그인이나 외부 계정 없이, 앱 자체 데이터베이스에 반차 신청 내역을 저장해요. "
    "같은 링크에 접속한 팀원 모두에게 실시간으로 반영됩니다."
)
