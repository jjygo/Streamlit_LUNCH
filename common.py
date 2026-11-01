# 세 페이지가 같이 쓰는 것: DB 연결, 식당 표, 계산 함수, 앱 주소
import math
import re
import socket
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
import streamlit as st

KST = timezone(timedelta(hours=9))
DAYS = '월화수목금토일'
BASE = (37.4866, 127.0205)  # 기준점: 드림디포 서초남점 (거리 계산 기준)
HERE = Path(__file__).parent


# 1. DB 연결 (모든 세션이 연결 1개 + 락 1개를 공유)
# ponytail: Streamlit Cloud는 재부팅/재배포 때 파일이 초기화돼 표가 사라짐, 오래 보관하려면 외부 DB로
@st.cache_resource
def get_db():
    conn = sqlite3.connect(HERE / 'lunch_votes.db', check_same_thread=False, timeout=5)
    conn.execute('PRAGMA journal_mode=WAL')
    # 배포 서버는 UTC라서 시간은 한국 시간(+9시간)으로 저장
    conn.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL,
        choice TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+9 hours')))''')
    # 식당 목록 원본은 restaurants.csv (db 파일은 git에 안 올라가니까 앱 켤 때마다 CSV로 다시 채움)
    pd.read_csv(HERE / 'restaurants.csv').to_sql('restaurants', conn, if_exists='replace', index=False)
    return conn, threading.Lock()


conn, lock = get_db()

# 2. 식당 표 (투표 후보 = 기준점에서 500m 안, 가까운 순)
with lock:
    shops = pd.read_sql('SELECT * FROM restaurants WHERE distance_m <= 500 ORDER BY distance_m',
                        conn).set_index('name')


def short(name):
    return re.sub(r'\s\S+점$', '', name)  # 좁은 곳에선 지점명 빼기 ('도라스시 남부터미널점' → '도라스시')


def walk_min(meters):
    return max(1, round(meters * 1.3 / 67))  # ponytail: 직선거리 x1.3, 분당 67m로 어림, 정확히 하려면 길찾기 API


def now_kst():
    return datetime.now(KST)


# 3. 오늘 휴무 · 영업 상태 (now를 받아서 계산만 하는 함수라 맨 아래 셀프 체크로 확인 가능)
def closed_today(closed, now):
    return isinstance(closed, str) and DAYS[now.weekday()] in closed.split(',')


def open_status(hours, closed, now):
    """('open' | 'before' | 'after' | 'closed', 배지 문구) 를 돌려줌"""
    if closed_today(closed, now):
        return 'closed', '오늘 휴무'
    start, end = [int(t[:2]) * 60 + int(t[3:]) for t in hours.split('~')]  # '11:00~21:30' → 660, 1290
    m = now.hour * 60 + now.minute
    if start == 0 and end == 1440:
        return 'open', '영업 중 · 24시간'
    is_open = start <= m < end if start < end else (m >= start or m < end)  # 닫는 시각이 더 이르면 자정 넘김
    if is_open:
        return 'open', f'영업 중 · {hours[-5:]}까지'
    if m < start:
        return 'before', f'영업 전 · {hours[:5]} 오픈'
    return 'after', '오늘 영업 끝'


BADGE = {'open': ('green', ':material/schedule:'), 'before': ('gray', ':material/schedule:'),
         'after': ('gray', ':material/bedtime:'), 'closed': ('red', ':material/event_busy:')}


def badge_md(state, text):
    return f':{BADGE[state][0]}-badge[{text}]'  # 문장 안에 넣는 배지 (st.badge는 한 줄 전체를 씀)


def price_band(price):
    if price <= 10000:
        return '1만원 이하'
    if price <= 20000:
        return '1~2만원'
    return '2만원 넘게'


def nearby(name, k=3):
    """같은 종류 중 이 식당에서 가까운 곳 (없으면 종류 상관없이) → (이름, 걸어서 분) 목록, 같은종류인지"""
    me = shops.loc[name]

    def dist(r):  # 이 식당에서 r까지 몇 m인지 (위경도로 어림)
        dx = (r.lng - me.lng) * math.cos(math.radians(me.lat)) * 111320
        dy = (r.lat - me.lat) * 110540
        return math.hypot(dx, dy)

    others = shops.drop(name)
    same = others[others.category == me.category]
    pool = same if len(same) else others
    near = sorted(pool.itertuples(), key=dist)[:k]
    return [(r.Index, walk_min(dist(r))) for r in near], len(same) > 0


# 4. 오늘 받은 표 (식당 이름 → 표 수, 닉네임 목록)
def today_votes():
    with lock:
        rows = conn.execute("""SELECT choice, nickname FROM votes
            WHERE date(created_at) = date('now', '+9 hours') ORDER BY id""").fetchall()
    who = {}
    for choice, nick in rows:
        who.setdefault(choice, []).append(nick)
    return who


def ranking(who):
    # 오늘 표를 많은 순 (같으면 가까운 순)으로: [(식당, 표 수, 닉네임 목록)], 참여 인원
    total = sum(len(v) for v in who.values())  # 후보 목록이 바뀌어도 이미 받은 표는 셈
    rows = [(n, len(v), v) for n, v in who.items() if n in shops.index]
    return sorted(rows, key=lambda x: (-x[1], shops.at[x[0], 'distance_m'])), total


def leaders(ranked):
    # 1위 표 수와 1위 식당 목록 (공동 1위면 여러 곳, 표가 없으면 0, [])
    if not ranked:
        return 0, []
    k = ranked[0][1]
    return k, [n for n, c, _ in ranked if c == k]


# 5. 투표 저장: DB에 쓰는 곳은 여기 한 곳 (첫 투표는 INSERT, 그 뒤로는 내 표 1개만 UPDATE)
#    투표방·마감 시간 검사를 넣게 되면 이 함수 맨 위에 넣으면 됨
# ponytail: session_state 기준이라 새로고침하면 다시 투표 가능 + 예전 표는 못 바꿈, 막아야 하면 쿠키/기기 ID로 바꾸기
def save_vote(name, nickname=''):
    with lock:
        if 'vote_id' in st.session_state:  # 이미 한 표 있음 (바꾸기 · 확인 창 버튼 두 번 누름) → 내 줄만 고침
            conn.execute('UPDATE votes SET choice = ? WHERE id = ?', (name, st.session_state.vote_id))
        else:
            st.session_state.vote_id = conn.execute('INSERT INTO votes (nickname, choice) VALUES (?, ?)',
                                                    (nickname.strip() or '익명', name)).lastrowid
        conn.commit()
    # toast: 다음 화면 맨 위(vote.py 1번)에서 꺼내 띄움. 완료 배너와 같은 말을 되풀이하지 않게,
    # 바꿨을 때는 바뀐 곳을 ('로/으로'는 받침 따라 달라져서 '에 옮겼어요')
    if st.session_state.get('editing'):
        toast = f'내 표를 「{short(name)}」에 옮겼어요'
    else:
        toast = '투표가 반영됐어요. 실시간 현황에서 확인하세요'
    st.session_state.update(voted=name, editing=False, toast=toast)


# 6. 닉네임을 화면에 쓸 때 (닉네임은 아무나 쓰니까 Markdown으로 해석되지 않고 글자 그대로 보이게)
def plain(text):
    # 기호 앞에 \ (굵게·링크·수식·HTML이 안 되게), 주소·이모지 글자(:smile:)가 안 바뀌게
    # . 앞과 : 뒤에 안 보이는 공백(\u200b)
    text = re.sub(r'([\\`*_~#<>|!$&{}\[\]()+-])', r'\\\1', text)
    return text.replace('.', '\u200b.').replace(':', ':\u200b')


def who_line(names, md=True):
    # 닉네임 줄: '민지 · 준호 · 익명 2' (익명은 숫자로 묶음)
    # md=False: Markdown이 아닌 곳(차트 툴팁)용, 기호를 풀지 않고 글자 그대로
    named = [plain(n) if md else n for n in names if n != '익명']
    anon = len(names) - len(named)
    return ' · '.join(named + ([f'익명 {anon}'] if anon else []))


# 7. 앱 기본 주소 (배포 중이면 지금 주소, 로컬이면 같은 와이파이 폰이 들어올 수 있게 LAN IP)
def app_url():
    u = urlparse((st.context.url or '').split('/~/+')[0])  # Streamlit Cloud는 앱을 /~/+ 경로로 띄움
    if u.hostname in (None, 'localhost', '127.0.0.1'):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 80))  # UDP라 실제로 패킷은 안 나감, 내 LAN IP만 알아냄
                ip = s.getsockname()[0]
        except OSError:
            ip = '127.0.0.1'
        return f"http://{ip}:{st.get_option('server.port')}/"
    path = re.sub(r'/(browse|restaurant)/?$', '', u.path).rstrip('/')
    return f'{u.scheme}://{u.netloc}{path}/'


def shop_url(name):
    return f'{app_url()}restaurant?r={quote(name)}'


def is_dark():
    return st.context.theme.type == 'dark'  # 처음 열 때는 None일 수 있음 → 라이트로


def accent():
    # 차트·지도 강조색 (config.toml primaryColor와 같은 테라코타, 바꾸면 config·여기·wheel.py 세 곳)
    return '#C2502F' if is_dark() else '#9C4026'


# 8. 페이지 맨 위 탭 줄 (폰에선 Streamlit 메뉴가 숨으니까 본문에 직접 둠)
#    오른쪽 빈칸을 돌려줌: 투표 홈은 `with tabs_row():` 안에 QR 공유를 넣고, 둘러보기는 그냥 tabs_row()
def tabs_row():
    with st.container(horizontal=True, vertical_alignment='center', gap='xxsmall'):
        st.page_link('app_pages/vote.py', label='투표', icon=':material/how_to_vote:')
        st.page_link('app_pages/browse.py', label='둘러보기', icon=':material/storefront:')
        st.space('stretch')
        return st.container(width='content')


# 9. 셀프 체크: python common.py 로 실행 ('셀프 체크 통과'가 나오면 OK)
#    옆의 lunch_votes.db에 식당 표를 다시 씀 (표는 안 건드림), 'missing ScriptRunContext' 경고 1줄은 무시
#    영업 상태는 실제 시계로 낮 상태를 만들 수 없어서 이 체크가 유일한 확인 방법
if __name__ == '__main__':
    def t(hh, mm, day=0):  # 체크용 시각 (2026-11-02 = 월요일, day=5면 토요일)
        return datetime(2026, 11, 2 + day, hh, mm, tzinfo=KST)

    # 9-1. 영업 상태 (영업 전 / 영업 중 / 영업 끝 / 오늘 휴무 / 24:00 / 24시간 / 자정 넘김)
    assert open_status('11:00~21:30', None, t(10, 59)) == ('before', '영업 전 · 11:00 오픈')
    assert open_status('11:00~21:30', None, t(11, 0)) == ('open', '영업 중 · 21:30까지')
    assert open_status('11:00~21:30', None, t(21, 30)) == ('after', '오늘 영업 끝')
    assert open_status('11:00~21:30', '토,일', t(12, 0, day=5)) == ('closed', '오늘 휴무')  # 토요일
    assert open_status('11:00~24:00', None, t(23, 59)) == ('open', '영업 중 · 24:00까지')
    assert open_status('00:00~24:00', None, t(3, 0)) == ('open', '영업 중 · 24시간')
    assert open_status('12:00~02:00', None, t(1, 0)) == ('open', '영업 중 · 02:00까지')  # 자정 넘김
    assert open_status('12:00~02:00', None, t(3, 0)) == ('before', '영업 전 · 12:00 오픈')

    # 9-2. 걸어서 몇 분 (최소 1분), 가격대 (경계값은 아래 칸)
    assert walk_min(0) == 1 and walk_min(200) == 4 and walk_min(500) == 10
    assert price_band(10000) == '1만원 이하' and price_band(10001) == '1~2만원'
    assert price_band(20000) == '1~2만원' and price_band(20001) == '2만원 넘게'

    # 9-3. 1위 계산 (a가 b보다 가까운 식당): 표 많은 순, 같으면 가까운 순, 후보에 없는 식당은 빼고 인원만 셈
    a, b = shops.index[0], shops.index[1]
    ranked, total = ranking({b: ['민지', '준호'], a: ['익명'], '없는 식당': ['익명']})
    assert [n for n, _, _ in ranked] == [b, a] and total == 4
    assert leaders(ranked) == (2, [b])
    assert leaders(ranking({b: ['민지'], a: ['준호']})[0]) == (1, [a, b])  # 공동 1위
    assert leaders([]) == (0, [])

    # 9-4. 닉네임 줄 (Markdown 기호는 \ 를 붙여 글자 그대로, 익명은 숫자로)
    assert who_line(['민지', '익명', '익명']) == '민지 · 익명 2'
    assert who_line(['**a**', '익명'], md=False) == '**a** · 익명 1'  # 차트 툴팁용은 그대로
    assert plain('**굵게**') == r'\*\*굵게\*\*'
    assert plain('[링크](x)') == r'\[링크\]\(x\)'
    print('셀프 체크 통과')
