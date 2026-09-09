"""스프라이트 시트(단색 배경) -> assets/fairy/ 프레임 PNG 추출.

사용법:
    python tools/extract_fairy.py <시트폴더>
<시트폴더> 안의 1.png ~ 7.png 를 읽는다 (SHEETS 매핑 참고).

- 배경색(좌상단 코너 픽셀) 크로마키 -> 알파
- 투명 밴드 기준으로 행/열 분할
- bbox 크롭, 캐릭터 높이 H(px)로 정규화
- 걷기 시트는 좌우 반전본도 생성
"""
import os
import sys
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "fairy")
H = 48        # 출력 캐릭터 높이(px)
THRESH = 90   # 배경색 거리 임계

# 시트 번호 -> (애니 이름, 좌우반전본 생성 여부)
SHEETS = {
    1: ("walkback", False),   # 뒷모습 걷기
    2: ("walk34", False),     # 3/4 정면 걷기
    3: ("idle", False),       # 정면 대기
    4: ("look", False),       # 두리번 (고개 기울임 변형)
    5: ("wave", False),       # 손 흔들기 (3번 프레임 = 잡기 포즈로 사용)
    6: ("walk_b", True),      # 옆모습 걷기 (눈감음 포함)
    7: ("walk", True),        # 옆모습 걷기 (미소)
}


def chroma_key(im):
    im = im.convert("RGBA")
    px = im.load()
    kr, kg, kb = px[2, 2][:3]  # 배경색은 코너에서 샘플
    w, h = im.size
    a = Image.new("L", im.size, 255)
    ap = a.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if abs(r - kr) + abs(g - kg) + abs(b - kb) < THRESH:
                ap[x, y] = 0
    # 가장자리 배경색 번짐 제거: 알파 1px 침식 + 이진화
    a = a.filter(ImageFilter.MinFilter(3))
    a = a.point(lambda v: 255 if v >= 128 else 0)
    im.putalpha(a)
    return im


def split_bands(flags):
    """True(내용 있음) 리스트 -> (start, end) 구간들."""
    bands, s = [], None
    for i, f in enumerate(flags):
        if f and s is None:
            s = i
        elif not f and s is not None:
            bands.append((s, i))
            s = None
    if s is not None:
        bands.append((s, len(flags)))
    return bands


def split_grid(im):
    """투명 밴드로 행 -> 각 행에서 열 분할. 반환: 셀 이미지 리스트(읽기 순)."""
    a = im.getchannel("A")
    w, h = im.size
    data = a.load()
    row_flags = [any(data[x, y] for x in range(0, w, 2)) for y in range(h)]
    cells = []
    for y1, y2 in split_bands(row_flags):
        if y2 - y1 < 40:
            continue
        col_flags = [any(data[x, y] for y in range(y1, y2, 2)) for x in range(w)]
        for x1, x2 in split_bands(col_flags):
            if x2 - x1 < 40:
                continue
            cell = im.crop((x1, y1, x2, y2))
            cells.append(cell.crop(cell.getbbox()))
    return cells


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    for n, (name, flip) in SHEETS.items():
        path = os.path.join(src, f"{n}.png")
        if not os.path.exists(path):
            print(f"{name}: {path} 없음 — 건너뜀")
            continue
        im = chroma_key(Image.open(path))
        cells = split_grid(im)
        print(f"{name}: {len(cells)} frames")
        for i, c in enumerate(cells):
            scale = H / c.height
            c2 = c.resize((max(1, int(c.width * scale)), H), Image.LANCZOS)
            # 리사이즈 후 알파 다시 이진화 (반투명 가장자리 제거)
            c2.putalpha(c2.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
            c2.save(os.path.join(OUT, f"{name}_{i}.png"))
            if flip:
                c2.transpose(Image.FLIP_LEFT_RIGHT).save(
                    os.path.join(OUT, f"{name}r_{i}.png"))


if __name__ == "__main__":
    main()
