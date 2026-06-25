from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/")
def get_all_flights(request: Request):
    return list(request.app.state.store.get_all().values())


@router.get("/bbox/search")
def get_flights_in_bbox(lat_min: float, lat_max: float,
                        lon_min: float, lon_max: float,
                        request: Request):
    icao_set = request.app.state.spatial.query_bbox(lat_min, lat_max, lon_min, lon_max)
    return [
        request.app.state.store.get(icao)
        for icao in icao_set
        if request.app.state.store.get(icao)
    ]


@router.get("/{icao24}")
def get_flight(icao24: str, request: Request):
    state = request.app.state.store.get(icao24)
    if not state:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return state
