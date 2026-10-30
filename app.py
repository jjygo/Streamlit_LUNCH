import streamlit as st
import altair as alt
import pandas as pd
import qrcode
import re
import socket
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

st.set_page_config(page_title='오늘 점심 투표', page_icon='🍚')



# 1. 투표 후보 (DB restaurants 테이블에서 드림디포 서초남점 반경 500m 안, 가까운 순)
def get_restaurant_candidates():
    with lock:
        return [name for name, in conn.execute(
            'SELECT name FROM restaurants WHERE distance_m <= 500 ORDER BY distance_m')]


# 2. DB 연결 (모든 세션이 연결 1개 + 락 1개를 공유)
# ponytail: Streamlit Cloud는 재부팅/재배포 때 파일이 초기화돼 표가 사라짐, 오래 보관하려면 외부 DB로
@st.cache_resource
def get_db():
    conn = sqlite3.connect(Path(__file__).parent / 'lunch_votes.db',
                           check_same_thread=False, timeout=5)
    conn.execute('PRAGMA journal_mode=WAL')
    # 배포 서버는 UTC라서 시간은 한국 시간(+9시간)으로 저장
    conn.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL,
        choice TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+9 hours')))''')
    # 식당 목록 원본은 restaurants.csv (db 파일은 git에 안 올라가니까 앱 켤 때마다 CSV로 다시 채움)
    pd.read_csv(Path(__file__).parent / 'restaurants.csv').to_sql(
        'restaurants', conn, if_exists='replace', index=False)
    return conn, threading.Lock()


conn, lock = get_db()
candidates = get_restaurant_candidates()

# 3. 접속 주소 (배포 중이면 지금 브라우저 주소 그대로, 로컬 실행이면 같은 와이파이 폰이 들어올 수 있게 LAN IP로)
url = (st.context.url or '').split('/~/+')[0]  # Streamlit Cloud는 앱을 /~/+ 경로로 띄움
if urlparse(url).hostname in (None, 'localhost', '127.0.0.1'):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))  # UDP라 실제로 패킷은 안 나감, 내 LAN IP만 알아냄
            lan_ip = s.getsockname()[0]
    except OSError:
        lan_ip = '127.0.0.1'
    url = f"http://{lan_ip}:{st.get_option('server.port')}/"

# 4. 헤더 (날짜 + 제목 + QR 공유)
today = datetime.now(timezone(timedelta(hours=9)))
head, share = st.columns([3, 1], vertical_alignment='bottom')
with head:
    st.caption(f"{today:%Y.%m.%d} ({'월화수목금토일'[today.weekday()]})")
    st.title('점심 뭐 먹지?', anchor=False)
with share:
    with st.popover('QR 공유', type='tertiary', icon=':material/qr_code_2:', width='stretch'):
        if '//127.0.0.1' in url:
            st.warning('LAN IP를 못 찾았어요. 와이파이 연결이나 VPN을 확인하세요.')
        st.image(qrcode.make(url).get_image(), width=220)
        st.caption('휴대폰 카메라로 찍으면 바로 열려요')
        st.code(url, language=None)

# 5. 투표하기 (브라우저 세션당 1표)
# ponytail: session_state 기준이라 새로고침하면 다시 투표 가능, 막아야 하면 쿠키/기기 ID로 바꾸기
with lock:
    info = pd.read_sql('SELECT * FROM restaurants', conn).set_index('name')


def short(name):
    return re.sub(r'\s\S+점$', '', name)  # 화면 좁은 곳에선 지점명 빼기 ('도라스시 남부터미널점' → '도라스시')


if 'voted' not in st.session_state:
    with st.form('vote'):
        choice = st.radio('식당 고르기', candidates, index=None, captions=[
            f'{r.menu} {r.price:,.0f}원 · {r.distance_m}m · ★{r.rating}'
            for r in info.loc[candidates].itertuples()])
        nickname = st.text_input('닉네임 (선택)', max_chars=20, placeholder='비우면 익명')
        submitted = st.form_submit_button('투표하기', type='primary', width='stretch')
    if submitted and not choice:
        st.warning('메뉴를 골라주세요.')
    elif submitted:
        with lock:
            conn.execute('INSERT INTO votes (nickname, choice) VALUES (?, ?)',
                         (nickname.strip() or '익명', choice))
            conn.commit()
        st.session_state.voted = choice
        st.rerun()
else:
    st.success(f'**{st.session_state.voted}**에 투표했어요', icon=':material/check_circle:')


# 6. 실시간 현황 (2초마다 이 부분만 다시 그림)
@st.fragment(run_every='2s')
def dashboard():
    with lock:
        rows = conn.execute("""SELECT choice, COUNT(*) FROM votes
            WHERE date(created_at) = date('now', '+9 hours') GROUP BY choice""").fetchall()
    votes = pd.Series(dict(rows), dtype=int).reindex(candidates, fill_value=0)

    st.subheader('실시간 현황', anchor=False)
    left, right = st.columns([1, 2], wrap=False)  # 폰에서도 나란히, 1위 메뉴 이름이 잘리지 않게 오른쪽을 넓게
    left.metric('참여', f'{sum(n for _, n in rows)}명', border=True)  # 후보 목록이 바뀌어도 이미 받은 표는 셈
    top = votes[votes == votes.max()].index.tolist()
    if votes.max() == 0:
        right.metric('1위', '아직 없음', border=True)
    elif len(top) == 1:
        right.metric(f'1위 · {votes.max()}표', short(top[0]), border=True)
        st.caption(f'[{top[0]} 카카오맵에서 보기 →]({info.at[top[0], "kakao_url"]})')
    else:
        right.metric(f'공동 1위 · {votes.max()}표', f'{len(top)}곳 동률', border=True)
        st.caption(' · '.join(short(n) for n in top))

    # 가로 막대 (표 많은 순, 같으면 가까운 순, 0표도 표시, 막대 끝에 표 수)
    # 색은 config.toml 의 primaryColor 와 맞춤, 글자는 막대색 말고 본문색
    dark = st.context.theme.type == 'dark'
    accent, ink = ('#C2502F', '#F2ECE3') if dark else ('#9C4026', '#2B2622')
    df = votes.rename(short).rename_axis('식당').reset_index(name='표')
    order = df.sort_values('표', ascending=False, kind='stable')['식당'].tolist()
    bars = alt.Chart(df).mark_bar(color=accent, size=16, cornerRadiusEnd=4).encode(
        x=alt.X('표:Q', axis=None, scale=alt.Scale(domain=[0, max(votes.max(), 1) * 1.2])),
        y=alt.Y('식당:N', sort=order, title=None, axis=alt.Axis(
            ticks=False, domain=False, labelPadding=8, labelFontSize=14, labelLimit=150, labelColor=ink)),
        tooltip=['식당', '표'],
    )
    labels = bars.mark_text(align='left', dx=6, fontSize=13, color=ink).encode(text='표:Q')
    st.altair_chart((bars + labels).properties(height=len(candidates) * 28), width='stretch')


dashboard()
