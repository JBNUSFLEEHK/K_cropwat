from math import radians, cos, sin, asin, sqrt


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    두 좌표 간의 거리를 km 단위로 계산 (Haversine 공식)

    Args:
        lat1: 첫 번째 지점 위도
        lon1: 첫 번째 지점 경도
        lat2: 두 번째 지점 위도
        lon2: 두 번째 지점 경도

    Returns:
        float: 두 지점 간 거리 (km)

    Example:
        >>> haversine_distance(37.5714, 126.9658, 35.8214, 127.1555)
        193.48
    """
    # 위도/경도를 라디안으로 변환
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine 공식
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # 지구 반지름 (km)
    r = 6371

    return round(c * r, 2)  # 소수점 2자리까지

