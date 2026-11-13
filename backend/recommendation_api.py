"""Drop-in FastAPI router: app.include_router(recommendation_router)."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from .recommendations import catalog, detail, recommend, KB

recommendation_router = APIRouter(prefix='/api/v1/recommendations', tags=['recommendations'])

class EvaluationRequest(BaseModel):
    object_id: str = Field(min_length=1, max_length=100)
    answers: dict[str, str] = Field(default_factory=dict)
    source: str = Field(default='manual', pattern='^(manual|detected|corrected)$')
    detected_category_id: str | None = Field(default=None, max_length=100)

@recommendation_router.get('/catalog')
def get_catalog(q: str = Query('', max_length=120), category_id: str | None = None,
                limit: int = Query(100, ge=1, le=200)):
    return {'version': KB['version'], 'items': catalog(q, category_id, limit), 'count': len(catalog(q, category_id, limit))}

@recommendation_router.get('/objects/{object_id}')
def get_object(object_id: str):
    try:
        return detail(object_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Không tìm thấy vật thể')

@recommendation_router.post('/evaluate')
def evaluate(req: EvaluationRequest):
    try:
        return recommend(req.object_id, req.answers, req.source, req.detected_category_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Không tìm thấy vật thể')
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
