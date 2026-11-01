# 돌림판 그림(HTML + SVG)을 만드는 함수 하나 (투표 홈에서 st.iframe으로 띄움)
import html
import json
import math

# 1. 돌림판 모양과 움직임 (돌림판은 iframe = 바깥 꾸미기가 안 들어가는 따로 된 문서라 여기 따로 둠)
#    보통 문자열이라 CSS·JS 중괄호를 한 겹 그대로 씀. 글자·바늘은 currentColor(= body 글자색)
FONT = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9'
        '/dist/web/static/pretendard-dynamic-subset.min.css">')
WHEEL_CSS = '''
body { margin: 0; font-family: Pretendard, sans-serif; text-align: center; }
svg { display: block; width: 260px; height: 260px; margin: 8px auto 0; }
#needle { transition: transform 4s cubic-bezier(.15, .85, .1, 1); }
text { font-size: 13px; font-weight: 600; dominant-baseline: middle; }
#msg { margin-top: 12px; font-size: 15px; font-weight: 600; }
@media (prefers-reduced-motion: reduce) { #needle { transition: none; } }
'''
# AFTER(결과 문구) · TARGET(당첨 칸 번호) · TURN(멈출 각도) · WIN(당첨 칸 색)은 wheel_html이 이 코드 앞에 붙여 줌
WHEEL_JS = '''
const needle = document.getElementById('needle'), msg = document.getElementById('msg');
function done() {
  msg.textContent = AFTER;
  document.getElementById('p' + TARGET).setAttribute('fill', WIN);  // 당첨 칸만 진하게
  document.getElementById('t' + TARGET).setAttribute('fill', '#FFFFFF');
}
requestAnimationFrame(() => requestAnimationFrame(() => needle.style.transform = 'rotate(' + TURN + 'deg)'));
needle.addEventListener('transitionend', done);
if (matchMedia('(prefers-reduced-motion: reduce)').matches) done();
'''


# 2. 돌림판 HTML 만들기 (식당마다 부채꼴 칸 1개 + 이름)
def wheel_html(names, spin, target, turn, dark):
    # 판은 그대로 두고 바늘만 돌림 (판이 안 돌아서 글자가 빙글빙글 돌지 않음)
    # 결과는 파이썬에서 미리 뽑고, 화면은 바늘을 그 칸에 멈추게 돌리기만 함
    # 당첨 칸 색은 config.toml primaryColor와 같은 테라코타 (흰 글자 대비 라이트 6.6:1 · 다크 4.7:1)
    if dark:
        ink, a, b, win = '#F2ECE3', '#2A2622', '#36302A', '#C2502F'
    else:
        ink, a, b, win = '#16120F', '#F2EBDF', '#E6DCCB', '#9C4026'
    n, R, seg = len(names), 128, 360 / len(names)
    slices = ''
    for i, name in enumerate(names):
        a0, a1, mid = math.radians(i * seg), math.radians((i + 1) * seg), (i + .5) * seg
        label = html.escape(name if len(name) <= 8 else name[:7] + '…')
        # 오른쪽 절반은 바깥쪽으로, 왼쪽 절반은 안쪽으로 써서 글자가 뒤집히지 않게
        if mid <= 180:
            turn_text, anchor = '-90', 'end'
        else:
            turn_text, anchor = '90', 'start'
        slices += (f'<path id="p{i}" d="M0 0L{R * math.sin(a0):.1f} {-R * math.cos(a0):.1f}'
                   f'A{R} {R} 0 0 1 {R * math.sin(a1):.1f} {-R * math.cos(a1):.1f}Z" fill="{(a, b)[i % 2]}"/>'
                   f'<text id="t{i}" transform="rotate({mid:.1f}) translate(0 -{R - 10}) rotate({turn_text})" '
                   f'text-anchor="{anchor}" fill="currentColor">{label}</text>')
    svg = (f'<svg viewBox="-130 -130 260 260" role="img" aria-label="돌림판">{slices}'
           f'<g id="needle"><path d="M0 -{R - 34}L5 0L-5 0Z" fill="currentColor"/></g>'
           '<circle r="13" fill="currentColor"/></svg>')
    before = f'돌리기를 누르면 {n}곳 중 한 곳을 골라줘요'
    page = (f'<!-- spin {spin} -->'  # 돌린 횟수: HTML이 지난번과 똑같으면 iframe을 다시 안 그려서 다시 돌리기가 안 돎
            + FONT + '<style>' + WHEEL_CSS + '</style>'
            + f'<body style="color: {ink}">' + svg
            + f'<div id="msg" aria-live="polite">{before}</div>')
    if spin:  # 돌리기를 누른 뒤에만 바늘을 돌림. 바뀌는 값은 JS 변수로 (json.dumps = 따옴표까지 안전하게)
        after = f'「{names[target]}」 당첨! 목록에도 골라 뒀어요'
        values = f'const AFTER = {json.dumps(after)}, TARGET = {target}, TURN = {turn:.1f}, WIN = {json.dumps(win)};'
        page += '<script>' + values + WHEEL_JS + '</script>'
    return page
