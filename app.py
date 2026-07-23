import datetime
import calendar as pycal

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# 기본 설정
# ============================================================
st.set_page_config(page_title="BI 스케줄러", page_icon="🗓️", layout="wide")

MAX_PER_DAY = 2
COLORS = ["#0F766E", "#B45309", "#4338CA", "#BE185D"]
DAY_LABELS = ["월", "화", "수", "목", "금"]
DEFAULT_TEAM = ["팀원1", "팀원2", "팀원3", "팀원4"]
TEAM_SHEET_NAME = "team"

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
# 구글시트 연결 (실시간 공용 저장소 — 앱이 재시작돼도 데이터가 유지됨)
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def get_spreadsheet():
    return get_client().open_by_key(st.secrets["sheet_id"])


def get_or_create_worksheet(sh, title, header):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=len(header))
        ws.append_row(header)
    return ws


@st.cache_data(ttl=8)
def load_team():
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, TEAM_SHEET_NAME, ["name"])
    values = ws.col_values(1)[1:]
    names = [v for v in values if v.strip()]
    if not names:
        names = DEFAULT_TEAM[:]
        _save_team_raw(names)
    return names[:4] if len(names) >= 4 else (names + DEFAULT_TEAM[len(names):])[:4]


def _save_team_raw(names):
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, TEAM_SHEET_NAME, ["name"])
    ws.clear()
    ws.append_row(["name"])
    for n in names:
        ws.append_row([n])


def save_team(names):
    old_names = load_team()
    _save_team_raw(names)
    sh = get_spreadsheet()
    for ws in sh.worksheets():
        if not ws.title.startswith("bookings-"):
            continue
        cells = ws.get_all_values()
        for old, new in zip(old_names, names):
            if old == new:
                continue
            for i, row in enumerate(cells[1:], start=2):
                if len(row) >= 2 and row[1] == old:
                    ws.update_cell(i, 2, new)
    load_team.clear()
    load_bookings_for_month.clear()


@st.cache_data(ttl=8)
def load_bookings_for_month(year, month):
    sh = get_spreadsheet()
    tab = f"bookings-{year:04d}-{month:02d}"
    ws = get_or_create_worksheet(sh, tab, ["date", "name"])
    records = ws.get_all_records()
    booked = {}
    for rec in records:
        d = str(rec.get("date", "")).strip()
        n = str(rec.get("name", "")).strip()
        if not d or not n:
            continue
        booked.setdefault(d, []).append(n)
    return booked


def load_bookings_for_weeks(weeks):
    months_needed = sorted({(d.year, d.month) for week in weeks for d in week})
    merged = {}
    for (y, m) in months_needed:
        merged.update(load_bookings_for_month(y, m))
    return merged


def add_booking(date_str, name):
    y, m = int(date_str[:4]), int(date_str[5:7])
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, f"bookings-{y:04d}-{m:02d}", ["date", "name"])
    ws.append_row([date_str, name])
    load_bookings_for_month.clear()


def remove_booking(date_str, name):
    y, m = int(date_str[:4]), int(date_str[5:7])
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, f"bookings-{y:04d}-{m:02d}", ["date", "name"])
    cells = ws.get_all_values()
    for i, row in enumerate(cells[1:], start=2):
        if len(row) >= 2 and row[0] == date_str and row[1] == name:
            ws.delete_rows(i)
            break
    load_bookings_for_month.clear()


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
        margin:0 auto;
        padding-left:1.5rem;
        padding-right:1.5rem;
    }
    div[data-testid="stHorizontalBlock"]{
        flex-wrap:nowrap !important;
        flex-direction:row !important;
        gap:6px !important;
    }
    div[data-testid="column"]{
        min-width:110px;
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

    @media (max-width: 700px){
        div.block-container, [data-testid="stAppViewBlockContainer"]{
            padding-left:0.4rem;
            padding-right:0.4rem;
        }
        div[data-testid="stHorizontalBlock"]{
            gap:3px !important;
        }
        div[data-testid="column"]{
            min-width:0;
            padding:0 !important;
        }
        .day-card{padding:3px;min-height:82px;border-radius:6px;}
        .day-num{font-size:10px;}
        .holiday-label{font-size:7.5px;margin-top:3px;line-height:1.2;}
        .pill{font-size:8px;padding:2px 3px;margin-top:2px;border-radius:5px;}
        .month-title{font-size:13px;padding:5px 8px;}
        h1{font-size:20px !important;}
        [data-testid="stCaptionContainer"]{font-size:11px !important;}
        div[data-testid="column"] .stButton button{
            font-size:8.5px !important;
            padding:1px 3px !important;
            min-height:0 !important;
            height:auto !important;
        }
        div[data-testid="column"] [data-baseweb="select"]{
            font-size:8.5px !important;
            min-height:0 !important;
        }
        div[data-testid="column"] [data-baseweb="select"] > div{
            padding:1px 4px !important;
            min-height:22px !important;
        }
    }
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
weeks = month_weeks(cur_year, cur_month)
bookings = load_bookings_for_weeks(weeks)

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
                        with st.popover("+ 신청", use_container_width=True):
                            for m in available:
                                pc1, pc2 = st.columns([1, 5])
                                with pc1:
                                    st.markdown(
                                        f'<div style="width:12px;height:12px;border-radius:50%;'
                                        f'background:{color_for(m, team)};margin-top:9px;"></div>',
                                        unsafe_allow_html=True,
                                    )
                                with pc2:
                                    if st.button(m, key=f"add-{date_str}-{m}", use_container_width=True):
                                        add_booking(date_str, m)
                                        st.rerun()

st.divider()
st.caption(
    "이 앱은 구글시트를 데이터 저장소로 사용해요. 앱이 재시작되어도 신청 데이터는 안전하게 유지됩니다. "
    "로그인 없이 누구나 사용할 수 있어요."
)
