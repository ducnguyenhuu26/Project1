"""SOICTERRA recommendation engine v2 — deterministic, no LLM or AI inference.

This module never assumes a detected material is the identified object. Callers
may pass category_id as a hint, but must explicitly choose an object_id.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

KB_PATH = Path(__file__).with_name('recommendation_kb.json')
KB = json.loads(KB_PATH.read_text(encoding='utf-8'))
OBJECTS = {x['id']: x for x in KB['objects']}
QUESTIONS = KB['questions']
STREAMS = KB['streams']


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFD', text.casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.replace('-', ' ').replace('_', ' ').split())


def catalog(query: str = '', category_id: str | None = None, limit: int = 100) -> list[dict]:
    """Search manually by Vietnamese object name/alias and optional YOLO category."""
    q = _norm(query.strip())
    if len(query) > 120:
        raise ValueError('Từ khóa quá dài')
    if not 1 <= limit <= 200:
        raise ValueError('limit phải nằm trong khoảng 1–200')
    results = []
    for item in KB['objects']:
        if category_id and item['category_id'] != category_id:
            continue
        words = [item['name_vi'], item['id'], *item.get('aliases_vi', [])]
        if q and not any(q in _norm(word) for word in words):
            continue
        results.append({
            'id': item['id'], 'name_vi': item['name_vi'],
            'category_id': item['category_id'], 'aliases_vi': item['aliases_vi'],
            'question_ids': item['question_ids'],
        })
    return results[:limit]


def detail(object_id: str) -> dict:
    if object_id not in OBJECTS:
        raise KeyError(object_id)
    item = OBJECTS[object_id]
    return {
        'id': item['id'], 'name_vi': item['name_vi'],
        'category_id': item['category_id'],
        'questions': [{'id': k, **QUESTIONS[k]} for k in item['question_ids']],
        'notice': KB['notice'], 'evidence_level': item['evidence_level'],
    }


def recommend(object_id: str, answers: dict[str, str] | None = None,
              source: str = 'manual', detected_category_id: str | None = None) -> dict[str, Any]:
    if object_id not in OBJECTS:
        raise KeyError(object_id)
    if source not in {'manual', 'detected', 'corrected'}:
        raise ValueError('source không hợp lệ')
    item = OBJECTS[object_id]
    answers = answers or {}
    unknown = set(answers) - set(item['question_ids'])
    if unknown:
        raise ValueError(f'Câu hỏi không hợp lệ cho vật thể này: {sorted(unknown)}')
    for key, answer in answers.items():
        permitted = {x['id'] for x in QUESTIONS[key]['options']}
        if answer not in permitted:
            raise ValueError(f'Giá trị không hợp lệ cho {key}: {answer}')
    pending = [key for key in item['question_ids'] if key not in answers]
    if pending:
        return {
            'status': 'needs_input', 'object_id': object_id, 'object_name': item['name_vi'],
            'pending_questions': [{'id': k, **QUESTIONS[k]} for k in pending],
            'answered': answers, 'notice': KB['notice'],
            'detected_category_id': detected_category_id, 'source': source,
        }

    stream = item['default_stream']
    recommendation = item['base_advice']
    cautions = [item['caution']]
    avoid = [item['avoid']]
    reasons = [f"Đã chọn đúng vật thể: {item['name_vi']}. Khuyến nghị gốc theo nhóm xử lý: {STREAMS[stream]}."]

    # First apply non-hazardous reuse and contamination logic.
    condition = answers.get('condition')
    contamination = answers.get('contamination')
    if condition == 'usable' and item['default_stream'] in {'reuse', 'special_collection'}:
        stream = 'reuse'
        recommendation = 'Ưu tiên tiếp tục sử dụng, sửa chữa hoặc chuyển cho nơi nhận đồ còn sử dụng được, khi vật an toàn và vệ sinh.'
        reasons.append('Bạn xác nhận vật vẫn còn sử dụng được.')
    if condition == 'damaged' and item['default_stream'] == 'reuse':
        stream = 'special_collection'
        recommendation = item['base_advice'] + ' Vì đồ đã hỏng, cần xác nhận khả năng tiếp nhận trước khi chuyển giao.'
        reasons.append('Đồ đã hỏng nên không mặc định phù hợp để cho tặng.')
    if contamination == 'food' and stream == 'recyclable':
        stream = 'special_collection'
        recommendation = 'Tách phần dư lượng thực phẩm nếu an toàn, hỏi đơn vị thu gom có nhận loại vật liệu này sau khi làm sạch hay không. Nếu không, làm theo dòng rác còn lại tại nơi ở.'
        reasons.append('Bám bẩn thực phẩm có thể làm giảm khả năng tiếp nhận tái chế.')
    elif contamination == 'hazardous':
        stream = 'hazardous'
        recommendation = 'Không tự xử lý, súc rửa hoặc trộn chung. Giữ riêng khi an toàn và liên hệ đơn vị tiếp nhận chất thải nguy hại phù hợp.'
        reasons.append('Bạn cho biết vật dính hóa chất, dịch cơ thể hoặc chất không rõ.')
    elif contamination == 'unknown':
        cautions.append('Không biết tình trạng nhiễm bẩn: chưa thể xác nhận khả năng tái chế hoặc tái sử dụng.')

    # Specific safety rules take precedence over re-use and material streams.
    if answers.get('battery_state') == 'damaged':
        stream = 'hazardous'
        recommendation = 'Tránh sờ, bóp, sạc, chọc thủng hoặc tự tháo pin. Giữ khoảng cách với nguồn nhiệt và hỏi đơn vị tiếp nhận pin hư hại để được hướng dẫn an toàn.'
        reasons.append('Có dấu hiệu pin hỏng hoặc chưa xác định được trạng thái an toàn.')
    if answers.get('hot') == 'no':
        stream = 'hazardous'
        recommendation = 'Không chạm hay bỏ vào thùng rác khi chưa chắc chắn vật đã tắt và nguội. Làm theo quy trình an toàn phòng cháy tại nơi ở.'
        reasons.append('Đầu thuốc có thể đang cháy hoặc âm ỉ.')
    if answers.get('pressure') == 'yes':
        stream = 'hazardous'
        reasons.append('Bình xịt có thể còn áp suất hoặc thành phần nguy hiểm.')
    if answers.get('bulb_type') in {'fluorescent', 'unknown'}:
        stream = 'hazardous'
        reasons.append('Bóng huỳnh quang/compact có thể chứa thủy ngân hoặc loại bóng chưa xác định.')
    if answers.get('coating') == 'yes':
        stream = 'special_collection'
        cautions.append('Không xác định được lớp sơn/phủ bảo quản và đặc tính hóa chất chỉ từ ảnh.')
    if answers.get('material') == 'unknown':
        cautions.append('Lớp lót có thể là giấy phủ hoặc màng polymer; không được mặc định thuộc giấy tái chế.')
    if answers.get('material') in {'coated_paper', 'plastic_film'}:
        reasons.append('Vật liệu được người dùng cung cấp; vẫn cần xác minh khả năng thu hồi tại địa phương.')
    if answers.get('chemical_state') == 'yes':
        stream = 'hazardous'
        reasons.append('Vật có thể còn hóa chất hoặc chưa xác nhận thành phần.')

    # Never allow a generic material rule to override hazardous object categories.
    if item['default_stream'] in {'hazardous', 'medical', 'sharps'}:
        stream = item['default_stream']
        recommendation = item['base_advice']
        reasons.append('Quy tắc an toàn của loại vật thể được ưu tiên hơn gợi ý tái chế chung.')

    if detected_category_id and detected_category_id != item['category_id']:
        cautions.append('Nhãn YOLO khác lựa chọn vật thể của bạn; hệ thống ưu tiên vật thể do người dùng xác nhận.')

    return {
        'status': 'complete', 'object_id': object_id, 'object_name': item['name_vi'],
        'category_id': item['category_id'], 'source': source,
        'detected_category_id': detected_category_id,
        'answers': answers, 'stream_id': stream, 'stream_label': STREAMS[stream],
        'recommendation': recommendation, 'avoid': avoid, 'cautions': cautions,
        'reasons': reasons,
        'evidence_level': item['evidence_level'],
        'local_collection_verified': False,
        'notice': KB['notice'], 'kb_version': KB['version'],
    }
