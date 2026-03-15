import httpx
from typing import Dict, List, Optional
from datetime import datetime
from config.settings import settings


class WeatherService:
    """ASOS API 연동 서비스"""

    def __init__(self):
        self.base_url = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
        self.service_key = settings.asos_api_key

    async def get_weather_data(
            self,
            station_id: str,
            start_date: str,
            end_date: str
    ) -> Optional[List[Dict]]:
        """
        ASOS API로 기상 데이터 조회

        Args:
            station_id: 기상대 지점번호 (예: "146")
            start_date: 시작일 (YYYYMMDD 형식, 예: "20240101")
            end_date: 종료일 (YYYYMMDD 형식, 예: "20240131")

        Returns:
            Optional[List[Dict]]: 기상 데이터 리스트 또는 None
        """
        params = {
            "serviceKey": self.service_key,
            "numOfRows": 999,  # 최대 조회 개수
            "pageNo": 1,
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "DAY",
            "startDt": start_date,
            "endDt": end_date,
            "stnIds": station_id
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params, timeout=30.0)
                response.raise_for_status()

                data = response.json()

                # 응답 확인
                header = data.get('response', {}).get('header', {})
                if header.get('resultCode') != '00':
                    print(f"❌ API 오류: {header.get('resultMsg')}")
                    return None

                # 데이터 추출
                items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])

                if not items:
                    print(f"⚠️ 데이터 없음: {start_date} ~ {end_date}")
                    return None

                # CROPWAT 계산에 필요한 데이터만 추출
                weather_data = []
                for item in items:
                    # 안전하게 float 변환하는 헬퍼 함수
                    def safe_float(value, default=0.0):
                        """빈 문자열이나 None을 안전하게 처리"""
                        if value is None or value == '':
                            return default
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return default

                    weather_data.append({
                        'date': item.get('tm'),  # 날짜
                        'avg_temp': safe_float(item.get('avgTa')),  # 평균기온
                        'min_temp': safe_float(item.get('minTa')),  # 최저기온
                        'max_temp': safe_float(item.get('maxTa')),  # 최고기온
                        'rainfall': safe_float(item.get('sumRn')),  # 강수량
                        'avg_humidity': safe_float(item.get('avgRhm')),  # 평균습도
                        'avg_wind_speed': safe_float(item.get('avgWs')),  # 평균풍속
                        'sunshine_hours': safe_float(item.get('sumSsHr')),  # 일조시간
                        'solar_radiation': safe_float(item.get('sumGsr')),  # 일사량
                    })

                return weather_data

        except httpx.HTTPError as e:
            print(f"❌ HTTP 오류: {e}")
            return None
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return None

    def format_date(self, date_str: str) -> str:
        """
        날짜 형식 변환: YYYY-MM-DD → YYYYMMDD

        Args:
            date_str: YYYY-MM-DD 형식 날짜

        Returns:
            str: YYYYMMDD 형식 날짜
        """
        return date_str.replace('-', '')


# 싱글톤 인스턴스
weather_service = WeatherService()

# 테스트 코드
if __name__ == "__main__":
    import asyncio


    async def test():
        print("=== ASOS API 테스트 ===\n")

        service = WeatherService()

        # 전주 기상대, 2024년 1월 1일~10일 데이터
        print("📡 전주(146) 기상대 데이터 조회 중...")
        print("기간: 2024-01-01 ~ 2024-01-10\n")

        data = await service.get_weather_data(
            station_id="146",
            start_date="20240101",
            end_date="20240110"
        )

        if data:
            print(f"✅ 데이터 조회 성공! (총 {len(data)}일)\n")

            # 처음 3일 데이터만 출력
            for i, day in enumerate(data[:3], 1):
                print(f"📅 {day['date']}")
                print(f"   🌡️  평균기온: {day['avg_temp']}°C")
                print(f"   🌡️  최저/최고: {day['min_temp']}°C / {day['max_temp']}°C")
                print(f"   💧 강수량: {day['rainfall']}mm")
                print(f"   💨 평균풍속: {day['avg_wind_speed']}m/s")
                print(f"   ☀️  일조시간: {day['sunshine_hours']}hr")
                print(f"   ☀️  일사량: {day['solar_radiation']}MJ/m²")
                print()

            if len(data) > 3:
                print(f"... 외 {len(data) - 3}일 데이터")
        else:
            print("❌ 데이터 조회 실패")


    # 비동기 함수 실행
    asyncio.run(test())