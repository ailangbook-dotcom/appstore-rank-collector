#!/usr/bin/env python3
"""
행위 우선 탐지 (behavior-first discovery)

차트는 '이미 앱이 된 것'만 보여준다. 이 스크립트는 반대로 간다:
유튜브에서 '아직 앱이 안 된 행위'가 니치 -> 메인스트림으로 넘어가는 변곡점을 찾는다.

검증된 신호 (2026-09-19 슬랑이/왁뿌볼 역추적으로 도출):
  슬랑이  2026-05:  2채널 / 채널규모중앙값    307명 /     20만뷰
          2026-06:  5채널 /                307명 /     21만뷰   <- 왁뿌볼 앱 출시 (06-17)
          2026-07: 11채널 /              1,340명 /  1,669만뷰
          2026-08: 12채널 /            132,000명 /  1,114만뷰   <- 메인스트림, 이미 늦음
  => 진입 시점은 '채널 수가 2배로 늘되 채널 규모는 아직 작은' 달이다.
     조회수가 터진 뒤에 들어가면 늦는다 (왁뿌볼 후속 11개 전멸이 증거).

  '새 단어 탐지'로는 못 잡는다. 왁뿌볼은 2026-01에 이미 유튜브에 있었고
  8월 시점엔 7개월 된 단어였다. 봐야 하는 건 신규성이 아니라 확산 기울기다.

사용법:
  AXIS=toy|luck|relation|self|shop|place|goods VIRAL_OUT=.discover-<축> 를 앞에 붙여 축별로 따로 돌린다.
  YTK=<youtube api key> python viral/discover.py harvest   # 벨웨더 채널 수집
  YTK=<youtube api key> python viral/discover.py pull      # 채널별 업로드 전량 수집
  python viral/discover.py detect                          # 변곡점 탐지
  python viral/discover.py curve <단어>                     # 특정 단어의 확산 곡선(코퍼스 내)
  YTK=<key> python viral/discover.py probe <단어> [개월]     # 확산 곡선(코퍼스 밖, 검색 API 직접)

API 키는 셸 환경변수로만 넘긴다. 파일에 쓰지 말 것 (저장소 공개).
산출물은 VIRAL_OUT(기본 .discover/)에 쌓이며 저장소에 커밋하지 않는다.
"""
import json, os, re, sys, time, collections, urllib.parse, urllib.request
import statistics as st, datetime as dt

OUT = os.environ.get("VIRAL_OUT", os.path.join(os.path.dirname(__file__), "..", ".discover"))
os.makedirs(OUT, exist_ok=True)


def P(n):
    return os.path.join(OUT, n)


# 트렌드가 '시작되는' 곳을 노린다. 대형 종합 채널은 트렌드를 증폭할 뿐 만들지 않는다.
#
# 축별 분리 (2026-09-19 2회차): 단일 SEEDS는 종합 예능·리뷰 채널로 수렴해
# 상위를 일반 명사가 먹는다. 실제로 기본 축으로는 석가머니(기복)가 0건으로 안 잡혔다.
# AXIS 환경변수로 축을 바꾸고, VIRAL_OUT도 축마다 따로 줘야 한다.
SEED_SETS = {
    # 촉각·물건 (기본). 왁뿌볼·슬랑이를 잡아낸 집합.
    "toy": ["ASMR 신상", "문구점 신상", "다이소 신상", "요즘 유행", "챌린지", "말랑이",
            "피젯 토이", "언박싱 장난감", "유행하는 놀이", "요즘 애들", "밈 유행", "신상 아이템 리뷰"],
    # 기복·운세·의례. 석가머니가 여기 있었는데 toy 집합으로는 0건이었다.
    "luck": ["사주 봐드립니다", "타로 리딩", "신점 후기", "운세 보는 법", "부적", "절 기도",
             "기도 브이로그", "소원 이루어지는", "미신 징크스", "꿈 해몽", "MBTI 운세", "개운법"],
    # 관계·고백·연애 의례.
    "relation": ["소개팅 후기", "고백 챌린지", "커플 질문", "친구 테스트", "연애 상담",
                 "랜덤채팅", "인맥 정리", "단톡방", "썸 판별", "결혼식 축의금", "카톡 프사", "연락 끊긴"],
    # 자기정체성·기록·측정.
    "self": ["인생 정리", "루틴 브이로그", "다이어리 꾸미기", "가계부 쓰기", "자기관리 앱",
             "폰 정리", "사진 정리", "습관 만들기", "체크리스트", "성격 테스트", "회고", "목표 세우기"],
    # 2026-09-20 신설. 시드 규칙: '주제'가 아니라 '그 행위를 돈 받고 해주는 사람'을 지목한다.
    # relation/self가 실패한 이유가 주제를 지목해 예능·명언 채널로 수렴했기 때문이다.
    # shop = 몸·외형을 남이 돈 받고 만져주는 영역 (마찰: 돈·예약·이동 확정).
    "shop": ["네일아트 시술", "속눈썹 연장", "타투 도안", "헤어 시술", "퍼스널컬러 진단",
             "셀프사진관", "네컷사진", "필름 현상", "스튜디오 촬영", "메이크업 숍",
             "왁싱 후기", "체형 교정"],
    # ⚠️ 2026-09-20 2회차: buyer 축 폐기. 재실행 금지.
    # 시드가 '도메인'이 아니라 '말투(register)'라서 한국 유튜브 전체 인구를 균등하게 긁는다.
    # detect 상위가 전부 어미였다: 합니다(7채널)·보세요(6)·이벤트(5)·된다(4)·거예요(4).
    # 채널 hit이 9→5→4→2→1로 즉시 꺼져 수렴 자체가 없다(shop/place는 '엉뚱한 곳으로 수렴'이라 다른 실패다).
    # 시드 규칙 최종: 도메인 + 소비자 + 고유명사. 성공한 toy(말랑이)·luck(사주 봐드립니다)가 그 모양이다.
    # 2026-09-20 신설. 9/19 3회차 시드 규칙의 후속 정정:
    # shop/place 시드는 '파는 사람'을 정확히 맞혔고 그래서 공급측 홍보물만 잡혔다.
    # buyer 축은 같은 마찰 영역을 '돈 쓰고 인증하는 소비자'의 말투로 지목한다.
    # 종사자는 서비스명을 쓰고, 소비자는 '처음 가봤는데 / 얼마 썼는지'를 쓴다.
    "buyer": ["처음 가봤는데", "솔직 후기", "돈 얼마 썼는지", "직접 해봤다", "n번째 방문",
              "현실 후기", "해보니까", "이거 사봤다", "내돈내산", "도전해봤습니다",
              "후기 브이로그", "실패 후기"],
    # 2026-09-21 신설. 시드 규칙 3차 정정 적용: 도메인 + 소비자 + **고유명사**.
    # shop/place는 '파는 사람'(서비스명)을 지목해 공급측 홍보물만 잡혔고,
    # buyer는 '말투'를 지목해 어미가 상위를 먹었다. 성공한 toy(말랑이)·luck(사주 봐드립니다)의
    # 공통점은 '소비자가 그 물건을 부르는 고유명사'였다. goods는 그 규칙만 적용한다.
    # 볼꾸·콜렉트북·비즈 자판기는 09-20 다이소 하울 영상 제목에서 실제 관측된 고유명사다.
    "goods": ["젤리캣", "라부부", "스퀴시", "키링 꾸미기", "폰꾸", "볼꾸",
              "콜렉트북", "비즈 자판기", "인형 옷 입히기", "그립톡 꾸미기",
              "다꾸 스티커", "파우치 꾸미기"],
    # place = 돈 내고 그 장소에 가야만 되는 놀이 (마찰: 돈·이동·예약 확정).
    "place": ["방탈출 카페", "보드게임 카페", "클라이밍 도전", "원데이클래스", "도자기 공방",
              "향수 공방", "반지 만들기 공방", "꽃다발 만들기", "실내 낚시터", "코인노래방",
              "오락실 인형뽑기", "스크린골프"],
}
SEEDS = SEED_SETS[os.environ.get("AXIS", "toy")]


def api(ep, **p):
    p["key"] = os.environ["YTK"]
    u = "https://www.googleapis.com/youtube/v3/" + ep + "?" + urllib.parse.urlencode(p)
    err = None
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(u, timeout=30))
        except Exception as e:
            err = e
            time.sleep(1)
    print("  ERR", ep, err, file=sys.stderr)
    return {}


def harvest():
    chans, names = collections.Counter(), {}
    after = (dt.date.today() - dt.timedelta(days=80)).isoformat() + "T00:00:00Z"
    for q in SEEDS:
        d = api("search", part="snippet", type="video", order="viewCount", maxResults=25,
                regionCode="KR", relevanceLanguage="ko", q=q, publishedAfter=after)
        for it in d.get("items", []):
            c = it["snippet"]["channelId"]
            chans[c] += 1
            names[c] = it["snippet"]["channelTitle"]
        print("  " + q + ": " + str(len(d.get("items", []))))
    out = [{"id": c, "name": names[c], "hits": n} for c, n in chans.most_common(70)]
    json.dump(out, open(P("channels.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("채널 %d개 발견 -> 상위 %d개 저장" % (len(chans), len(out)))


def pull():
    chans = json.load(open(P("channels.json"), encoding="utf-8"))
    ids = [c["id"] for c in chans]
    up = {}
    for i in range(0, len(ids), 50):
        d = api("channels", part="contentDetails,statistics", id=",".join(ids[i:i + 50]))
        for it in d.get("items", []):
            up[it["id"]] = (it["contentDetails"]["relatedPlaylists"]["uploads"],
                            int(it.get("statistics", {}).get("subscriberCount", 0) or 0))
    vids = []
    for c in chans:
        if c["id"] not in up:
            continue
        pl, subs = up[c["id"]]
        tok, got = None, 0
        # 다작 채널은 100편으로는 3개월치도 안 된다. 이전 창이 비면 모든 단어가 '신규'로 오판된다.
        while got < 200:
            p = dict(part="snippet", playlistId=pl, maxResults=50)
            if tok:
                p["pageToken"] = tok
            d = api("playlistItems", **p)
            items = d.get("items", [])
            if not items:
                break
            for it in items:
                s = it["snippet"]
                vids.append({"vid": s["resourceId"]["videoId"], "ch": c["name"], "subs": subs,
                             "date": s["publishedAt"][:10], "title": s["title"]})
            got += len(items)
            tok = d.get("nextPageToken")
            if not tok:
                break
        print("  %-20s subs=%9d vids=%d" % (c["name"][:20], subs, got))
    stats = {}
    vi = [v["vid"] for v in vids]
    for i in range(0, len(vi), 50):
        d = api("videos", part="statistics", id=",".join(vi[i:i + 50]))
        for it in d.get("items", []):
            stats[it["id"]] = int(it["statistics"].get("viewCount", 0) or 0)
    for v in vids:
        v["views"] = stats.get(v["vid"], 0)
    json.dump(vids, open(P("videos.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("\n영상 %d개 / 채널 %d개 저장" % (len(vids), len(up)))


STOP = set("""이거 진짜 그냥 우리 오늘 만들기 리뷰 언박싱 챌린지 신상 하는 했는데 하고 해서 너무 완전 대박
처음 마지막 영상 구독 좋아요 댓글 여러분 안녕 하세요 감사 직접 전부 모두 다시 같이 함께 혼자 사람
진심 미쳤 실화 레전드 최초 공개 모음 정리 추천 비교 순위 소리 사운드 먹방 브이로그 일상 하루 아침
저녁 주말 이번 지난 다음 시간 그리고 그래서 하지만 근데 있는 없는 많은 좋은 작은 시리즈 편집 구독자
조회수 유튜브 쇼츠 인스타 틱톡 한국 일본 중국 미국 서울 사람들 이야기 생각 시작 마음 진짜로 역대급
아니 어떻게 그거 저거 뭔가 이런 저런 무슨 때문 정도 경우 하나 여기 거기 오늘의 알바 한번 가지 개웃긴
웃긴영상 랭킹 모먼트 치와와 고양이 강아지 만원 사은품 세상 이유 방법 최고 최악 최강 인생 요즘 유행
사실 상황 반응 표정 친구 엄마 아빠 언니 오빠 동생 학생 선생 남자 여자 아이들 외국인 한국인 충격적인
가격 날씨 영화 그림 익숙한 이상한 어려운 한다는 넘게 무려 최후 올리브영""".split())

SUFFIX = ("으로", "에서", "하기", "했다", "이랑", "까지", "부터", "들이", "이는", "에게", "한테", "보다")


def toks(t):
    out = set()
    for w in re.findall(r"[가-힣]{2,10}", t):
        for suf in SUFFIX:
            if w.endswith(suf) and len(w) > len(suf) + 1:
                w = w[:-len(suf)]
                break
        if len(w) >= 2 and w not in STOP:
            out.add(w)
    return out


def load():
    return json.load(open(P("videos.json"), encoding="utf-8"))


def curve(word):
    V = load()
    m = collections.defaultdict(lambda: {"ch": set(), "v": 0, "subs": [], "n": 0})
    for v in V:
        if word not in v["title"]:
            continue
        d = m[v["date"][:7]]
        d["ch"].add(v["ch"])
        d["v"] += v["views"]
        d["subs"].append(v["subs"])
        d["n"] += 1
    print("=== %s ===\n  월      영상 채널     누적조회   채널규모중앙값" % word)
    for k in sorted(m):
        d = m[k]
        print("  %s  %4d %4d  %12s  %10s"
              % (k, d["n"], len(d["ch"]), format(d["v"], ","), format(int(st.median(d["subs"])), ",")))


def detect():
    V = load()
    E = dt.date.fromisoformat(max(v["date"] for v in V))
    W = [((E - dt.timedelta(days=a)).isoformat(), (E - dt.timedelta(days=b)).isoformat())
         for a, b in ((29, 0), (59, 30), (89, 60))]
    agg = [collections.defaultdict(lambda: {"ch": set(), "v": 0, "subs": [], "vids": []}) for _ in W]
    for v in V:
        for i, (lo, hi) in enumerate(W):
            if lo <= v["date"] <= hi:
                for t in toks(v["title"]):
                    a = agg[i][t]
                    a["ch"].add(v["ch"])
                    a["v"] += v["views"]
                    a["subs"].append(v["subs"])
                    a["vids"].append(v)
    rows = []
    for t, a in agg[0].items():
        c0 = len(a["ch"])
        c1 = len(agg[1][t]["ch"]) if t in agg[1] else 0
        c2 = len(agg[2][t]["ch"]) if t in agg[2] else 0
        if c0 < 3:
            continue
        base = max(c1, c2, 1)
        if c0 < 2 * base:                  # 채널 수 2배 = 확산 시작
            continue
        med = st.median(a["subs"])
        if med > 300000:                   # 이미 메인스트림이면 늦었다
            continue
        # 한 채널이 편수를 독점하면 확산이 아니라 그 채널의 시리즈다.
        # 2026-09-19 오탐 2건이 근거: 손금=화담철학관 125/157편, 랜덤깡=다꾸녀신 36/39편.
        # 채널 수만 세면 둘 다 '3채널 확산'으로 올라온다. 편수 집중도를 봐야 걸러진다.
        share = collections.Counter(v["ch"] for v in a["vids"]).most_common(1)[0][1] / len(a["vids"])
        if share > 0.6:
            continue
        rows.append((c0 / base, c0, c1, c2, int(med), a["v"], t, a["vids"], share))
    rows.sort(key=lambda r: (-r[0], -r[5]))
    print("창: 최근 %s~%s / 이전 %s~%s / 그전 %s~%s\n"
          % (W[0][0], W[0][1], W[1][0], W[1][1], W[2][0], W[2][1]))
    seen = []
    for ratio, c0, c1, c2, med, views, t, vids, share in rows:
        if any(t in s or s in t for s in seen):
            continue
        seen.append(t)
        print("[%s] 확산 %d→%d→%d채널 (x%.1f) 채널규모중앙값=%s 조회=%s 최다채널비중=%.0f%%"
              % (t, c2, c1, c0, ratio, format(med, ","), format(views, ","), share * 100))
        for v in sorted(vids, key=lambda x: -x["views"])[:3]:
            print("     %s %10s (subs %9s) %-14s %s"
                  % (v["date"], format(v["views"], ","), format(v["subs"], ","),
                     v["ch"][:14], v["title"][:50]))
        if len(seen) >= 20:
            break


def probe(word, months=9):
    """코퍼스 밖에서 확산 곡선을 뜬다.

    curve()는 harvest한 벨웨더 70채널 안에서만 센다. 그래서 그 집합에 없는 영역은
    구조적으로 0건이 된다(석가머니가 toy 축에서 0건이었던 이유). probe()는
    검색 API를 월별로 직접 때려서 채널 수 / 채널규모 중앙값 / 조회를 낸다.
    진입 규칙('채널 수 2배 & 채널규모 중앙값 1만 미만')을 임의 단어에 적용할 수 있다.

    비용: 월당 search 100 + channels 1 유닛. 9개월이면 약 909 유닛.
    """
    today = dt.date.today().replace(day=1)
    ms = []
    for i in range(months - 1, -1, -1):
        y, m = divmod((today.year * 12 + today.month - 1) - i, 12)
        ms.append((y, m + 1))
    print("=== probe: %s ==="  % word)
    print("  월       영상 채널  채널규모중앙값      누적조회  최다채널비중")
    for y, m in ms:
        lo = dt.date(y, m, 1)
        hi = dt.date(y + (m == 12), m % 12 + 1, 1)
        d = api("search", part="snippet", type="video", order="relevance", maxResults=50,
                regionCode="KR", relevanceLanguage="ko", q=word,
                publishedAfter=lo.isoformat() + "T00:00:00Z",
                publishedBefore=hi.isoformat() + "T00:00:00Z")
        items = [it for it in d.get("items", []) if word in it["snippet"]["title"]]
        if not items:
            print("  %04d-%02d      0    0           -             -" % (y, m))
            continue
        cids = sorted({it["snippet"]["channelId"] for it in items})
        subs, views = {}, 0
        for i in range(0, len(cids), 50):
            c = api("channels", part="statistics", id=",".join(cids[i:i + 50]))
            for it in c.get("items", []):
                subs[it["id"]] = int(it.get("statistics", {}).get("subscriberCount", 0) or 0)
        vids = [it["id"]["videoId"] for it in items]
        for i in range(0, len(vids), 50):
            vv = api("videos", part="statistics", id=",".join(vids[i:i + 50]))
            for it in vv.get("items", []):
                views += int(it["statistics"].get("viewCount", 0) or 0)
        cnt = collections.Counter(it["snippet"]["channelId"] for it in items)
        share = cnt.most_common(1)[0][1] / len(items)
        med = int(st.median([subs.get(c, 0) for c in cids]))
        print("  %04d-%02d   %4d %4d  %12s  %12s        %3.0f%%"
              % (y, m, len(items), len(cids), format(med, ","), format(views, ","), share * 100))
    print("")
    print("  주의: search API는 상위 50편만 준다. 월 50편을 채우면 포화이므로")
    print("        '채널 수'는 하한이다. 절대값이 아니라 기울기만 읽어라.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "detect"
    if cmd == "curve":
        curve(sys.argv[2])
    elif cmd == "probe":
        probe(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 9)
    else:
        {"harvest": harvest, "pull": pull, "detect": detect}[cmd]()
