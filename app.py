import streamlit as st
import altair as alt
import html
import json
import math
import pandas as pd
import qrcode
import random
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


def wheel_html(names, spin, target, turn, dark):
    # 돌림판 SVG (결과는 파이썬에서 미리 뽑고, 화면은 그 칸에 멈추게 돌리기만 함)
    ink = '#F2ECE3' if dark else '#2B2622'
    n, R, seg = len(names), 140, 360 / len(names)
    slices = []
    for i, name in enumerate(names):
        # 두 색 번갈아, 칸 수가 홀수면 마지막 칸만 세 번째 색 (첫 칸과 같은 색이 붙지 않게)
        fill, text = ('#E3B9A5', '#2B2622') if n % 2 and i == n - 1 else [('#C2502F', '#FFFFFF'), ('#F2EBDF', '#2B2622')][i % 2]
        a0, a1 = math.radians(i * seg), math.radians((i + 1) * seg)
        label = html.escape(name if len(name) <= 7 else name[:6] + '…')
        slices.append(
            f'<path d="M0 0L{R * math.sin(a0):.1f} {-R * math.cos(a0):.1f}'
            f'A{R} {R} 0 0 1 {R * math.sin(a1):.1f} {-R * math.cos(a1):.1f}Z" fill="{fill}"/>'
            f'<text transform="rotate({(i + .5) * seg:.1f}) translate(0 -34) rotate(-90)" fill="{text}">{label}</text>')
    before = f'돌리기를 누르면 {n}곳 중 한 곳을 골라줘요'
    after = f'「{names[target]}」 당첨! 아래 목록에 골라 뒀어요' if spin else before
    return f'''<!-- spin {spin} -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css">
<style>
body {{ margin: 0; font-family: Pretendard, sans-serif; color: {ink}; text-align: center; }}
.box {{ position: relative; width: 280px; margin: 8px auto 0; }}
.pin {{ position: absolute; left: 50%; top: -6px; transform: translateX(-50%); z-index: 1;
        border: 11px solid transparent; border-top: 20px solid {ink}; }}
#w {{ transition: transform 4s cubic-bezier(.15, .85, .1, 1); }}
svg {{ display: block; width: 280px; height: 280px; }}
text {{ font-size: 11px; dominant-baseline: middle; }}
#msg {{ margin-top: 12px; font-size: 15px; }}
@media (prefers-reduced-motion: reduce) {{ #w {{ transition: none; }} }}
</style>
<div class="box"><div class="pin"></div><div id="w">
<svg viewBox="-142 -142 284 284">{''.join(slices)}
<circle r="{R}" fill="none" stroke="{ink}" stroke-opacity=".25"/><circle r="14" fill="{ink}"/></svg></div></div>
<div id="msg" aria-live="polite">{before}</div>
<script>
const w = document.getElementById('w'), msg = document.getElementById('msg');
const done = () => msg.textContent = {json.dumps(after)};
if ({spin}) {{
  requestAnimationFrame(() => requestAnimationFrame(() => w.style.transform = 'rotate({turn:.1f}deg)'));
  w.addEventListener('transitionend', done);
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) done();
}}
</script>'''


if 'voted' not in st.session_state:
    # 5-1. 돌림판 (뽑힌 식당은 아래 목록에 미리 선택됨)
    with st.expander('못 고르겠으면 돌림판', icon=':material/casino:'):
        if st.button('돌리기', icon=':material/refresh:', width='stretch'):
            k = random.randrange(len(candidates))
            seg = 360 / len(candidates)
            turn = 360 * 6 - (k + .5) * seg + random.uniform(-.35, .35) * seg  # 6바퀴 돌고 k번째 칸에서 멈춤
            st.session_state.pick = candidates[k]
            st.session_state.wheel = (st.session_state.get('wheel', (0,))[0] + 1, k, turn)
        spin, k, turn = st.session_state.get('wheel', (0, 0, 0))
        st.iframe(wheel_html([short(n) for n in candidates], spin, k, turn,
                             st.context.theme.type == 'dark'), height=330)

    # 5-2. 식당 고르고 투표 (돌림판이나 상세 페이지에서 고른 식당이 있으면 미리 선택)
    pick = st.session_state.get('pick')
    with st.container(border=True):
        choice = st.radio('식당 고르기', candidates, index=candidates.index(pick) if pick in candidates else None,
                          captions=[f'{r.menu} {r.price:,.0f}원 · {r.distance_m}m · ★{r.rating}'
                                    for r in info.loc[candidates].itertuples()])
        if choice:
            st.page_link('pages/restaurant.py', label=f'「{short(choice)}」 자세히 보기',
                         icon=':material/info:', query_params={'r': choice})
        nickname = st.text_input('닉네임 (선택)', max_chars=20, placeholder='비우면 익명')
        if st.button('투표하기', type='primary', width='stretch'):
            if not choice:
                st.warning('식당을 골라주세요.')
            else:
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
        st.page_link('pages/restaurant.py', label=f'「{short(top[0])}」 자세히 보기',
                     icon=':material/info:', query_params={'r': top[0]})
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
