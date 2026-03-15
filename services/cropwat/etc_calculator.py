import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta


class ETcCalculator:
    """
    작물 증발산량(ETc) 계산

    ETc = ETo × Kc

    Kc는 작물 생육단계에 따라 변함:
    - Initial (초기)
    - Development (발육기)
    - Mid-season (중기)
    - Late season (후기)
    """

    def __init__(self, crop_data: Dict):
        """
        Args:
            crop_data: 작물 정보
                - kc_init: 초기 Kc
                - kc_mid: 중기 Kc
                - kc_end: 후기 Kc
                - stage_init_days: 초기 기간 (일)
                - stage_dev_days: 발육기 기간 (일)
                - stage_mid_days: 중기 기간 (일)
                - stage_late_days: 후기 기간 (일)
        """
        self.crop_data = crop_data

        # 각 단계 기간
        self.L_init = crop_data['stage_init_days']
        self.L_dev = crop_data['stage_dev_days']
        self.L_mid = crop_data['stage_mid_days']
        self.L_late = crop_data['stage_late_days']

        # 각 단계 Kc 값
        self.Kc_init = crop_data['kc_init']
        self.Kc_mid = crop_data['kc_mid']
        self.Kc_end = crop_data['kc_end']

        # 총 생육기간
        self.total_days = self.L_init + self.L_dev + self.L_mid + self.L_late

    def get_kc_for_day(self, day_since_planting: int) -> tuple:
        """
        파종 후 일수에 따른 Kc 값과 생육단계 반환

        Args:
            day_since_planting: 파종 후 경과 일수 (0부터 시작)

        Returns:
            tuple: (Kc 값, 생육단계 이름)
        """
        if day_since_planting < 0:
            return (0, "Before planting")

        # 각 단계의 끝나는 날 계산
        end_init = self.L_init
        end_dev = end_init + self.L_dev
        end_mid = end_dev + self.L_mid
        end_late = end_mid + self.L_late

        # 초기 단계
        if day_since_planting < end_init:
            return (self.Kc_init, "Init")

        # 발육기 (선형 증가)
        elif day_since_planting < end_dev:
            days_in_stage = day_since_planting - end_init
            Kc = self.Kc_init + (self.Kc_mid - self.Kc_init) * (days_in_stage / self.L_dev)
            return (Kc, "Deve")

        # 중기 단계
        elif day_since_planting < end_mid:
            return (self.Kc_mid, "Mid")

        # 후기 단계 (선형 감소)
        elif day_since_planting < end_late:
            days_in_stage = day_since_planting - end_mid
            Kc = self.Kc_mid - (self.Kc_mid - self.Kc_end) * (days_in_stage / self.L_late)
            return (Kc, "Late")

        # 수확 후
        else:
            return (0, "End")

    def calculate_etc_series(self, eto_series: List[float], planting_date: str) -> List[Dict]:
        """
        전체 재배기간의 ETc 계산

        Args:
            eto_series: ETo 값 리스트 (mm/day)
            planting_date: 파종일 (YYYY-MM-DD)

        Returns:
            List[Dict]: ETc 계산 결과
                - date: 날짜
                - day: 파종 후 일수
                - stage: 생육단계
                - kc: Kc 값
                - eto: ETo (mm/day)
                - etc: ETc (mm/day)
        """
        results = []
        plant_date = datetime.strptime(planting_date, "%Y-%m-%d")

        for day_num, eto in enumerate(eto_series):
            current_date = plant_date + timedelta(days=day_num)
            kc, stage = self.get_kc_for_day(day_num)
            etc = eto * kc

            results.append({
                'date': current_date.strftime("%Y-%m-%d"),
                'day': day_num + 1,
                'stage': stage,
                'kc': round(kc, 2),
                'eto': round(eto, 2),
                'etc': round(etc, 2)
            })

        return results

    @staticmethod
    def load_crop(crop_id: str) -> Dict:
        """작물 데이터 로드"""
        crops_file = Path(__file__).parent.parent.parent / "data" / "crops.json"

        with open(crops_file, "r", encoding="utf-8") as f:
            crops = json.load(f)

        for crop in crops:
            if crop['id'] == crop_id:
                return crop

        raise ValueError(f"작물 ID '{crop_id}'를 찾을 수 없습니다.")


# 테스트 코드
if __name__ == "__main__":
    print("=== ETc 계산기 테스트 ===\n")

    # 양배추 데이터 로드
    crop = ETcCalculator.load_crop("cabbage")
    print(f"📦 작물: {crop['name']} ({crop['name_en']})")
    print(f"   - 초기 Kc: {crop['kc_init']}")
    print(f"   - 중기 Kc: {crop['kc_mid']}")
    print(f"   - 후기 Kc: {crop['kc_end']}")
    print(
        f"   - 총 재배기간: {crop['stage_init_days'] + crop['stage_dev_days'] + crop['stage_mid_days'] + crop['stage_late_days']}일\n")

    # ETc 계산기 생성
    calculator = ETcCalculator(crop)

    # 샘플 ETo 데이터 (10일치, 모두 2.5 mm/day로 가정)
    eto_values = [2.5] * 10

    # ETc 계산
    results = calculator.calculate_etc_series(
        eto_series=eto_values,
        planting_date="2024-01-01"
    )

    print("📊 ETc 계산 결과 (처음 10일):\n")
    print(f"{'날짜':<12} {'일차':>4} {'단계':<6} {'Kc':>6} {'ETo':>8} {'ETc':>8}")
    print("-" * 52)

    for r in results:
        print(f"{r['date']:<12} {r['day']:>4} {r['stage']:<6} {r['kc']:>6.2f} {r['eto']:>8.2f} {r['etc']:>8.2f}")

    print(f"\n✅ 평균 ETc: {sum(r['etc'] for r in results) / len(results):.2f} mm/day")