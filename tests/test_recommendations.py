"""Focused safety, data-integrity, and HTTP coverage for KB v2."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.main import build_app
from backend.recommendations import (
    KB, OBJECTS, RESPONSE_CATALOG, TAXONOMY, recommend,
    validate_knowledge_base, validate_response_catalog,
)


LEGACY_OBJECT_IDS = (
    'plastic_bottle', 'plastic_cap', 'plastic_cup', 'plastic_bag', 'plastic_wrap', 'foam_box', 'straw',
    'paper_sheet', 'cardboard', 'newspaper', 'tissue', 'paper_cup', 'milk_carton', 'release_liner',
    'aluminum_can', 'steel_food_can', 'aerosol_can', 'glass_bottle', 'glass_jar', 'broken_glass',
    'ceramic_bowl', 'fruit_peel', 'leftover_food', 'coffee_grounds', 'dry_leaves', 'old_tshirt',
    'fabric_scraps', 'old_shoes', 'stuffed_toy', 'battery_aa', 'phone', 'charger', 'lightbulb', 'mask',
    'diaper', 'cigarette_butt', 'razor', 'needle', 'chemical_bottle', 'paint_can', 'cooking_oil',
    'wood_scraps', 'rubber_tire',
)


@pytest.fixture
def client():
    return TestClient(build_app(mode='demo'))


BASE_ANSWERS = {
    'condition': 'unknown', 'contamination': 'clean', 'material': 'unknown',
    'pressure': 'no', 'sharp': 'no', 'hot': 'yes', 'battery_state': 'normal',
    'bulb_type': 'led', 'chemical_state': 'no', 'coating': 'no',
}

# Each row exercises a distinct object/state/rule interaction. Parameterization
# intentionally produces independent pytest cases rather than repeating a single check.
SCENARIOS = [
    ('plastic_bottle', {'condition':'usable'}, 'recyclable', 'chai'),
    ('plastic_bottle', {'contamination':'food'}, 'special_collection', 'dư lượng thức ăn'),
    ('plastic_bottle', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('plastic_bottle', {'contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('plastic_cap', {'condition':'usable'}, 'recyclable', 'nắp'),
    ('plastic_cup', {'contamination':'food'}, 'special_collection', 'dư lượng thức ăn'),
    ('plastic_cup', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('plastic_bag', {'condition':'usable','contamination':'clean'}, 'special_collection', 'đơn vị thu gom'),
    ('plastic_bag', {'contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('plastic_wrap', {'contamination':'clean'}, 'residual', 'rác còn lại'),
    ('foam_box', {'contamination':'food'}, 'residual', 'địa phương'),
    ('straw', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('paper_sheet', {'condition':'usable','contamination':'clean'}, 'recyclable', 'giấy sạch'),
    ('paper_sheet', {'contamination':'food'}, 'special_collection', 'dư lượng thức ăn'),
    ('paper_sheet', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('cardboard', {'contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('newspaper', {'contamination':'clean'}, 'recyclable', 'giấy'),
    ('tissue', {'contamination':'clean'}, 'residual', 'rác còn lại'),
    ('paper_cup', {'contamination':'clean'}, 'special_collection', 'tráng phủ'),
    ('milk_carton', {'contamination':'clean'}, 'special_collection', 'nhiều lớp'),
    ('release_liner', {'material':'unknown','contamination':'clean'}, 'residual', 'chưa xác định'),
    ('release_liner', {'material':'coated_paper','contamination':'clean'}, 'residual', 'chưa xác minh'),
    ('release_liner', {'material':'plastic_film','contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('aluminum_can', {'contamination':'clean'}, 'recyclable', 'lon'),
    ('steel_food_can', {'contamination':'food'}, 'special_collection', 'dư lượng thức ăn'),
    ('aerosol_can', {'pressure':'yes'}, 'hazardous', 'tránh nguồn nhiệt'),
    ('aerosol_can', {'pressure':'no'}, 'hazardous', 'Giữ nguyên bình'),
    ('glass_bottle', {'condition':'usable','contamination':'clean','sharp':'no'}, 'reuse', 'còn nguyên vẹn'),
    ('glass_bottle', {'condition':'damaged','contamination':'clean','sharp':'no'}, 'special_collection', 'Không áp dụng hướng dẫn'),
    ('glass_bottle', {'condition':'damaged','contamination':'clean','sharp':'yes'}, 'sharps', 'Không chạm tay trần'),
    ('glass_bottle', {'condition':'unknown','contamination':'hazardous','sharp':'yes'}, 'hazardous', 'Không chạm'),
    ('glass_jar', {'condition':'unknown','contamination':'clean','sharp':'no'}, 'special_collection', 'Không áp dụng hướng dẫn'),
    ('glass_jar', {'condition':'usable','contamination':'clean','sharp':'no'}, 'reuse', 'còn nguyên vẹn'),
    ('broken_glass', {'sharp':'yes'}, 'sharps', 'hộp cứng'),
    ('broken_glass', {'sharp':'no'}, 'sharps', 'Tránh tay trần'),
    ('ceramic_bowl', {'condition':'damaged'}, 'sharps', 'dụng cụ'),
    ('fruit_peel', {'contamination':'clean'}, 'organic', 'thu gom hữu cơ'),
    ('fruit_peel', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('leftover_food', {'contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('coffee_grounds', {'contamination':'food'}, 'organic', 'tuyến hữu cơ'),
    ('dry_leaves', {'condition':'usable'}, 'organic', 'ủ phân'),
    ('old_tshirt', {'condition':'usable','contamination':'clean'}, 'reuse', 'chuyển cho nơi nhận'),
    ('old_tshirt', {'condition':'damaged','contamination':'clean'}, 'special_collection', 'không mặc định'),
    ('old_tshirt', {'condition':'usable','contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('old_tshirt', {'condition':'usable','contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('fabric_scraps', {'condition':'usable','contamination':'clean'}, 'special_collection', 'không mặc định'),
    ('old_shoes', {'condition':'usable','contamination':'clean'}, 'reuse', 'còn nguyên vẹn'),
    ('stuffed_toy', {'condition':'unknown','contamination':'clean'}, 'special_collection', 'không mặc định'),
    ('battery_aa', {'battery_state':'normal'}, 'hazardous', 'điểm thu hồi'),
    ('battery_aa', {'battery_state':'damaged'}, 'hazardous', 'Không sử dụng, sạc'),
    ('battery_aa', {'battery_state':'unknown'}, 'hazardous', 'Tránh thao tác trực tiếp'),
    ('battery_aa', {'battery_state':'active_incident'}, 'hazardous', 'khẩn cấp'),
    ('phone', {'condition':'usable','battery_state':'normal'}, 'ewaste', 'sao lưu'),
    ('phone', {'condition':'usable','battery_state':'damaged'}, 'hazardous', 'Không sử dụng, sạc'),
    ('charger', {'condition':'usable'}, 'ewaste', 'điểm nhận rác điện tử'),
    ('lightbulb', {'bulb_type':'unknown','condition':'usable'}, 'hazardous', 'loại chưa xác định'),
    ('lightbulb', {'bulb_type':'led','condition':'damaged'}, 'hazardous', 'Giữ nguyên, tránh làm vỡ'),
    ('mask', {'contamination':'hazardous'}, 'hazardous', 'Không rửa'),
    ('diaper', {'contamination':'unknown'}, 'special_collection', 'chưa rõ'),
    ('cigarette_butt', {'hot':'no'}, 'hazardous', 'chưa chắc chắn'),
    ('cigarette_butt', {'hot':'yes'}, 'residual', 'đã tắt và nguội'),
    ('razor', {'sharp':'yes'}, 'sharps', 'hộp cứng'),
    ('needle', {'sharp':'yes'}, 'medical', 'cơ sở y tế'),
    ('needle', {'sharp':'no'}, 'medical', 'quy trình vật sắc y tế'),
    ('chemical_bottle', {'chemical_state':'yes'}, 'hazardous', 'tránh tiếp xúc'),
    ('chemical_bottle', {'chemical_state':'no'}, 'hazardous', 'giữ nguyên nhãn'),
    ('paint_can', {'chemical_state':'yes'}, 'hazardous', 'không đổ'),
    ('cooking_oil', {'condition':'usable','contamination':'clean'}, 'special_collection', 'chương trình thu gom'),
    ('wood_scraps', {'condition':'usable','coating':'yes'}, 'special_collection', 'Không đốt'),
    ('rubber_tire', {'condition':'usable'}, 'special_collection', 'garage'),
]


@pytest.mark.parametrize('object_id,updates,expected_stream,must_contain', SCENARIOS)
def test_scenario_matrix(object_id, updates, expected_stream, must_contain):
    answers = {key: value for key, value in BASE_ANSWERS.items() if key in OBJECTS[object_id]['question_ids']}
    answers.update(updates)
    answers = {key: value for key, value in answers.items() if key in OBJECTS[object_id]['question_ids']}
    result = recommend(object_id, answers)
    assert result['status'] == 'complete'
    assert result['stream_id'] == expected_stream
    output = ' '.join([result['recommendation'], *result['avoid'], *result['cautions'], *result['reasons']]).casefold()
    assert must_contain.casefold() in output
    assert result['recommendation'].strip()
    assert result['local_collection_verified'] is False
    assert result['stream_id'] in KB['streams']


@pytest.mark.parametrize('object_id', list(OBJECTS))
def test_every_kb_record_returns_a_complete_result_when_answered(object_id):
    answers = {key: BASE_ANSWERS[key] for key in OBJECTS[object_id]['question_ids']}
    result = recommend(object_id, answers)
    assert result['status'] == 'complete'
    assert result['object_id'] == object_id
    assert result['stream_label'] == KB['streams'][result['stream_id']]


def test_kb_integrity_and_category_references():
    validate_knowledge_base(KB, TAXONOMY)
    validate_response_catalog(RESPONSE_CATALOG, KB, TAXONOMY)
    assert len(OBJECTS) == len(KB['objects']) == 166
    assert tuple(obj['id'] for obj in KB['objects'][:43]) == LEGACY_OBJECT_IDS
    assert tuple(obj['id'] for obj in RESPONSE_CATALOG['objects'][:43]) == LEGACY_OBJECT_IDS


def test_response_catalog_has_vietnamese_guidance_and_verified_references_for_every_object():
    catalog_ids = {obj['id'] for obj in RESPONSE_CATALOG['objects']}
    assert catalog_ids == set(OBJECTS)
    for obj in RESPONSE_CATALOG['objects']:
        guidance = obj['guidance']
        assert obj['review_status'] == 'pending_human_review'
        assert obj['human_review_requirement'] == 'required_before_public_release'
        assert guidance['headline'] and guidance['assessment'] and guidance['default_action']
        assert guidance['practical_steps']
        assert set(obj['source_ids']) <= set(RESPONSE_CATALOG['sources'])
        assert obj['question_ids'] == OBJECTS[obj['id']]['question_ids']
    assert RESPONSE_CATALOG['local_collection_verified'] is False


@pytest.mark.parametrize('mutation,match', [
    ('duplicate_id', 'unique'), ('bad_category', 'taxonomy'), ('bad_question', 'unknown questions'),
    ('bad_stream', 'unknown stream'), ('empty_advice', 'mandatory guidance'), ('orphan_question', 'Orphan'),
    ('duplicate_option', 'duplicate option IDs'), ('empty_option_label', 'empty option label'),
])
def test_kb_validator_rejects_broken_records(mutation, match):
    kb = deepcopy(KB)
    if mutation == 'duplicate_id': kb['objects'][1]['id'] = kb['objects'][0]['id']
    elif mutation == 'bad_category': kb['objects'][0]['category_id'] = 'not-a-category'
    elif mutation == 'bad_question': kb['objects'][0]['question_ids'] = ['missing-question']
    elif mutation == 'bad_stream': kb['objects'][0]['default_stream'] = 'missing-stream'
    elif mutation == 'empty_advice': kb['objects'][0]['base_advice'] = '  '
    elif mutation == 'orphan_question': kb['questions']['orphan'] = {'label':'Unused?', 'options':[{'id':'x','label':'X'}]}
    elif mutation == 'duplicate_option': kb['questions']['condition']['options'][1]['id'] = kb['questions']['condition']['options'][0]['id']
    elif mutation == 'empty_option_label': kb['questions']['condition']['options'][0]['label'] = ''
    with pytest.raises(ValueError, match=match):
        validate_knowledge_base(kb, TAXONOMY)


def test_missing_answers_are_returned_as_pending():
    result = recommend('release_liner', {'material': 'unknown'})
    assert result['status'] == 'needs_input'
    assert [question['id'] for question in result['pending_questions']] == ['contamination']


@pytest.mark.parametrize('answers', [
    {'unknown_question':'x'}, {'condition':'not-an-option'}, {'condition':None},
])
def test_invalid_answers_are_rejected(answers):
    with pytest.raises(ValueError):
        recommend('plastic_bottle', answers)


@pytest.mark.parametrize('source,detected_category', [
    ('manual', None), ('detected', 'textile'), ('corrected', 'textile'),
])
def test_manual_and_detector_provenance_are_preserved(source, detected_category):
    result = recommend('paper_sheet', {'condition':'usable','contamination':'clean'}, source, detected_category)
    assert result['source'] == source
    assert result['detected_category_id'] == detected_category
    assert result['category_id'] == 'paper'
    assert result['stream_id'] == 'recyclable'
    if source == 'corrected':
        assert any('khác nhóm' in caution.casefold() for caution in result['cautions'])


def test_detector_provenance_requires_original_category():
    with pytest.raises(ValueError, match='detected_category_id'):
        recommend('paper_sheet', {'condition':'usable','contamination':'clean'}, 'corrected')
    with pytest.raises(ValueError, match='Không biết nhóm detector'):
        recommend('paper_sheet', {'condition':'usable','contamination':'clean'}, 'corrected', 'invented-class')


def test_hazardous_contamination_replaces_generic_cleaning_advice():
    result = recommend('plastic_bottle', {'condition':'usable','contamination':'hazardous'})
    assert result['stream_id'] == 'hazardous'
    assert result['recommendation'].startswith('Không rửa, súc, đổ bỏ')
    assert 'làm sạch sơ bộ' not in result['recommendation']


def test_broken_glass_never_uses_intact_bottle_advice():
    result = recommend('glass_bottle', {'condition':'damaged','contamination':'clean','sharp':'no'})
    assert result['stream_id'] == 'special_collection'
    assert 'Không áp dụng hướng dẫn cho chai/lọ nguyên vẹn' in result['recommendation']
    assert 'gom theo điểm nhận thủy tinh' not in result['recommendation']


def test_usable_special_objects_do_not_become_reuse_recommendations():
    for object_id, answers in [
        ('cooking_oil', {'contamination':'clean'}),
        ('wood_scraps', {'condition':'usable','coating':'no'}),
        ('rubber_tire', {'condition':'usable'}),
        ('phone', {'condition':'usable','battery_state':'normal'}),
    ]:
        result = recommend(object_id, answers)
        assert result['stream_id'] != 'reuse'


def test_active_battery_and_needle_safety_are_not_downgraded():
    active = recommend('battery_aa', {'battery_state':'active_incident'})
    needle = recommend('needle', {'sharp':'no'})
    assert active['stream_id'] == 'hazardous' and 'Không chạm' in active['recommendation']
    assert needle['stream_id'] == 'medical' and 'Không chạm' in needle['recommendation']


def test_catalog_and_detail_endpoints(client):
    catalog = client.get('/api/v1/recommendations/catalog?q=urgo')
    assert catalog.status_code == 200
    assert catalog.json()['items'][0]['id'] == 'release_liner'
    assert catalog.json()['total_count'] == 166
    detail = client.get('/api/v1/recommendations/objects/release_liner')
    assert detail.status_code == 200
    assert {q['id'] for q in detail.json()['questions']} == {'material', 'contamination'}
    assert client.get('/api/v1/recommendations/objects/not-an-object').status_code == 404


def test_evaluate_endpoint_happy_path_and_traceability(client):
    response = client.post('/api/v1/recommendations/evaluate', json={
        'object_id':'paper_sheet', 'answers':{'condition':'usable','contamination':'clean'},
        'source':'corrected', 'detected_category_id':'textile',
    })
    assert response.status_code == 200
    assert response.json()['source'] == 'corrected'
    assert response.json()['detected_category_id'] == 'textile'
    assert response.json()['object_id'] == 'paper_sheet'
    assert response.json()['context_response']
    assert response.json()['review_status'] == 'pending_human_review'
    assert response.json()['sources'][0]['url'].startswith('https://')


def test_evaluate_endpoint_pending_and_invalid_object(client):
    pending = client.post('/api/v1/recommendations/evaluate', json={'object_id':'plastic_bottle'})
    assert pending.status_code == 200 and pending.json()['status'] == 'needs_input'
    assert client.post('/api/v1/recommendations/evaluate', json={'object_id':'unknown'}).status_code == 404


@pytest.mark.parametrize('answers', [
    {'not_a_question':'x'}, {'condition':'wrong-value'},
])
def test_evaluate_endpoint_rejects_unknown_question_and_option(client, answers):
    response = client.post('/api/v1/recommendations/evaluate', json={'object_id':'plastic_bottle','answers':answers})
    assert response.status_code == 422


def test_evaluate_endpoint_rejects_invalid_source(client):
    response = client.post('/api/v1/recommendations/evaluate', json={'object_id':'plastic_bottle','source':'guess'})
    assert response.status_code == 422


def test_evaluate_endpoint_rejects_unknown_detector_category(client):
    response = client.post('/api/v1/recommendations/evaluate', json={
        'object_id':'paper_sheet','answers':{'condition':'usable','contamination':'clean'},
        'source':'corrected','detected_category_id':'not-in-taxonomy',
    })
    assert response.status_code == 422


def test_legacy_knowledge_and_health_routes_remain_available(client):
    assert client.get('/api/v1/health').status_code == 200
    assert client.get('/api/v1/waste-types').status_code == 200


def test_new_objects_are_available_for_manual_diacritic_insensitive_lookup(client):
    response = client.get('/api/v1/recommendations/catalog?q=nhiet ke&limit=200')
    assert response.status_code == 200
    assert response.json()['total_count'] == 166
    assert any(item['id'] == 'thermometer_mercury' for item in response.json()['items'])
    detail = client.get('/api/v1/recommendations/objects/painted_wood_frame')
    assert detail.status_code == 200
    assert detail.json()['review_status'] == 'pending_human_review'


def test_condition_aware_natural_language_is_selected_for_ordinary_objects():
    obj = next(x for x in RESPONSE_CATALOG['objects'] if x['id'] == 'plastic_bottle')
    expected = obj['guidance']['condition_responses']['usable']
    result = recommend('plastic_bottle', {'condition': 'usable', 'contamination': 'clean'})
    assert result['context_response'] == expected
    assert result['recommendation'] == OBJECTS['plastic_bottle']['base_advice']
    assert result['headline'] == obj['guidance']['headline']
    assert result['assessment'] == obj['guidance']['assessment']
    assert result['practical_steps']
    assert result['safety_override'] is False


def test_food_and_condition_responses_compose_without_dropping_context():
    obj = next(x for x in RESPONSE_CATALOG['objects'] if x['id'] == 'plastic_bottle')
    result = recommend('plastic_bottle', {'condition': 'damaged', 'contamination': 'food'})
    assert obj['guidance']['condition_responses']['damaged'] in result['context_response']
    assert obj['guidance']['contamination_responses']['food'] in result['context_response']


def test_hazardous_contamination_and_special_objects_keep_safety_overrides():
    hazardous = recommend('plastic_bottle', {'condition': 'usable', 'contamination': 'hazardous'})
    assert hazardous['stream_id'] == 'hazardous'
    assert hazardous['safety_override'] is True
    assert hazardous['recommendation'].startswith('Không rửa, súc, đổ bỏ')
    assert 'tận dụng ngắn hạn' not in hazardous['context_response']

    hot_battery = recommend('powerbank', {'condition': 'usable', 'battery_state': 'active_incident'})
    assert hot_battery['stream_id'] == 'hazardous'
    assert hot_battery['safety_override'] is True
    assert 'Không chạm, di chuyển, sạc' in hot_battery['recommendation']

    pressure = recommend('aerosol_can', {'pressure': 'yes'})
    assert pressure['stream_id'] == 'hazardous'
    assert pressure['safety_override'] is True

    needle = recommend('needle', {'sharp': 'no'})
    assert needle['stream_id'] == 'medical'
    assert needle['safety_override'] is True
    assert 'Không chạm' in needle['recommendation']


def test_corrected_yolo_keeps_user_selected_object_and_original_detector_label():
    result = recommend('release_liner', {'material': 'unknown', 'contamination': 'clean'}, 'corrected', 'textile')
    assert result['object_id'] == 'release_liner'
    assert result['category_id'] == 'composite_packaging'
    assert result['detected_category_id'] == 'textile'
    assert result['source'] == 'corrected'
    assert any('YOLO khác nhóm' in caution for caution in result['cautions'])
