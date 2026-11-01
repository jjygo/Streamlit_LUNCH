import streamlit as st

# 1. 페이지 3개 (식당 정보는 메뉴에 안 보이고 링크로만 열림, 옛 주소 restaurant?r=이름 그대로)
#    폴더 이름이 pages/면 서버를 막 켰을 때 주소로 바로 들어온 사람에게 이 파일(꾸미기)을 건너뛰고
#    페이지만 뜸 (Streamlit 옛 방식 자동 메뉴) → 그래서 app_pages/
pages = [
    st.Page('app_pages/vote.py', title='투표', icon=':material/how_to_vote:', default=True),
    st.Page('app_pages/browse.py', title='둘러보기', icon=':material/storefront:', url_path='browse'),
    st.Page('app_pages/restaurant.py', title='식당 정보', icon=':material/restaurant:',
            url_path='restaurant', visibility='hidden'),
]

# 2. 꾸미기: 색·글꼴·크기는 .streamlit/config.toml, 여기는 기본 기능으로 안 되는 것만
#    Streamlit 1.66 내부 구조(data-testid, 클래스 이름)에 기대므로 버전을 requirements.txt에 고정(1.66.1),
#    올릴 때는 그 숫자만 바꾸고 화면을 한 번 확인할 것
st.html('''<style>
/* (1) 누르는 곳은 높이 44px 이상 (버튼·칩·링크·접기 제목·토글·확인 창). 지도·차트의 작은 도구 버튼은 그대로 */
:is(.stButton, .stPopover, .stLinkButton, .stButtonGroup, .stPageLink) :is(button, a),
.stExpander summary, .stCheckbox label, [role="dialog"] button, [data-testid="stTextInputRootElement"] { min-height: 2.75rem; align-items: center; }
[role="dialog"] button[aria-label="Close"] { min-width: 2.75rem; }
/* 한국어는 낱말 단위로 줄바꿈 · 입력칸 글자는 1rem(17px): 16px보다 작으면 아이폰이 화면을 확대함 */
[data-testid="stMain"] :is(p, h1, h2), :is([role="dialog"], [data-testid="stToast"]) p { word-break: keep-all; }
[data-testid="stTextInputField"] { font-size: 1rem; }
/* (2) 키보드로 온 곳에 본문색 테두리 (Streamlit 기본 링은 연해서 배경과 3:1이 안 됨)
       링크는 바깥쪽: a 자체 색은 브라우저 파랑이라 color: inherit로 본문색 (보이는 글자색은 안쪽 span이라 그대로)
       버튼·접기 제목은 안쪽: 주 버튼 안에선 흰 테두리, 나머지는 본문색 */
:is([data-testid="stMain"], [data-testid="stBottom"]) a:focus-visible { color: inherit; outline: 2px solid currentColor; outline-offset: 2px; }
:is([data-testid="stMain"], [data-testid="stBottom"], [role="dialog"]) :is(button, summary):focus-visible { outline: 2px solid currentColor; outline-offset: -4px; }
/*     아래 고정 바가 키보드로 온 곳을 가리지 않게 (그만큼 띄워서 스크롤), 차트 도구는 키보드로 오면 보이게 */
[data-testid="stMain"] { scroll-padding-bottom: 9rem; }
[data-testid="stElementToolbar"]:focus-within { opacity: 1; }
/* (3) 고른 칩: 글자 본문색 + 굵게 (색만으로 구분하지 않게, 다크 테라코타 글자는 대비가 모자라서 본문색)
       [role="radiogroup"]을 붙여야 Streamlit 자체 칩 색 규칙보다 우선순위가 높아짐 (빼면 다크에서 조용히 테라코타 글자로 돌아감)
       마우스를 올리거나 키보드로 왔을 때 · 팝오버(QR 공유·공유)가 열렸을 때도 같은 이유로 본문색 */
.stButtonGroup [role="radiogroup"] button[aria-checked="true"],
.stButtonGroup [role="radiogroup"] button[aria-checked="true"]:is(:hover, :focus-visible),
.stPopover button:is(:hover, :focus-visible, [aria-expanded="true"]) { color: inherit; }
.stButtonGroup button[aria-checked="true"] p { font-weight: 700; }
/* (4) 식당 목록 세 곳 (홈 라디오 shoplist · 둘러보기 list_browse · 근처 추천 list_near) 같은 모양:
       첫 줄 '굵은 이름 ... 가격', 둘째 줄 회색 정보, 칸 사이 얇은 선, 칸 전체가 누르는 곳 */
.st-key-shoplist [role="radiogroup"] { align-items: stretch; gap: 0; }
.st-key-shoplist [data-testid="stRadioOption"] { padding: .4rem .5rem; border-bottom: 1px solid rgba(128, 128, 128, .2); }
.st-key-shoplist [data-testid="stRadioOption"]:has(input:checked) { background: rgba(194, 80, 47, .14); border-radius: .75rem; border-bottom-color: transparent; }
.st-key-shoplist [data-testid="stRadioOption"] > div, .st-key-shoplist [data-testid="stMarkdownContainer"] { flex: 1; }
:is(.st-key-list_browse, .st-key-list_near) a { padding: .7rem 0; background: none; border-bottom: 1px solid rgba(128, 128, 128, .2); border-radius: 0; }
:is(.st-key-list_browse, .st-key-list_near) a > span:first-child { flex: 1; }
:is(.st-key-list_browse, .st-key-list_near) a :is(span, p) { white-space: normal; font-weight: 400; }
:is(.st-key-list_browse, .st-key-list_near) [data-testid="stElementContainer"] { margin: 0; }  /* 아래 칸이 위 칸을 덮지 않게 */
:is(.st-key-shoplist, .st-key-list_browse, .st-key-list_near) p:first-child { display: flex; flex-wrap: wrap; align-items: center; gap: .375rem; font-size: 1rem; }
:is(.st-key-shoplist, .st-key-list_browse, .st-key-list_near) p { line-height: 1.4; }
:is(.st-key-shoplist, .st-key-list_browse, .st-key-list_near) strong { font-weight: 700; }
/* 가격: vote.py row()와 browse.py가 *기울임*으로 씀 → 기울임 없이 오른쪽 끝 굵은 글씨, 숫자 폭을 같게 (자릿수가 줄 맞게) */
:is(.st-key-shoplist, .st-key-list_browse) em { margin-left: auto; font-style: normal; font-weight: 700; font-variant-numeric: tabular-nums; }
/* (5) 아래 고정 바: 여백 줄이기, 넓은 화면에선 가운데 46rem까지만, 위에 얇은 선 */
[data-testid="stBottomBlockContainer"] { padding-top: .75rem; padding-bottom: 1rem; max-width: 46rem; }
[data-testid="stBottom"] > div { border-top: 1px solid rgba(128, 128, 128, .2); }
/*     투표 홈(vote.py key='votebar')은 640px보다 넓으면 2열이라, 바를 왼쪽 투표 열과 같은 자리·폭으로
       (Streamlit은 640px까지 열을 위아래로 쌓음 · st.columns([3, 2])의 왼쪽 열 = 60% - 간격 절반 1rem) */
@media (min-width: 641px) {
  [data-testid="stBottomBlockContainer"]:has(.st-key-votebar) { max-width: none; }
  .st-key-votebar { max-width: calc(60% - 1rem); }
}
/* 주 버튼 글자는 굵게, 비활성 버튼은 회색 면 + 본문색 글자 ('식당을 골라주세요' 안내가 잘 읽히게) */
[data-testid="stBaseButton-primary"] p { font-weight: 600; }
[data-testid="stBottom"] button:disabled { color: inherit; background: rgba(128, 128, 128, .12); border-color: transparent; }
/* (6) 스크립트만 든 st.html (아래 3번 lang · vote.py 투표 뒤 맨 위로 · restaurant.py 근처 추천 뒤 맨 위로)은 빈칸·간격을 차지하지 않게 (숨겨도 스크립트는 돎) */
[data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > script:only-child) { display: none; }
</style>''')

# 3. 화면 언어를 한국어로 (Streamlit 기본은 영어 'en' → 화면 읽기 프로그램이 영어 발음 규칙으로 읽음)
st.html('<script>document.documentElement.lang = "ko"</script>', unsafe_allow_javascript=True)

st.navigation(pages, position='hidden').run()
