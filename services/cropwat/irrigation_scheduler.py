import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class IrrigationScheduler:
    """
    관개 스케줄 계산

    토양 수분 균형을 계산하고 관개 시점과 양을 결정
    """

    def __init__(self, crop_data: Dict, soil_data: Dict, options: Optional[Dict] = None):
        """
        Args:
            crop_data: 작물 정보
            soil_data: 토양 정보
            options: 관개 옵션
                - timing: 'critical_depletion' (기본값)
                - depletion_level: 0.8 (80%, 기본값)
                - application: 'refill_to_fc' (기본값)
                - field_efficiency: 70 (%, 기본값)
        """
        self.crop_data = crop_data
        self.soil_data = soil_data

        # 기본 옵션 설정
        default_options = {
            'timing': 'critical_depletion',
            'depletion_level': 0.8,  # 80% depletion에서 관개
            'application': 'refill_to_fc',
            'field_efficiency': 70
        }
        self.options = {**default_options, **(options or {})}

        # 토양 수분 파라미터
        self.fc = soil_data['fc']  # Field Capacity (포장용수량)
        self.pwp = soil_data['pwp']  # Permanent Wilting Point (영구위조점)
        self.tam = soil_data['tam']  # Total Available Moisture (총유효수분, mm/m)

        # 작물 뿌리 깊이 (평균값 사용)
        self.rooting_depth = (crop_data['rooting_depth_min'] + crop_data['rooting_depth_max']) / 2

        # 총유효수분 (mm)
        self.TAW = self.tam * self.rooting_depth / 1000  # mm/m → mm

        # 관개 임계점 (Readily Available Water)
        p = crop_data.get('critical_depletion', 0.5)  # 기본값 50%
        self.RAW = self.TAW * p

    def calculate_irrigation_schedule(
            self,
            etc_series: List[Dict],
            rainfall_series: List[float],
            planting_date: str
    ) -> List[Dict]:
        """
        관개 스케줄 계산

        Args:
            etc_series: ETc 계산 결과 리스트
            rainfall_series: 강수량 리스트 (mm)
            planting_date: 파종일 (YYYY-MM-DD)

        Returns:
            List[Dict]: 관개 스케줄
                - date: 날짜
                - day: 파종 후 일수
                - stage: 생육단계
                - rain: 강수량 (mm)
                - etc: 작물 증발산량 (mm)
                - eff_rain: 유효강수량 (mm)
                - depletion: 토양수분 감소량 (mm)
                - depl_percent: 고갈률 (%)
                - irrigation: 관개량 (mm)
                - net_irrigation: 순관개량 (mm)
        """
        results = []

        # 초기 토양수분 = 포장용수량 (100%)
        current_depletion = 0  # mm (0 = 포장용수량)

        plant_date = datetime.strptime(planting_date, "%Y-%m-%d")

        for i, etc_data in enumerate(etc_series):
            rain = rainfall_series[i] if i < len(rainfall_series) else 0
            etc = etc_data['etc']

            # 유효강수량 계산 (FAO-56 방법)
            eff_rain = self._calculate_effective_rainfall(rain)

            # 전날의 고갈량
            prev_depletion = current_depletion

            # 오늘의 고갈량 = 전날 고갈 + ETc - 유효강수량
            current_depletion = prev_depletion + etc - eff_rain
            current_depletion = max(0, current_depletion)  # 음수 방지

            # 고갈률 (%)
            depl_percent = (current_depletion / self.TAW) * 100 if self.TAW > 0 else 0

            # 관개 필요 여부 판단
            irrigation = 0
            net_irrigation = 0

            if current_depletion >= (self.RAW * self.options['depletion_level']):
                # 관개 필요!
                if self.options['application'] == 'refill_to_fc':
                    # 포장용수량까지 채우기
                    net_irrigation = current_depletion
                else:
                    # 고정량 관개
                    net_irrigation = self.RAW

                # 현장 효율 고려
                irrigation = net_irrigation / (self.options['field_efficiency'] / 100)

                # 관개 후 토양수분 = 포장용수량
                current_depletion = 0

            current_date = plant_date + timedelta(days=i)

            results.append({
                'date': current_date.strftime("%Y-%m-%d"),
                'day': i + 1,
                'stage': etc_data['stage'],
                'rain': round(rain, 1),
                'etc': round(etc, 2),
                'eff_rain': round(eff_rain, 1),
                'depletion': round(current_depletion, 1),
                'depl_percent': round(depl_percent, 1),
                'irrigation': round(irrigation, 1),
                'net_irrigation': round(net_irrigation, 1)
            })

        return results

    def _calculate_effective_rainfall(self, rainfall: float) -> float:
        """
        유효강수량 계산 (FAO-56)

        Args:
            rainfall: 강수량 (mm)

        Returns:
            float: 유효강수량 (mm)
        """
        if rainfall <= 0:
            return 0

        # USDA Soil Conservation Service 방법
        if rainfall < 8.3:
            eff_rain = rainfall
        else:
            eff_rain = (rainfall * 0.8) - 2

        return max(0, eff_rain)

    def summarize_schedule(self, schedule: List[Dict]) -> Dict:
        """
        관개 스케줄 요약 통계

        Args:
            schedule: 관개 스케줄 결과

        Returns:
            Dict: 요약 통계
        """
        total_etc = sum(day['etc'] for day in schedule)
        total_rain = sum(day['rain'] for day in schedule)
        total_eff_rain = sum(day['eff_rain'] for day in schedule)
        total_irrigation = sum(day['irrigation'] for day in schedule)
        total_net_irrigation = sum(day['net_irrigation'] for day in schedule)

        irrigation_events = [day for day in schedule if day['irrigation'] > 0]

        return {
            'total_days': len(schedule),
            'total_etc': round(total_etc, 1),
            'total_rain': round(total_rain, 1),
            'total_eff_rain': round(total_eff_rain, 1),
            'total_irrigation': round(total_irrigation, 1),
            'total_net_irrigation': round(total_net_irrigation, 1),
            'irrigation_count': len(irrigation_events),
            'efficiency_rain': round((total_eff_rain / total_rain * 100) if total_rain > 0 else 0, 1),
            'efficiency_irrigation': self.options['field_efficiency']
        }

    @staticmethod
    def load_soil(soil_id: str) -> Dict:
        """토양 데이터 로드"""
        soils_file = Path(__file__).parent.parent.parent / "data" / "soils.json"

        with open(soils_file, "r", encoding="utf-8") as f:
            soils = json.load(f)

        for soil in soils:
            if soil['id'] == soil_id:
                return soil

        raise ValueError(f"토양 ID '{soil_id}'를 찾을 수 없습니다.")


# 테스트 코드
if __name__ == "__main__":
    from .etc_calculator import ETcCalculator

    print("=== 관개 스케줄 계산 테스트 ===\n")

    # 작물 & 토양 로드
    crop = ETcCalculator.load_crop("cabbage")
    soil = IrrigationScheduler.load_soil("loam")

    print(f"📦 작물: {crop['name']}")
    print(f"🏞️  토양: {soil['name']}\n")

    # ETc 샘플 데이터 (30일)
    etc_series = []
    for day in range(30):
        if day < 10:
            stage, kc = "Init", 0.50
        elif day < 20:
            stage, kc = "Deve", 0.70
        else:
            stage, kc = "Mid", 1.05

        etc_series.append({
            'stage': stage,
            'kc': kc,
            'eto': 3.0,
            'etc': 3.0 * kc
        })

    # 강수량 샘플 (가끔 비)
    rainfall_series = [0] * 30
    rainfall_series[5] = 15  # 6일째 15mm
    rainfall_series[15] = 25  # 16일째 25mm
    rainfall_series[25] = 10  # 26일째 10mm

    # 관개 스케줄 계산
    scheduler = IrrigationScheduler(crop, soil)
    schedule = scheduler.calculate_irrigation_schedule(
        etc_series=etc_series,
        rainfall_series=rainfall_series,
        planting_date="2024-03-01"
    )

    # 관개 발생일만 출력
    print("💧 관개 스케줄 (관개 발생일만):\n")
    print(f"{'날짜':<12} {'일차':>4} {'단계':<6} {'ETc':>6} {'강수':>6} {'관개':>8}")
    print("-" * 50)

    for day in schedule:
        if day['irrigation'] > 0:
            print(f"{day['date']:<12} {day['day']:>4} {day['stage']:<6} "
                  f"{day['etc']:>6.1f} {day['rain']:>6.1f} {day['irrigation']:>8.1f}")

    # 요약 통계
    summary = scheduler.summarize_schedule(schedule)
    print(f"\n📊 요약 통계:")
    print(f"   총 재배기간: {summary['total_days']}일")
    print(f"   총 ETc: {summary['total_etc']} mm")
    print(f"   총 강수량: {summary['total_rain']} mm")
    print(f"   총 관개량: {summary['total_irrigation']} mm")
    print(f"   관개 횟수: {summary['irrigation_count']}회")
    print(f"   관개 효율: {summary['efficiency_irrigation']}%")