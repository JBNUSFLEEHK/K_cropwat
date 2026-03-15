import json
from pathlib import Path
from typing import List, Dict, Optional


def load_stations() -> List[Dict]:
    """
    기상대 데이터 로드

    Returns:
        List[Dict]: 기상대 정보 리스트
    """
    stations_file = Path(__file__).parent.parent / "data" / "stations.json"

    with open(stations_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_station_by_id(station_id: str) -> Optional[Dict]:
    """
    지점번호로 기상대 정보 조회

    Args:
        station_id: 기상대 지점번호 (예: "108", "146")

    Returns:
        Optional[Dict]: 기상대 정보 또는 None
    """
    stations = load_stations()

    for station in stations:
        if station['id'] == station_id:
            return station

    return None


def get_all_stations() -> List[Dict]:
    """
    모든 기상대 리스트 조회 (드롭다운용)

    Returns:
        List[Dict]: 기상대 정보 리스트
    """
    return load_stations()


def get_stations_by_region(region: str) -> List[Dict]:
    """
    지역별 기상대 필터링

    Args:
        region: 지역명 (예: "서울", "경기", "강원")

    Returns:
        List[Dict]: 해당 지역 기상대 리스트
    """
    stations = load_stations()
    return [s for s in stations if s['region'] == region]


# 테스트 코드
if __name__ == "__main__":
    print("=== 기상대 서비스 테스트 ===\n")

    # 1. 모든 기상대 로드
    all_stations = get_all_stations()
    print(f"✅ 전체 기상대 개수: {len(all_stations)}개\n")

    # 2. 특정 기상대 조회
    jeonju = get_station_by_id("146")
    if jeonju:
        print(f"✅ 전주 기상대:")
        print(f"   - 이름: {jeonju['name']} ({jeonju['name_en']})")
        print(f"   - 좌표: ({jeonju['lat']}, {jeonju['lon']})")
        print(f"   - 지역: {jeonju['region']}\n")

    # 3. 지역별 필터링
    gangwon = get_stations_by_region("강원")
    print(f"✅ 강원도 기상대 개수: {len(gangwon)}개")
    for s in gangwon:
        print(f"   - {s['name']} ({s['id']})")