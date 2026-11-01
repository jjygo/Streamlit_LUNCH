import pandas as pd
import qrcode
import streamlit as st

from common import (BADGE, BASE, DAYS, accent, closed_today, nearby, now_kst, open_status, shop_url, shops,
                    short, today_votes, walk_min, who_line)

now = now_kst()
name = st.query_params.get('r')  # 주소창 ?r=식당이름 (옛 링크·QR도 그대로 열림)

# 1. 식당이 없으면 빈 상태 (첫 식당을 대신 보여주지 않음)
if name not in shops.index:
    st.set_page_config(page_title='식당 정보 · 점심 투표', page_icon='🍚')
    st.page_link('app_pages/vote.py', label='투표로 돌아가기', icon=':material/arrow_back:')
    st.title('식당을 찾을 수 없어요', anchor=False)
    st.write('링크가 잘못됐거나 투표 후보에서 빠진 식당이에요.')
    st.page_link('app_pages/browse.py', label='식당 둘러보기', icon=':material/storefront:')
    st.stop()

st.set_page_config(page_title=f'{short(name)} · 점심 투표', page_icon='🍚')
st.query_params['r'] = name  # 근처 추천으로 옮겨 와도 주소창을 이 식당으로 맞춤 (새로 고침·공유가 맞게)
# 근처 추천은 같은 페이지 안 이동이라 Streamlit이 스크롤을 그대로 둠 → 맨 위로 올림
#   (스크립트 글자에 식당 이름을 넣어야 식당이 바뀔 때마다 다시 돎. 같은 식당에서 버튼을 눌러도 안 튐)
st.html(f'<script>/* {name} */ document.querySelector("[data-testid=stMain]").scrollTo(0, 0)</script>',
        unsafe_allow_javascript=True)
r = shops.loc[name]
state, status = open_status(r.hours, r.closed, now)
who = today_votes().get(name, [])

# 2. 맨 위: 돌아가기, 종류·별점, 이름, 영업 배지 + 오늘 표
st.page_link('app_pages/vote.py', label='투표로 돌아가기', icon=':material/arrow_back:')
st.caption(f'{r.category} · ★ {r.rating} (리뷰 {r.rating_count:,}개)')
st.title(name, anchor=False)
with st.container(horizontal=True, gap='xsmall'):
    st.badge(status, color=BADGE[state][0], icon=BADGE[state][1])
    st.badge(f'오늘 {len(who)}표' if who else '아직 표가 없어요', color='blue' if who else 'gray',
             icon=':material/how_to_vote:')
if who:  # 닉네임은 who_line()이 Markdown 기호를 풀어서 글자 그대로 보여 줌 (링크·굵게 안 됨)
    st.caption('투표한 사람: ' + who_line(who))

# 3. 대표 메뉴 · 걸어서 몇 분 (좁은 폰에선 자동으로 위아래로)
with st.container(horizontal=True, gap='large'):
    st.metric(r.menu, f'{r.price:,.0f}원', width='content')
    st.metric(f'걸어서 · {r.distance_m}m', f'약 {walk_min(r.distance_m)}분', width='content')

# 4. 카카오맵 · 공유
with st.container(horizontal=True):
    st.link_button('카카오맵에서 보기', r.kakao_url, icon=':material/map:', width='stretch')
    with st.popover('공유', icon=':material/share:', width='stretch'):
        link = shop_url(name)
        st.caption('이 링크를 보내면 이 식당 정보가 바로 열려요')
        st.code(link, language=None)
        st.image(qrcode.make(link).get_image(), width=200, alt='이 식당 링크 QR 코드')
        st.caption('휴대폰 카메라로 찍어도 열려요')

# 5. 영업 정보 (값이 없는 줄은 숨김)
st.header('영업 정보', anchor=False)
info = {'영업시간': r.hours, '주소': r.address, '메모': r.note, '휴무': '휴무일 없음'}
if isinstance(r.closed, str):  # '토,일' → '매주 토·일요일', 오늘이 쉬는 날이면 '(오늘 일요일 휴무)'를 붙임
    info['휴무'] = '매주 ' + '·'.join(r.closed.split(',')) + '요일'
    if closed_today(r.closed, now):
        info['휴무'] += f' (오늘 {DAYS[now.weekday()]}요일 휴무)'
for label in ['영업시간', '휴무', '주소', '메모']:
    if isinstance(info[label], str):
        with st.container(horizontal=True, gap='small'):
            st.markdown(f':gray[{label}]', width=72)
            st.markdown(info[label])

# 6. 지도 (회색: 기준점, 테라코타 점: 식당)
st.map(pd.DataFrame({'lat': [BASE[0], r.lat], 'lon': [BASE[1], r.lng],
                     'color': ['#948576', accent()], 'size': [10, 16]}),  # size 단위는 미터
       latitude='lat', longitude='lon', color='color', size='size', zoom=16, height=260)
st.caption('회색 점은 기준점(드림디포 서초남점)이에요')

# 7. 근처 같은 종류 3곳 (없으면 종류 상관없이 가까운 곳)
near, same_kind = nearby(name)
st.header(f'근처 {r.category} 더 보기' if same_kind else '근처 다른 식당', anchor=False)
if not same_kind:
    st.caption('같은 종류는 여기뿐이라 가까운 곳을 골랐어요')
with st.container(key='list_near', gap=None):
    for n, mins in near:
        o = shops.loc[n]
        tail = ' · 오늘 휴무' if closed_today(o.closed, now) else ''
        st.page_link('app_pages/restaurant.py', query_params={'r': n}, width='stretch',
                     icon=':material/chevron_right:', icon_position='right',
                     label=f'**{short(n)}**\n\n:gray[여기서 걸어서 {mins}분 · {o.menu} {o.price:,.0f}원 · ★{o.rating}{tail}]')

st.page_link('app_pages/browse.py', label='다른 식당 둘러보기', icon=':material/storefront:')
st.caption('영업 정보는 바뀔 수 있어요. 가기 전에 카카오맵에서 확인하세요.')

# 8. 아래 고정 버튼: 이 식당 고르기 → 투표 화면 (이 식당이 골라진 상태로)
voted = st.session_state.get('voted')
with st.bottom:
    if voted == name:
        st.button('여기에 투표했어요', icon=':material/check:', disabled=True, width='stretch')
    elif st.button('이 식당으로 바꾸기' if voted else '이 식당 고르기', type='primary', width='stretch'):
        st.session_state.update(pick=name, cat='전체', editing=bool(voted), toast=f'「{short(name)}」 골라 뒀어요')
        st.switch_page('app_pages/vote.py')
