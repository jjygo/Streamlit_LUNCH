import random

import altair as alt
import pandas as pd
import qrcode
import streamlit as st

from common import (DAYS, accent, app_url, closed_today, is_dark, leaders, now_kst, ranking, save_vote, shops,
                    short, tabs_row, today_votes, walk_min, who_line)
from wheel import wheel_html

# 홈만 넓은 화면(wide): 데스크톱에서 왼쪽 투표 · 오른쪽 현황 2열로 보려고 (폰에선 그냥 1열로 쌓임)
st.set_page_config(page_title='오늘 점심 투표', page_icon='🍚', layout='wide')

# 1. 지금 상태 (투표 전 / 투표 후 / 바꾸는 중)
now = now_kst()
voted = st.session_state.get('voted')
editing = st.session_state.get('editing', False)
voting = voted is None or editing
if msg := st.session_state.pop('toast', None):  # 투표·바꾸기 직후, 또는 식당 정보에서 '이 식당 고르기'로 왔을 때
    st.toast(msg, icon=':material/check_circle:')


# 투표 확인 창 (닉네임은 여기서 한 번만 받음, 오늘 휴무면 알려 줌). 아래 투표 버튼과 돌림판 둘 다 이 창을 씀
@st.dialog('투표하기', icon=':material/how_to_vote:')
def confirm_vote(name):
    r = shops.loc[name]
    st.markdown(f'**{name}**  \n:gray[{r.menu} {r.price:,.0f}원 · 걸어서 {walk_min(r.distance_m)}분]')
    if closed_today(r.closed, now_kst()):
        st.markdown(':red[:material/event_busy: 오늘 휴무인 식당이에요. 그래도 투표할 수 있어요.]')
    nickname = st.text_input('닉네임 (선택)', max_chars=20, placeholder='비우면 익명')
    if st.button(f'「{short(name)}」에 투표하기', type='primary', width='stretch'):
        save_vote(name, nickname)  # DB 쓰기는 common.py save_vote() 한 곳
        st.rerun()


def row(n):
    # 식당 목록 한 칸: 첫 줄 '이름 ... 가격', 둘째 줄 회색 '메뉴 · 걸어서 N분 · 별점'
    # 가격의 *기울임*은 표시용 신호: app.py CSS (4)가 기울임(em)을 오른쪽 끝 굵은 글씨로 바꿈
    r = shops.loc[n]
    return (f'**{short(n)}** *{r.price:,.0f}원*\n\n'
            f':gray[{r.menu} · 걸어서 {walk_min(r.distance_m)}분 · ★{r.rating}]')


def keep_one(other):
    # 위 목록과 '오늘 휴무' 목록 중 한 곳만 골라지게: 한쪽에서 고르면 다른 쪽 선택은 풀기
    st.session_state[other] = None


def vote_chart(ranked, top):
    # 가로 막대: 표 받은 곳만. 내 표 = 테라코타 + '내 표' 글자, 1위 = 진한 갈색 회색, 나머지 = 갈색 회색
    mine = st.session_state.get('voted')
    if is_dark():
        top_color, other_color, ink = '#C9BEB2', '#857A6E', '#F2ECE3'
    else:
        top_color, other_color, ink = '#5A5047', '#948576', '#16120F'
    rows = []
    for n, c, who in ranked:
        if n == mine:
            color = accent()
        elif n in top:
            color = top_color
        else:
            color = other_color
        closed = ' · 휴무' if closed_today(shops.at[n, 'closed'], now_kst()) else ''
        rows.append({'name': short(n) + closed, 'votes': c, 'color': color, 'who': who_line(who, md=False),
                     'label': f'{c}표 · 내 표' if n == mine else f'{c}표'})
    df = pd.DataFrame(rows)
    base = alt.Chart(df).encode(y=alt.Y('name:N', sort=None, title=None, axis=alt.Axis(
        ticks=False, domain=False, labelPadding=10, labelFontSize=15, labelLimit=150, labelColor=ink)))
    bars = base.mark_bar(size=20, cornerRadiusEnd=4).encode(
        x=alt.X('votes:Q', axis=None, scale=alt.Scale(domain=[0, ranked[0][1] * 1.5])),
        color=alt.Color('color:N', scale=None),  # 위에서 정한 색을 그대로 씀
        tooltip=[alt.Tooltip('name:N', title='식당'), alt.Tooltip('votes:Q', title='표'),
                 alt.Tooltip('who:N', title='투표한 사람')])
    labels = base.mark_text(align='left', dx=8, fontSize=14, fontWeight=600, color=ink).encode(
        x='votes:Q', text='label:N')
    st.altair_chart((bars + labels).properties(height=len(df) * 40), width='stretch',
                    alt='실시간 현황: ' + ', '.join(f'{short(n)} {c}표' for n, c, _ in ranked))


# 2. 맨 위: 탭 줄 + QR 공유, 제목 + 날짜
with tabs_row():
    with st.popover('QR 공유', icon=':material/qr_code_2:', type='tertiary'):
        url = app_url()
        if '//127.0.0.1' in url:
            st.warning('내 컴퓨터 주소를 못 찾았어요. 와이파이나 VPN 연결을 확인해 주세요.')
        st.image(qrcode.make(url).get_image(), width=220, alt='앱 주소 QR 코드')
        st.caption('휴대폰 카메라로 찍으면 바로 열려요')
        st.code(url, language=None)
with st.container(horizontal=True, vertical_alignment='center'):
    st.title('점심 뭐 먹지?', anchor=False, width='content')
    st.caption(f'{now.month}월 {now.day}일 ({DAYS[now.weekday()]})', width='content')


# 3. 한 줄 요약 (투표 전에도 지금 누가 이기는지 첫 화면에서 보이게, 2초마다)
@st.fragment(run_every='2s')
def live_line():
    ranked, total = ranking(today_votes())
    k, top = leaders(ranked)
    if not top:
        st.markdown(':gray[아직 표가 없어요]')
        return
    if len(top) == 1:
        first = f'1위 **{short(top[0])}** {k}표'
        if closed_today(shops.at[top[0], 'closed'], now_kst()):
            first += ' :red-badge[오늘 휴무]'
    else:
        first = f'공동 1위 {len(top)}곳 · {k}표'  # 이름은 아래 현황에서 보여 줌 (한 줄이 넘치지 않게)
    st.markdown(f':blue-badge[:material/bolt: 실시간] **{total}명** 참여 · {first}')


# 4. 실시간 현황 (2초마다 이 부분만 다시 그림)
@st.fragment(run_every='2s')
def live():
    ranked, total = ranking(today_votes())
    k, top = leaders(ranked)
    top_closed = len(top) == 1 and closed_today(shops.at[top[0], 'closed'], now_kst())
    with st.container(horizontal=True, vertical_alignment='bottom'):
        st.header('실시간 현황', anchor=False)
        st.space('stretch')
        st.caption('2초마다 새로 고쳐요', width='content')
    with st.container(horizontal=True, gap='medium'):
        st.metric('참여', f'{total}명', width='content')
        if not top:
            st.metric('1위', '아직 없음')
        elif top_closed:
            st.metric(f'1위 · {k}표 · 오늘 휴무', short(top[0]))
        elif len(top) == 1:
            st.metric(f'1위 · {k}표', short(top[0]))
        else:
            st.metric(f'공동 1위 · {k}표', f'{len(top)}곳')

    if top_closed:  # 경고는 큰 이름 바로 아래 (자세히 보기 링크보다 먼저 읽히게)
        st.markdown(':red[:material/event_busy: 1위 식당이 오늘 휴무예요. 다른 곳도 살펴보세요.]')
    if len(top) == 1:
        st.page_link('app_pages/restaurant.py', label=f'「{short(top[0])}」 자세히 보기',
                     icon=':material/chevron_right:', icon_position='right', query_params={'r': top[0]})
    elif top:  # 공동 1위: 이름마다 자세히 보기 링크 (3곳까지)
        with st.container(horizontal=True, gap='xsmall'):
            for n in top[:3]:
                st.page_link('app_pages/restaurant.py', label=f'**{short(n)}**', icon=':material/chevron_right:',
                             icon_position='right', query_params={'r': n})
            if len(top) > 3:
                st.caption(' · '.join(short(n) for n in top[3:]))

    if not ranked:
        st.info('아직 표가 없어요. 첫 표를 던져 보세요!', icon=':material/how_to_vote:')
        return
    vote_chart(ranked, top)
    if not voting:  # 막대 아래 누가 골랐는지 (폰에선 차트 툴팁이 안 보여서). 투표 전 홈은 짧게 두려고 투표 뒤에만
        lines = [f'**{short(n)}** {who_line(who)}' for n, _, who in ranked]
        st.caption('  \n'.join(['투표한 사람', *lines]))
    if len(shops) > len(ranked):
        st.caption(f'나머지 {len(shops) - len(ranked)}곳은 아직 0표예요')


# 5. 화면 배치 (넓은 화면은 왼쪽 투표 · 오른쪽 현황, 폰은 위아래로 쌓임)
if voting:
    live_line()
left, right = st.columns([3, 2], gap='medium')

if not voting:
    # 5-1. 투표 후: 완료 배너 + 바꾸기, 그 아래 바로 현황
    with left:
        with st.container(border=True, horizontal=True, vertical_alignment='center', wrap=False):
            st.markdown(':blue[:material/check_circle:]', width='content')  # 아이콘을 따로 둬서 글자가 두 줄이어도 줄이 맞음
            st.markdown(f'**{voted}**에 투표했어요')
            if st.button('바꾸기'):
                st.session_state.update(editing=True, pick=voted, cat='전체')
                st.rerun()
    with right:
        live()
        st.page_link('app_pages/browse.py', label='식당 둘러보기', icon=':material/storefront:')
    # 목록을 내려서 고르고 투표해도 완료 배너가 보이게 맨 위로 (Streamlit은 다시 그려도 스크롤 위치를 그대로 둠)
    st.html('<script>document.querySelector("[data-testid=stMain]").scrollTo(0, 0)</script>',
            unsafe_allow_javascript=True)
    st.stop()

with left:
    # 5-2. 돌림판 (오늘 휴무는 빼고 돌림, 뽑힌 식당은 아래 목록에 미리 골라 둠)
    open_names = [n for n in shops.index if not closed_today(shops.at[n, 'closed'], now)] or list(shops.index)
    with st.expander('못 고르겠으면 돌림판', icon=':material/casino:'):
        if len(open_names) < len(shops):
            st.caption(f'오늘 쉬는 {len(shops) - len(open_names)}곳은 빼고 돌려요')
        if st.button('돌리기', icon=':material/refresh:', width='stretch'):
            k = random.randrange(len(open_names))
            seg = 360 / len(open_names)
            # 바늘이 6바퀴 돌고 k번째 칸 안에서 멈춤 (칸 가운데는 이름 글자라서 1/4쯤 비껴 멈춤)
            turn = 360 * 6 + (k + random.choice([.25, .75]) + random.uniform(-.05, .05)) * seg
            st.session_state.pick = open_names[k]
            st.session_state.cat = '전체'  # 뽑힌 식당이 종류 필터에 가려지지 않게
            st.session_state.wheel = (st.session_state.get('wheel', (0,))[0] + 1, k, turn)
        spin, k, turn = st.session_state.get('wheel', (0, 0, 0))
        if k >= len(open_names):  # 자정이 지나 오늘 휴무가 바뀌면 지난 결과는 버림
            spin, k, turn = 0, 0, 0
        st.iframe(wheel_html([short(n) for n in open_names], spin, k, turn, is_dark()), height=310, alt='돌림판')
        # 돌린 뒤엔 결과로 바로 투표 (아래 투표 버튼과 같은 확인 창). 바꾸는 중이면 아래 '이걸로 바꾸기'를 씀
        #   버튼에 당첨 이름을 넣음: 돌린 뒤 목록에서 다른 곳을 골라도 이 버튼이 어디에 투표하는지 보이게
        if spin and not editing:
            if st.button(f'「{short(open_names[k])}」에 투표하기', icon=':material/how_to_vote:', width='stretch'):
                confirm_vote(open_names[k])

    # 5-3. 식당 고르기: 종류 칩 + 목록 (가까운 순, 오늘 휴무는 맨 아래 '오늘 휴무 N곳' 접기 안에)
    #      소제목은 따로 안 둠 (제목 '점심 뭐 먹지?'와 같은 뜻이라 폰에서 한 줄 아끼기)
    if editing:
        st.info(f'지금 내 표: **{voted}**  \n다른 곳을 고르고 바꾸기를 누르세요', icon=':material/edit:')
    else:
        st.caption('한 사람 한 표 · 투표한 뒤에도 바꿀 수 있어요')
    counts = shops.category.value_counts()
    st.session_state.setdefault('cat', '전체')
    # 칩을 감싼 칸의 key에 돌린 횟수(spin)를 붙여, 돌림판이 칩을 '전체'로 바꿀 때마다 칩을 새로 그림
    #   (값만 바꾸면 다음 첫 탭이 빗나가는 Streamlit 문제, 둘러보기 '필터 초기화'도 같은 방법)
    with st.container(key=f'chips{spin}'):
        cat = st.pills('종류', ['전체', *counts.index], key='cat', required=True, label_visibility='collapsed',
                       format_func=lambda c: f'{c} {len(shops) if c == "전체" else counts[c]}', wrap=False)
    shown = [n for n in shops.index if cat == '전체' or shops.at[n, 'category'] == cat]
    closed = [n for n in shown if closed_today(shops.at[n, 'closed'], now)]
    opened = [n for n in shown if n not in closed]
    # 돌림판·식당 정보·바꾸기가 넘겨준 식당(pick)을 목록 선택으로 옮김
    # 위 목록은 choice, 휴무 목록은 choice_closed (둘 중 하나만 값이 있음)
    if 'pick' in st.session_state:
        pick = st.session_state.pop('pick')
        st.session_state.choice = None if pick in closed else pick
        st.session_state.choice_closed = pick if pick in closed else None
    if st.session_state.get('choice') not in opened:  # 종류 칩에 가려진 식당은 고른 것 풀기
        st.session_state.choice = None
    if st.session_state.get('choice_closed') not in closed:
        st.session_state.choice_closed = None
    with st.container(key='shoplist'):
        if opened:
            # persist_state='session': 식당 정보에 다녀와도 고른 식당이 그대로 남음
            st.radio('식당 고르기', opened, index=None, key='choice', persist_state='session',
                     on_change=keep_one, args=('choice_closed',),
                     format_func=row, label_visibility='collapsed', width='stretch')
        else:  # 고른 종류가 오늘 전부 휴무면 빈 라디오(영어 문구) 대신 안내하고 휴무 목록을 펼침
            st.caption('오늘 문 연 곳이 없어요. 아래 휴무 식당에도 투표할 수 있어요')
        if closed:  # 휴무 식당도 투표는 됨 (데이터가 틀릴 수 있어서), 고른 게 여기 있으면 펼쳐 둠
            with st.expander(f'오늘 휴무 {len(closed)}곳', icon=':material/event_busy:',
                             expanded=st.session_state.choice_closed is not None or not opened):
                st.radio('오늘 휴무 식당', closed, index=None, key='choice_closed', persist_state='session',
                         on_change=keep_one, args=('choice',),
                         format_func=row, label_visibility='collapsed', width='stretch')
    choice = st.session_state.choice or st.session_state.choice_closed
    with st.container(horizontal=True, vertical_alignment='center', gap='xsmall'):
        st.page_link('app_pages/browse.py', label='식당 둘러보기', icon=':material/storefront:')
        st.caption('가격·평점·지도로 비교해요')

with right:
    live()

# 6. 아래 고정 바: 고른 식당 이름이 들어간 투표 버튼 (목록 어디서 골라도 스크롤 없이 바로 누름)
#    key='votebar': 넓은 화면에서 바 폭을 왼쪽 열에 맞추는 app.py CSS (5)가 찾는 이름
with st.bottom:
    with st.container(key='votebar', gap='xsmall'):  # 링크와 버튼 사이를 좁혀서 고정 바가 목록을 덜 가리게
        if choice:
            st.page_link('app_pages/restaurant.py', label=f'「{short(choice)}」 자세히 보기',
                         icon=':material/info:', query_params={'r': choice})
        if editing:
            with st.container(horizontal=True):
                if st.button('그대로 두기', width='stretch'):
                    st.session_state.editing = False
                    st.rerun()
                if st.button('이걸로 바꾸기', type='primary', width='stretch', disabled=not choice):
                    save_vote(choice)  # 바꾸는 중이라 내 표 1개만 고침 (새로 한 표 더 넣지 않음)
                    st.rerun()
        elif st.button(f'「{short(choice)}」에 투표하기' if choice else '식당을 골라주세요',
                       type='primary', width='stretch', disabled=not choice):
            confirm_vote(choice)
