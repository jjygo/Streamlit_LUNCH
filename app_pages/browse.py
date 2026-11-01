import pandas as pd
import pydeck as pdk
import streamlit as st

from common import BASE, accent, badge_md, now_kst, open_status, price_band, shops, tabs_row, walk_min

st.set_page_config(page_title='식당 둘러보기', page_icon='🍚')

now = now_kst()
BANDS = ['전체', '1만원 이하', '1~2만원', '2만원 넘게']
SHORT_BADGE = {'open': '영업 중', 'after': '오늘 영업 끝', 'closed': '오늘 휴무'}  # 목록은 좁아서 짧게


def reset_filters():
    st.session_state.update(browse_cat='전체', browse_band='전체', browse_sort='거리순', browse_open=False)
    st.session_state.browse_resets = st.session_state.get('browse_resets', 0) + 1  # 종류 칩 새로 그리기 (아래 2번)


# 1. 맨 위: 탭 줄, 제목, 투표로 가는 링크
tabs_row()
st.title('식당 둘러보기', anchor=False)
st.caption(f'투표 후보 {len(shops)}곳 · 기준점에서 500m 안')
st.page_link('app_pages/vote.py', label='투표 현황 보기' if 'voted' in st.session_state else '투표하러 가기',
             icon=':material/chevron_right:', icon_position='right')

# 2. 필터·정렬 (위젯 key는 홈과 안 겹치게 browse_ 로 시작)
#    종류만 펼쳐 두고, 가격대·정렬·영업 중만은 '필터·정렬' 접기에 넣음 (폰 첫 화면에 식당이 보이게)
#    팝오버(st.popover)는 쓰지 않음: 안의 위젯이 처음 열 때 생겨서, 칩을 먼저 누르고 열면 값이 None으로 와 에러가 남
for key, value in {'browse_cat': '전체', 'browse_band': '전체', 'browse_sort': '거리순',
                   'browse_open': False, 'browse_view': '목록'}.items():
    st.session_state.setdefault(key, value)
counts = shops.category.value_counts()
# 종류 칩을 감싼 칸의 key를 '필터 초기화' 때마다 바꿔서 칩을 새로 그림
#   (코드가 칩 값을 바꾸면, 다음 첫 탭에 칩 줄이 예전 칩 쪽으로 밀려 탭이 빗나가는 Streamlit 문제가 있어서)
with st.container(key=f'browse_chips{st.session_state.get("browse_resets", 0)}'):
    cat = st.pills('종류', ['전체', *counts.index], key='browse_cat', required=True, wrap=False,
                   label_visibility='collapsed', format_func=lambda c: f'{c} {len(shops) if c == "전체" else counts[c]}')
with st.expander('필터·정렬', icon=':material/tune:'):
    band = st.pills('가격대', BANDS, key='browse_band', required=True)
    sort = st.segmented_control('정렬', ['거리순', '가격순', '평점순'], key='browse_sort', required=True,
                                width='stretch')
    st.caption('가격순은 싼 곳부터, 평점순은 높은 곳부터')
    open_only = st.toggle('지금 영업 중만', key='browse_open')

# 3. 걸러서 정렬
df = shops.copy()
df['walk'] = df.distance_m.map(walk_min)
df['state'] = [open_status(r.hours, r.closed, now)[0] for r in df.itertuples()]  # 'open', 'closed' 등
if cat != '전체':
    df = df[df.category == cat]
if band != '전체':
    df = df[df.price.map(price_band) == band]
if open_only:
    df = df[df.state == 'open']
if sort == '거리순':
    df = df.sort_values('distance_m')
elif sort == '가격순':
    df = df.sort_values(['price', 'distance_m'])
else:  # 평점순 (같으면 리뷰 많은 순)
    df = df.sort_values(['rating', 'rating_count'], ascending=False)

# 결과 개수 옆에 지금 걸린 정렬·필터를 적음 (접어 둬도 무엇이 걸렸는지 보이게), 같은 줄 오른쪽에 목록/지도
notes = [sort]
if band != '전체':
    notes.append(band)
if open_only:
    notes.append('지금 영업 중')
with st.container(horizontal=True, vertical_alignment='center', wrap=False):  # 글자가 길면 글자만 두 줄로
    st.markdown(f'**{len(shops)}곳 중 {len(df)}곳** :gray[· {" · ".join(notes)}]')
    st.space('stretch')
    view = st.segmented_control('보기', ['목록', '지도'], key='browse_view', required=True,
                                label_visibility='collapsed')

# 4. 결과: 빈 상태 / 목록 / 지도
if df.empty:
    with st.container(border=True):
        if open_only:
            st.markdown('**지금 문 연 식당이 없어요**')
            st.caption(f"{now:%H:%M} 기준이에요. '지금 영업 중만'을 끄면 전체가 보여요.")
        else:
            st.markdown('**조건에 맞는 식당이 없어요**')
            st.caption('필터를 하나씩 풀어 보세요.')
        st.button('필터 초기화', icon=':material/restart_alt:', on_click=reset_filters)
elif view == '목록':
    # 한 칸 전체가 '식당 정보'로 가는 링크 (같은 탭에서 열림), 홈 목록과 같은 모양:
    # 첫 줄 '이름 배지 ... 가격', 둘째 줄 회색 정보 (가격의 *기울임*은 app.py CSS (4)가 오른쪽 굵은 글씨로 바꿈)
    with st.container(key='list_browse', gap=None):
        for name, r in df.iterrows():
            text = SHORT_BADGE.get(r.state, f'{r.hours[:5]} 오픈')  # 영업 전이면 '11:30 오픈'
            #   = 줄바꿈 안 되는 빈칸 ('(리뷰' 와 '90개)'가 두 줄로 갈라지지 않게)
            st.page_link('app_pages/restaurant.py', query_params={'r': name}, width='stretch',
                         icon=':material/chevron_right:', icon_position='right',
                         label=f'**{name}** {badge_md(r.state, text)} *{r.price:,.0f}원*\n\n'
                               f':gray[{r.category} · {r.menu} · 걸어서 {r.walk}분 · '
                               f'★{r.rating} (리뷰 {r.rating_count:,}개)]')
else:
    # 지도: 점을 누르면 이름이 보임 (st.map은 이름을 못 보여줘서 pydeck)
    color = accent()
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]  # '#9C4026' → [156, 64, 38] (pydeck은 숫자 3개로 받음)
    points = df.reset_index()
    points['tip'] = [f'{r.menu} {r.price:,.0f}원 · 걸어서 {r.walk}분' for r in points.itertuples()]
    base = pd.DataFrame({'name': ['기준점(드림디포 서초남점)'], 'tip': [''], 'lat': [BASE[0]], 'lng': [BASE[1]]})
    dot = dict(get_position='[lng, lat]', get_radius=8, radius_min_pixels=7, stroked=True,
               get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True)
    st.pydeck_chart(pdk.Deck(
        map_style=None,  # None이면 라이트/다크 테마를 따라감
        initial_view_state=pdk.ViewState(latitude=BASE[0], longitude=BASE[1], zoom=15.4),
        layers=[pdk.Layer('ScatterplotLayer', id='base', data=base, get_fill_color=[148, 133, 118], **dot),
                pdk.Layer('ScatterplotLayer', id='shops', data=points, get_fill_color=rgb, **dot)],
        tooltip={'text': '{name}\n{tip}'}), height=420)
    st.caption('점을 누르면 식당 이름이 보여요 · 회색 점은 기준점(드림디포 서초남점)')

# 5. 각주
st.caption('가격은 대표 메뉴 기준이에요  \n영업 정보는 바뀔 수 있어요. 가기 전에 카카오맵에서 확인하세요.')
