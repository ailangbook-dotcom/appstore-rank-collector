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
  YTK=<youtube api key> python viral/discover.py harvest   # 벨웨더 채널 수집
  YTK=<youtube api key> python viral/discover.py pull      # 채널별 업로드 전량 수집
  python viral/discover.py detect                          # 변곡점 탐지
  python viral/discover.py curve <단어>                     # 특정 단어의 확산 곡선

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
SEEDS = ["ASMR 신상", "문구점 신상", "다이소 신상", "요즘 유행", "챌린지", "말랑이",
         "피젯 토이", "언박싱 장난감", "유행하는 놀이", "요즘 애들", "밈 유행", "신상 아이템 리뷰"]


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
        rows.append((c0 / base, c0, c1, c2, int(med), a["v"], t, a["vids"]))
    rows.sort(key=lambda r: (-r[0], -r[5]))
    print("창: 최근 %s~%s / 이전 %s~%s / 그전 %s~%s\n"
          % (W[0][0], W[0][1], W[1][0], W[1][1], W[2][0], W[2][1]))
    seen = []
    for ratio, c0, c1, c2, med, views, t, vids in rows:
        if any(t in s or s in t for s in seen):
            continue
        seen.append(t)
        print("[%s] 확산 %d→%d→%d채널 (x%.1f) 채널규모중앙값=%s 조회=%s"
              % (t, c2, c1, c0, ratio, format(med, ","), format(views, ",")))
        for v in sorted(vids, key=lambda x: -x["views"])[:3]:
            print("     %s %10s (subs %9s) %-14s %s"
                  % (v["date"], format(v["views"], ","), format(v["subs"], ","),
                     v["ch"][:14], v["title"][:50]))
        if len(seen) >= 20:
            break


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "detect"
    if cmd == "curve":
        curve(sys.argv[2])
    else:
        {"harvest": harvest, "pull": pull, "detect": detect}[cmd]()
