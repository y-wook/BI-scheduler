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
# 팀원 순서대로 매칭될 이모티콘 컬러 서클 (청록, 갈색/주황, 보라, 핑크)
COLOR_EMOJIS = ["🟢", "🟤", "🔵", "🔴"]
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
# SQLite 저장소
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
# 날짜 및 색상 계산
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


def emoji_for(name, team):
    """팀원 이름에 맞는 고유 컬러 이모티콘을 반환합니다."""
    idx = team.index(name) if name in team else 0
    return COLOR_EMOJIS[idx % len(COLOR_EMOJIS)]


# ============================================================
# 스타일 (아이폰 12 대응 정밀 미디어 쿼리)
# ============================================================
st.markdown(
    """
    <style>
    div.block-container, [data-testid="stAppViewBlockContainer"]{
        max-width:960px;
        margin:0 auto;
        padding-left:1.0rem;
        padding-right:1.0rem;
    }
    
    div[data-testid="stHorizontalBlock"]{
        display: flex !important;
        flex-wrap: nowrap !important;
        flex-direction: row !important;
        gap: 6px !important;
    }
    div[data-testid="column"]{
        flex: 1 1 0% !important;
        min-width: 0 !important;
        width: 100% !important;
    }
    
    .day-card{border:1px solid #DDE2EA;border-radius:10px;padding:8px;min-height:112px;background:#fff;}
    .day-card.outside{background:#F0F1F4;opacity:.5;border-style:dashed;}
    .day-card.holiday{background:#FDF2F2;border-color:#E4A5A5;}
    .day-card.full{background:#FCEEDD;border-color:#B45309;}
    .day-num{font-weight:700;font-size:13px;color:#1E293B;}
    .day-num.holiday{color:#B91C1C;}
    .holiday-label{font-size:10.5px;color:#B91C1C;font-weight:700;margin-top:6px;}
    .pill{border-radius:7px;padding:4px 6px;font-size:11px;font-weight:700;color:#fff;margin-top:4px;
          overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center;}
    .month-title{background:#0F766E;color:#fff;padding:8px 12px;border-radius:8px;
                 font-weight:800;font-size:18px;text-align:center;margin-bottom:12px;}

    div[data-testid="column"] button {
        margin-top: 4px !important;
        width: 100% !important;
    }

    /* ===== 아이폰 12 및 모바일 환경 최적화 ===== */
    @media (max-width: 430px){
        div.block-container, [data-testid="stAppViewBlockContainer"]{
            padding-left:0.25rem !important;
            padding-right:0.25rem !important;
        }
        div[data-testid="stHorizontalBlock"]{
            gap:3px !important;
        }
        .day-card{padding:4px;min-height:75px;border-radius:6px;}
        .day-num{font-size:10px;}
        .holiday-label{font-size:7px;margin-top:2px;line-height:1.1;}
        .pill{font-size:8.5px;padding:2px 3px;margin-top:2px;border-radius:4px;}
        .month-title{font-size:14px;padding:6px 8px;margin-bottom:8px;}
        h1{font-size:18px !important;}
        [data-testid="stCaptionContainer"]{font-size:10px !important;}
        
        div[data-testid="column"] button p {
            font-size: 8.5px !important;
            font-weight: bold !important;
        }
        div[data-testid="column"] button {
            padding: 1px 2px !important;
            min-height: 20px !important;
            height: 20px !important;
            line-height: 1 !important;
            border-radius: 4px !important;
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

if "open_add_panel" not in st.session_state:
    st.session_state.open_add_panel = {}

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
nav1, nav2, nav3, nav4 = st.columns([1.2, 2.6, 1.2, 2], gap="small")
with nav1:
    if st.button("‹ 이전 달", key="btn-prev-month"):
        m = st.session_state.cur_month - 1
        y = st.session_state.cur_year
        if m == 0:
            m, y = 12, y - 1
        st.session_state.cur_year, st.session_state.cur_month = y, m
        st.rerun()
with nav3:
    if st.button("다음 달 ›", key="btn-next-month"):
        m = st.session_state.cur_month + 1
        y = st.session_state.cur_year
        if m == 13:
            m, y = 1, y + 1
        st.session_state.cur_year, st.session_state.cur_month = y, m
        st.rerun()
with nav4:
    if st.button("이번달로 이동", key="btn-today"):
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
    c.markdown(f"<div style='text-align:center; font-weight:700; font-size:13px;'>{label}</div>", unsafe_allow_html=True)

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
            # 1. 날짜 카드 렌더링 (텍스트 결합 없이 오직 해당 날짜 숫자만 출력하도록 수정)
            num_class = "day-num holiday" if holiday_name else "day-num"
            html = f'<div class="{css_class}"><div class="{num_class}">{date.day}</div>'
            if holiday_name:
                html += f'<div class="holiday-label">{holiday_name}</div>'
            else:
                for n in booked:
                    html += f'<div class="pill" style="background:{color_for(n, team)}">{n}</div>'
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

            # 2. 버튼 및 인터랙션 제어
            if not holiday_name:
                # 취소 버튼 레이아웃
                for n in booked:
                    if st.button(f"✕ {n}", key=f"cancel-{date_str}-{n}", help=f"{n} 신청 취소"):
                        remove_booking(date_str, n)
                        st.rerun()

                # 신청 패널 레이아웃
                if len(booked) < MAX_PER_DAY:
                    available = [m for m in team if m not in booked]
                    if available:
                        is_panel_open = st.session_state.open_add_panel.get(date_str, False)

                        if not is_panel_open:
                            if st.button("+ 신청", key=f"open-{date_str}"):
                                st.session_state.open_add_panel[date_str] = True
                                st.rerun()
                        else:
                            for member in available:
                                member_emoji = emoji_for(member, team)
                                if st.button(f"{member_emoji} {member}", key=f"add-{date_str}-{member}"):
                                    add_booking(date_str, member)
                                    st.session_state.open_add_panel[date_str] = False
                                    st.rerun()
                            
                            if st.button("닫기", key=f"close-{date_str}"):
                                st.session_state.open_add_panel[date_str] = False
                                st.rerun()

st.divider()
st.caption(
    "이 앱은 별도 로그인이나 외부 계정 없이, 앱 자체 데이터베이스에 반차 신청 내역을 저장해요. "
    "같은 링크에 접속한 팀원 모두에게 실시간으로 반영됩니다."
)
