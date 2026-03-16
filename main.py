from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from pathlib import Path
from datetime import datetime, timedelta, date

# 우리가 만든 계산 모듈들
from services.station_service import get_station_by_id, get_all_stations
from services.weather_service import weather_service
from services.cropwat.eto_calculator import EToCalculator
from services.cropwat.etc_calculator import ETcCalculator
from services.cropwat.irrigation_scheduler import IrrigationScheduler

app = FastAPI(title="CROPWAT Web Service")
templates = Jinja2Templates(directory="templates")


def load_json_data(filename: str):
    """JSON 데이터 로드"""
    file_path = Path(__file__).parent / "data" / filename
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_data_by_id(data_list: list, data_id: str):
    """ID로 데이터 찾기"""
    for item in data_list:
        if item['id'] == data_id:
            return item
    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 입력 페이지"""
    stations = load_json_data("stations.json")
    crops = load_json_data("crops.json")
    soils = load_json_data("soils.json")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stations": stations,
        "crops": crops,
        "soils": soils
    })


@app.post("/calculate", response_class=HTMLResponse)
async def calculate(
        request: Request,
        station_id: str = Form(...),
        crop_id: str = Form(...),
        soil_id: str = Form(...),
        planting_date: str = Form(...),
        harvest_date: str = Form(...)
):
    """CROPWAT 계산 실행"""

    try:
        # 0. 날짜 검증
        stations = load_json_data("stations.json")
        crops = load_json_data("crops.json")
        soils = load_json_data("soils.json")

        planting = datetime.strptime(planting_date, "%Y-%m-%d").date()
        harvest = datetime.strptime(harvest_date, "%Y-%m-%d").date()
        today = date.today()

        if planting > today or harvest > today:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "stations": stations,
                "crops": crops,
                "soils": soils,
                "error_message": "미래 날짜는 입력할 수 없습니다."
            })

        if harvest < planting:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "stations": stations,
                "crops": crops,
                "soils": soils,
                "error_message": "수확일은 파종일보다 빠를 수 없습니다."
            })

        # 1. 데이터 로드
        station = get_station_by_id(station_id)
        crop = get_data_by_id(crops, crop_id)
        soil = get_data_by_id(soils, soil_id)

        if not station or not crop or not soil:
            return HTMLResponse(content="<h1>오류: 선택한 데이터를 찾을 수 없습니다</h1>", status_code=400)

        # 2. 기상 데이터 가져오기
        start_date = planting_date.replace('-', '')
        end_date = harvest_date.replace('-', '')

        weather_data = await weather_service.get_weather_data(
            station_id=station_id,
            start_date=start_date,
            end_date=end_date
        )

        if not weather_data:
            return HTMLResponse(content="<h1>오류: 기상 데이터를 가져올 수 없습니다</h1>", status_code=500)

        # 3. ETo 계산
        eto_calculator = EToCalculator(
            latitude=station['lat'],
            altitude=station.get('altitude', 0)
        )

        eto_values = []
        start = datetime.strptime(planting_date, "%Y-%m-%d")

        for i, weather in enumerate(weather_data):
            day_of_year = (start + timedelta(days=i)).timetuple().tm_yday
            eto = eto_calculator.calculate_daily_eto(weather, day_of_year)
            eto_values.append(eto)

        # 4. ETc 계산
        etc_calculator = ETcCalculator(crop)
        etc_results = etc_calculator.calculate_etc_series(eto_values, planting_date)

        # 5. 관개 스케줄 계산
        rainfall_series = [w['rainfall'] for w in weather_data]

        scheduler = IrrigationScheduler(crop, soil)
        schedule = scheduler.calculate_irrigation_schedule(
            etc_series=etc_results,
            rainfall_series=rainfall_series,
            planting_date=planting_date
        )

        summary = scheduler.summarize_schedule(schedule)

        # 6. CWR 데이터 준비 (decade 단위로 집계)
        cwr_data = prepare_cwr_data(etc_results, rainfall_series)

        # 7. 관개 발생일만 필터링
        irrigation_events = [day for day in schedule if day['irrigation'] > 0]

        # 8. 결과 페이지 렌더링
        return templates.TemplateResponse("results.html", {
            "request": request,
            "station_id": station_id,
            "station_name": station['name'],
            "crop_name": crop['name'],
            "soil_name": soil['name'],
            "planting_date": planting_date,
            "harvest_date": harvest_date,
            "cwr_data": cwr_data,
            "irrigation_events": irrigation_events,
            "summary": summary,
            "yield_reduction": 0.0,  # 나중에 계산
            "options": {
                "depletion_level": 80,
                "application": "Refill to field capacity",
                "field_efficiency": 70
            }
        })

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return HTMLResponse(
            content=f"<h1>계산 중 오류 발생</h1><pre>{error_detail}</pre>",
            status_code=500
        )


def prepare_cwr_data(etc_results, rainfall_series):
    """CWR 테이블용 decade 단위 데이터 준비"""
    cwr_data = []

    # 간단하게 10일 단위로 묶기
    for i in range(0, len(etc_results), 10):
        decade_data = etc_results[i:i + 10]
        decade_rain = rainfall_series[i:i + 10]

        if not decade_data:
            continue

        # 평균 Kc
        avg_kc = sum(d['kc'] for d in decade_data) / len(decade_data)

        # ETc 합계
        etc_sum = sum(d['etc'] for d in decade_data)
        etc_day = etc_sum / len(decade_data)

        # 유효강수량 (간단 계산)
        rain_sum = sum(decade_rain)
        eff_rain = min(rain_sum * 0.8, etc_sum)

        # 관개 필요량
        irr_req = max(0, etc_sum - eff_rain)

        # Month & Decade
        first_date = datetime.strptime(decade_data[0]['date'], "%Y-%m-%d")
        month = first_date.strftime("%b")
        decade = (first_date.day - 1) // 10 + 1

        cwr_data.append({
            'month': month,
            'decade': decade,
            'stage': decade_data[0]['stage'],
            'kc': round(avg_kc, 2),
            'etc_day': round(etc_day, 2),
            'etc_dec': round(etc_sum, 1),
            'eff_rain': round(eff_rain, 1),
            'irr_req': round(irr_req, 1)
        })

    return cwr_data


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)