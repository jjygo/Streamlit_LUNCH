import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title='식당 정보', page_icon='🍚')

BASE = (37.4866, 127.0205)  # 기준점: 드림디포 서초남점 (거리 계산 기준)


# 1. 식당 목록 (투표 후보와 같은 기준: 반경 500m, 가까운 순)
@st.cache_data
def load_restaurants():
    df = pd.read_csv(Path(__file__).parent.parent / 'restaurants.csv')
    return df[df.distance_m <= 500].sort_values('distance_m').set_index('name')


info = load_restaurants()


def show(v):
    return '정보 없음' if pd.isna(v) else v


# 2. 식당 고르기 (주소창 ?r=식당이름 과 연결돼서 링크로 공유 가능)
st.page_link('app.py', label='투표로 돌아가기', icon=':material/arrow_back:')
# (bind='query-params'는 st.switch_page 가 주소창을 못 비워서 에러 → 직접 읽고 씀)
names = info.index.tolist()
asked = st.query_params.get('r')
name = st.selectbox('식당', names, index=names.index(asked) if asked in names else 0,
                    label_visibility='collapsed')
st.query_params['r'] = name
r = info.loc[name]

# 3. 식당 정보
st.caption(f'{r.category} · ★ {r.rating} (리뷰 {r.rating_count:,.0f})')
st.title(name, anchor=False)

walk = max(1, round(r.distance_m * 1.3 / 67))  # ponytail: 직선거리 x1.3, 분당 67m 걷기로 어림, 정확히 하려면 길찾기 API
menu, dist = st.columns(2, wrap=False)
menu.metric(r.menu, f'{r.price:,.0f}원', border=True)
dist.metric(f'걸어서 · {r.distance_m}m', f'약 {walk}분', border=True)

rows = {'주소': r.address, '영업': r.hours, '휴무': r.closed, '메모': r.note}
st.markdown('  \n'.join(f':gray[{k}]&emsp;{show(v)}' for k, v in rows.items()))

# 4. 지도 (회색: 기준점, 진한 점: 식당)
accent = '#C2502F' if st.context.theme.type == 'dark' else '#9C4026'
st.map(pd.DataFrame({'lat': [BASE[0], r.lat], 'lon': [BASE[1], r.lng],
                     'color': ['#948576', accent], 'size': [12, 18]}),  # size 단위는 미터
       latitude='lat', longitude='lon', color='color', size='size', zoom=16, height=280)
st.caption('회색 점은 기준점(드림디포 서초남점)이에요')

# 5. 이 식당 고르기 (투표 화면으로 돌아가서 이 식당이 선택된 상태로 열림)
pick, kakao = st.columns(2)
if 'voted' in st.session_state:
    pick.button(f'오늘은 「{st.session_state.voted}」에 투표했어요', disabled=True, width='stretch')
elif pick.button('이 식당 고르기', type='primary', width='stretch'):
    st.session_state.pick = name
    st.switch_page('app.py')
kakao.link_button('카카오맵', r.kakao_url, icon=':material/open_in_new:', width='stretch')
