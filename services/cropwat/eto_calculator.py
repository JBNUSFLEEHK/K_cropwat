import math
from typing import Dict


class EToCalculator:
    """
    FAO Penman-Monteith 공식을 사용한 기준 증발산량(ETo) 계산

    Reference: FAO Irrigation and Drainage Paper No. 56
    """

    def __init__(self, latitude: float, altitude: float = 0):
        """
        Args:
            latitude: 위도 (도)
            altitude: 고도 (m)
        """
        self.latitude = latitude
        self.altitude = altitude

    def calculate_daily_eto(self, weather_data: Dict, day_of_year: int) -> float:
        """
        일별 ETo 계산

        Args:
            weather_data: 기상 데이터
                - avg_temp: 평균기온 (°C)
                - min_temp: 최저기온 (°C)
                - max_temp: 최고기온 (°C)
                - avg_humidity: 평균상대습도 (%)
                - avg_wind_speed: 평균풍속 (m/s)
                - sunshine_hours: 일조시간 (hr)
                - solar_radiation: 일사량 (MJ/m²/day) - 있으면 사용
            day_of_year: 1~365 (1월 1일 = 1)

        Returns:
            float: ETo (mm/day)
        """
        T_mean = weather_data['avg_temp']
        T_min = weather_data['min_temp']
        T_max = weather_data['max_temp']
        RH_mean = weather_data['avg_humidity']
        u2 = weather_data['avg_wind_speed']
        n = weather_data['sunshine_hours']

        # 1. 평균 기온에서의 포화증기압 곡선 기울기 (kPa/°C)
        delta = self._calculate_delta(T_mean)

        # 2. 대기압 (kPa)
        P = self._calculate_pressure(self.altitude)

        # 3. 습도정수 (kPa/°C)
        gamma = self._calculate_gamma(P)

        # 4. 최저/최고 기온에서의 포화증기압 (kPa)
        e_T_min = self._calculate_saturation_vapor_pressure(T_min)
        e_T_max = self._calculate_saturation_vapor_pressure(T_max)
        e_s = (e_T_min + e_T_max) / 2

        # 5. 실제 증기압 (kPa)
        e_a = (e_s * RH_mean) / 100

        # 6. 순 복사량 (MJ/m²/day)
        if weather_data.get('solar_radiation', 0) > 0:
            # 일사량 데이터가 있으면 사용
            Rs = weather_data['solar_radiation']
        else:
            # 없으면 일조시간으로 추정
            Rs = self._calculate_solar_radiation(day_of_year, n)

        Rn = self._calculate_net_radiation(Rs, T_min, T_max, e_a, day_of_year)

        # 7. 토양열유속 (일별 계산에서는 0으로 가정)
        G = 0

        # 8. FAO Penman-Monteith 공식
        # ETo = (0.408 * Δ * (Rn - G) + γ * (900/(T+273)) * u2 * (es - ea)) / (Δ + γ * (1 + 0.34*u2))

        numerator_1 = 0.408 * delta * (Rn - G)
        numerator_2 = gamma * (900 / (T_mean + 273)) * u2 * (e_s - e_a)
        denominator = delta + gamma * (1 + 0.34 * u2)

        ETo = (numerator_1 + numerator_2) / denominator

        return max(0, ETo)  # 음수 방지

    def _calculate_delta(self, T: float) -> float:
        """포화증기압 곡선의 기울기"""
        return 4098 * (0.6108 * math.exp((17.27 * T) / (T + 237.3))) / ((T + 237.3) ** 2)

    def _calculate_pressure(self, z: float) -> float:
        """고도에 따른 대기압"""
        return 101.3 * ((293 - 0.0065 * z) / 293) ** 5.26

    def _calculate_gamma(self, P: float) -> float:
        """습도정수"""
        return 0.000665 * P

    def _calculate_saturation_vapor_pressure(self, T: float) -> float:
        """포화증기압"""
        return 0.6108 * math.exp((17.27 * T) / (T + 237.3))

    def _calculate_solar_radiation(self, J: int, n: float) -> float:
        """
        일사량 추정 (일조시간 기반)

        Args:
            J: day of year (1-365)
            n: 실제 일조시간 (hr)

        Returns:
            Rs: 일사량 (MJ/m²/day)
        """
        # 위도를 라디안으로 변환
        phi = math.radians(self.latitude)

        # 태양 적위
        delta_rad = 0.409 * math.sin((2 * math.pi / 365) * J - 1.39)

        # 일몰 시각
        omega_s = math.acos(-math.tan(phi) * math.tan(delta_rad))

        # 최대 일조시간
        N = (24 / math.pi) * omega_s

        # 대기권 외 일사량
        dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
        Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
                omega_s * math.sin(phi) * math.sin(delta_rad) +
                math.cos(phi) * math.cos(delta_rad) * math.sin(omega_s)
        )

        # Angstrom 공식
        a_s = 0.25  # 계수
        b_s = 0.50  # 계수
        Rs = (a_s + b_s * (n / N)) * Ra if N > 0 else 0

        return Rs

    def _calculate_net_radiation(self, Rs: float, T_min: float, T_max: float,
                                 e_a: float, J: int) -> float:
        """
        순 복사량 계산

        Args:
            Rs: 일사량 (MJ/m²/day)
            T_min, T_max: 최저/최고기온 (°C)
            e_a: 실제증기압 (kPa)
            J: day of year

        Returns:
            Rn: 순복사량 (MJ/m²/day)
        """
        # 알베도 (반사율)
        alpha = 0.23

        # 순 단파복사
        Rns = (1 - alpha) * Rs

        # 대기권 외 일사량
        phi = math.radians(self.latitude)
        delta_rad = 0.409 * math.sin((2 * math.pi / 365) * J - 1.39)
        omega_s = math.acos(-math.tan(phi) * math.tan(delta_rad))
        dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
        Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
                omega_s * math.sin(phi) * math.sin(delta_rad) +
                math.cos(phi) * math.cos(delta_rad) * math.sin(omega_s)
        )

        # 맑은 날 일사량
        Rso = (0.75 + 2e-5 * self.altitude) * Ra

        # Stefan-Boltzmann 상수
        sigma = 4.903e-9  # MJ/K⁴/m²/day

        # 순 장파복사
        T_min_K = T_min + 273.16
        T_max_K = T_max + 273.16
        Rnl = sigma * ((T_min_K ** 4 + T_max_K ** 4) / 2) * \
              (0.34 - 0.14 * math.sqrt(e_a)) * \
              (1.35 * (Rs / Rso if Rso > 0 else 0.5) - 0.35)

        # 순 복사량
        Rn = Rns - Rnl

        return Rn


# 테스트 코드
if __name__ == "__main__":
    print("=== ETo 계산기 테스트 ===\n")

    # 전주 기상대 위치
    calculator = EToCalculator(latitude=35.8214, altitude=53.4)

    # 샘플 기상 데이터 (2024년 1월 1일)
    weather = {
        'avg_temp': 5.1,
        'min_temp': 0.2,
        'max_temp': 9.3,
        'avg_humidity': 65,
        'avg_wind_speed': 1.1,
        'sunshine_hours': 6.4,
        'solar_radiation': 8.67
    }

    eto = calculator.calculate_daily_eto(weather, day_of_year=1)

    print(f"📅 날짜: 2024-01-01 (1일차)")
    print(f"🌡️  평균기온: {weather['avg_temp']}°C")
    print(f"💧 평균습도: {weather['avg_humidity']}%")
    print(f"💨 평균풍속: {weather['avg_wind_speed']}m/s")
    print(f"☀️  일조시간: {weather['sunshine_hours']}hr")
    print(f"☀️  일사량: {weather['solar_radiation']}MJ/m²")
    print(f"\n✅ 계산된 ETo: {eto:.2f} mm/day")