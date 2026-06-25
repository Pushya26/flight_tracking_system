from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
def get_alerts(request: Request):
    alerts = request.app.state.alert_worker.get_alerts()
    return [
        {"icao1": a[0], "icao2": a[1], "distance_km": a[2]}
        for a in alerts
    ]
