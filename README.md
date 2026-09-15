# App Store Rank Collector

여러 국가의 App Store 카테고리별 **무료 앱 Top 100**을 매일 수집해서 GitHub에 JSON으로 저장하는 최소 프로젝트입니다.

## 수집 대상

- Productivity
- Utilities
- Photo & Video
- Lifestyle
- Health & Fitness
- Education
- Finance
- Entertainment
- Developer Tools
- Graphics & Design

설정은 `src/config.py`에서 바꿀 수 있습니다.

## 구조

```text
.
├── .github/
│   └── workflows/
│       └── collect.yml
├── src/
│   ├── collect.py
│   ├── compare.py
│   └── config.py
├── data/
├── requirements.txt
└── README.md
```

수집 후에는 이런 식으로 데이터가 쌓입니다.

```text
data/
├── 2026-09-15/
│   ├── kr/
│   │   ├── productivity.json
│   │   ├── utilities.json
│   │   ├── photo-video.json
│   │   └── _summary.json
│   ├── us/
│   │   └── ...
│   └── ...
└── 2026-09-16/
    └── ...
```

## 로컬에서 실행

```bash
pip install -r requirements.txt
python src/collect.py
```

## 두 날짜 비교

```bash
python src/compare.py 2026-09-14 2026-09-15 kr productivity
```

`change`는 **양수일수록 순위 상승**입니다.

예:

```json
{
  "previous_rank": 82,
  "current_rank": 20,
  "change": 62,
  "status": "up"
}
```

## GitHub Actions

Repository의 `Actions` 탭에서 `Collect App Store rankings` workflow를 직접 실행할 수 있습니다.

또한 기본 설정으로 매일 한국시간 약 03:10에 자동 실행합니다.

Actions가 repository에 커밋할 수 있도록 다음 설정을 확인하세요.

1. GitHub repository → Settings
2. Actions → General
3. Workflow permissions
4. `Read and write permissions` 선택

## 데이터 출처

Apple의 공개 iTunes RSS JSON feed를 사용합니다.

기본 endpoint 형태:

```text
https://itunes.apple.com/{country}/rss/topfreeapplications/limit={limit}/genre={genre_id}/json
```

카테고리는 URL의 `genre` 값으로 전달합니다 (`rss.marketingtools.apple.com`의 v2 feed는 `genre` 파라미터를 무시해서 카테고리 필터가 동작하지 않으므로 사용하지 않습니다).

## 참고

이 저장소는 다운로드 수 추정치가 아니라 **Apple이 공개하는 App Store chart 순서**를 기록합니다.

Apple의 공개 feed 형식이나 제공 범위가 향후 변경될 수 있으므로, 수집 실패 시 endpoint/response format을 확인해야 합니다.
