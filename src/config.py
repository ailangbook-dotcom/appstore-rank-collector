COUNTRIES = [
    "us", "jp", "kr",
    "gb", "de", "fr",
    "ca", "au",
    "sg", "tw", "hk",
    "nl", "se", "nz"
]
LIMIT = 100
CHART = "top-free"

# Apple App Store genre IDs
# https://developer.apple.com/app-store/categories/
CATEGORIES = {
    "productivity": 6007,
    "utilities": 6002,
    "photo-video": 6008,
    "lifestyle": 6012,
    "health-fitness": 6013,
    "education": 6017,
    "finance": 6015,
    "entertainment": 6016,
    "developer-tools": 6026,
    "graphics-design": 6027,
    # 2026-09-20 추가. 게임이 빠져 있어서 신호1·2·4가 게임 앱을 원리상 한 건도 못 봤다.
    # 촉각·동작 축(왁뿌볼·클리커류)의 후속은 대부분 여기로 나온다.
    "games": 6014,
}
