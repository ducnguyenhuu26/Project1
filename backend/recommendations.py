"""Deterministic, rule-based item guidance for SOICTERRA Knowledge Base v2."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

KB_PATH = Path(__file__).with_name('recommendation_kb.json')
RESPONSE_CATALOG_PATH = Path(__file__).with_name('response_catalog_v21.json')
TAXONOMY_PATH = Path(__file__).with_name('taxonomy.json')
KB = json.loads(KB_PATH.read_text(encoding='utf-8'))
RESPONSE_CATALOG = json.loads(RESPONSE_CATALOG_PATH.read_text(encoding='utf-8'))
TAXONOMY = json.loads(TAXONOMY_PATH.read_text(encoding='utf-8'))
OBJECTS = {x['id']: x for x in KB['objects']}
RESPONSE_OBJECTS = {x['id']: x for x in RESPONSE_CATALOG['objects']}
QUESTIONS = KB['questions']
STREAMS = KB['streams']

SOURCES = {'manual', 'detected', 'corrected'}
FIXED_SAFETY_STREAMS = {'hazardous', 'medical', 'sharps'}
REUSE_ELIGIBLE = {'old_tshirt', 'old_shoes', 'stuffed_toy', 'glass_bottle', 'glass_jar'}
RULE_QUESTION_IDS = {
    'condition', 'contamination', 'material', 'pressure', 'sharp', 'hot',
    'battery_state', 'bulb_type', 'chemical_state', 'coating',
}


def validate_knowledge_base(kb: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    """Fail fast when KB records cannot be evaluated safely and deterministically."""
    if not isinstance(kb, dict) or not isinstance(taxonomy, dict):
        raise ValueError('Knowledge base and taxonomy must be mappings')
    if not isinstance(kb.get('objects'), list) or not kb['objects']:
        raise ValueError('Knowledge base must contain at least one object')
    if not isinstance(kb.get('questions'), dict) or not isinstance(kb.get('streams'), dict):
        raise ValueError('Knowledge base questions and streams must be mappings')
    notice = kb.get('notice')
    if not isinstance(notice, str) or not notice.strip():
        raise ValueError('Knowledge base notice is required')

    categories = taxonomy.get('categories')
    if not isinstance(categories, list):
        raise ValueError('Taxonomy categories must be a list')
    category_ids = {row.get('id') for row in categories if isinstance(row, dict)}
    if not category_ids:
        raise ValueError('Taxonomy has no categories')
    for stream_id, label in kb['streams'].items():
        if not stream_id or not isinstance(label, str) or not label.strip():
            raise ValueError(f'Invalid stream label: {stream_id!r}')

    for question_id, question in kb['questions'].items():
        options = question.get('options') if isinstance(question, dict) else None
        label = question.get('label') if isinstance(question, dict) else None
        if not isinstance(question_id, str) or not question_id.strip() or not isinstance(label, str) or not label.strip() or not isinstance(options, list) or not options:
            raise ValueError(f'Invalid question definition: {question_id!r}')
        if any(not isinstance(option, dict) for option in options):
            raise ValueError(f'Question {question_id!r} has an invalid option record')
        option_ids = [option.get('id') for option in options]
        if any(not isinstance(option_id, str) or not option_id.strip() for option_id in option_ids) or len(option_ids) != len(set(option_ids)):
            raise ValueError(f'Question {question_id!r} has empty or duplicate option IDs')
        if any(not isinstance(option.get('label'), str) or not option['label'].strip() for option in options):
            raise ValueError(f'Question {question_id!r} has an empty option label')

    if any(not isinstance(obj, dict) for obj in kb['objects']):
        raise ValueError('Object records must be mappings')
    ids = [obj.get('id') for obj in kb['objects']]
    if any(not isinstance(object_id, str) or not object_id.strip() for object_id in ids) or len(ids) != len(set(ids)):
        raise ValueError('Object IDs must be nonempty and unique')
    referenced_questions: set[str] = set()
    for obj in kb['objects']:
        required = ('name_vi', 'category_id', 'default_stream', 'base_advice', 'avoid', 'caution', 'evidence_level')
        if any(not isinstance(obj.get(key), str) or not obj[key].strip() for key in required):
            raise ValueError(f"Object {obj.get('id')!r} has empty mandatory guidance")
        if obj['category_id'] not in category_ids:
            raise ValueError(f"Object {obj['id']!r} references unknown taxonomy category {obj['category_id']!r}")
        if obj['default_stream'] not in kb['streams']:
            raise ValueError(f"Object {obj['id']!r} references unknown stream {obj['default_stream']!r}")
        question_ids = obj.get('question_ids')
        if (not isinstance(question_ids, list)
                or any(not isinstance(key, str) or not key.strip() for key in question_ids)
                or len(question_ids) != len(set(question_ids))):
            raise ValueError(f"Object {obj['id']!r} has invalid question IDs")
        unknown_questions = set(question_ids) - set(kb['questions'])
        if unknown_questions:
            raise ValueError(f"Object {obj['id']!r} references unknown questions: {sorted(unknown_questions)}")
        referenced_questions.update(question_ids)
    orphan_questions = set(kb['questions']) - referenced_questions
    if orphan_questions:
        raise ValueError(f'Orphan question definitions: {sorted(orphan_questions)}')
    invalid_rule_questions = RULE_QUESTION_IDS - set(kb['questions'])
    if invalid_rule_questions:
        raise ValueError(f'Rule engine references undefined questions: {sorted(invalid_rule_questions)}')


def validate_response_catalog(catalog: dict[str, Any], kb: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    """Validate the authored Vietnamese response catalog before serving it."""
    if catalog.get('schema_version') != '2.1' or not isinstance(catalog.get('objects'), list):
        raise ValueError('Response catalog schema/version is invalid')
    ids = [obj.get('id') for obj in catalog['objects'] if isinstance(obj, dict)]
    if len(ids) != len(catalog['objects']) or len(ids) != len(set(ids)):
        raise ValueError('Response catalog object IDs must be unique')
    taxonomy_ids = {row['id'] for row in taxonomy['categories']}
    kb_ids = {obj['id'] for obj in kb['objects']}
    source_ids = set(catalog.get('sources', {}))
    kb_objects = {obj['id']: obj for obj in kb['objects']}
    for obj in catalog['objects']:
        if obj.get('category_id') not in taxonomy_ids:
            raise ValueError(f"Response object {obj.get('id')!r} references an unknown taxonomy category")
        if obj.get('id') not in kb_ids:
            raise ValueError(f"Response object {obj.get('id')!r} is missing from the recommendation KB")
        if set(obj.get('question_ids', [])) - set(kb['questions']):
            raise ValueError(f"Response object {obj['id']!r} references an unknown question")
        if obj.get('question_ids') != kb_objects[obj['id']]['question_ids']:
            raise ValueError(f"Response object {obj['id']!r} question list differs from the recommendation KB")
        if set(obj.get('source_ids', [])) - source_ids:
            raise ValueError(f"Response object {obj['id']!r} references an unknown source")
        guidance = obj.get('guidance', {})
        if not all(isinstance(guidance.get(key), str) and guidance[key].strip()
                   for key in ('headline', 'assessment', 'default_action', 'why')):
            raise ValueError(f"Response object {obj['id']!r} has incomplete Vietnamese guidance")
        if not isinstance(guidance.get('practical_steps'), list) or not guidance['practical_steps']:
            raise ValueError(f"Response object {obj['id']!r} has no practical steps")


validate_knowledge_base(KB, TAXONOMY)
validate_response_catalog(RESPONSE_CATALOG, KB, TAXONOMY)


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFD', text.casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.replace('-', ' ').replace('_', ' ').split())


def catalog(query: str = '', category_id: str | None = None, limit: int = 100) -> list[dict]:
    """Search manually by Vietnamese object name/alias and optional YOLO category."""
    if len(query) > 120:
        raise ValueError('Từ khóa quá dài')
    if not 1 <= limit <= 200:
        raise ValueError('limit phải nằm trong khoảng 1–200')
    q = _norm(query.strip())
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
            'review_status': RESPONSE_OBJECTS[item['id']]['review_status'],
        })
    return results[:limit]


def detail(object_id: str) -> dict:
    if object_id not in OBJECTS:
        raise KeyError(object_id)
    item = OBJECTS[object_id]
    return {
        'id': item['id'], 'name_vi': item['name_vi'],
        'category_id': item['category_id'],
        'questions': [{'id': key, **QUESTIONS[key]} for key in item['question_ids']],
        'notice': KB['notice'], 'evidence_level': item['evidence_level'],
        'headline': RESPONSE_OBJECTS[item['id']]['guidance']['headline'],
        'review_status': RESPONSE_OBJECTS[item['id']]['review_status'],
    }


def recommend(object_id: str, answers: dict[str, str] | None = None,
              source: str = 'manual', detected_category_id: str | None = None) -> dict[str, Any]:
    if object_id not in OBJECTS:
        raise KeyError(object_id)
    if source not in SOURCES:
        raise ValueError('source phải là manual, detected hoặc corrected')
    if source in {'detected', 'corrected'} and not detected_category_id:
        raise ValueError('Cần lưu detected_category_id cho kết quả có nguồn từ detector')
    if detected_category_id and detected_category_id not in {row['id'] for row in TAXONOMY['categories']}:
        raise ValueError(f'Không biết nhóm detector: {detected_category_id}')
    if answers is None:
        answers = {}
    if not isinstance(answers, dict):
        raise ValueError('answers phải là một object gồm question_id và option_id')

    item = OBJECTS[object_id]
    unknown = set(answers) - set(item['question_ids'])
    if unknown:
        raise ValueError(f'Câu hỏi không hợp lệ cho vật thể này: {sorted(unknown)}')
    for key, answer in answers.items():
        if not isinstance(answer, str):
            raise ValueError(f'Giá trị trả lời cho {key} phải là chuỗi option_id')
        permitted = {option['id'] for option in QUESTIONS[key]['options']}
        if answer not in permitted:
            raise ValueError(f'Giá trị không hợp lệ cho {key}: {answer}')

    pending = [key for key in item['question_ids'] if key not in answers]
    if pending:
        return {
            'status': 'needs_input', 'object_id': object_id, 'object_name': item['name_vi'],
            'pending_questions': [{'id': key, **QUESTIONS[key]} for key in pending],
            'answered': answers, 'notice': KB['notice'],
            'detected_category_id': detected_category_id, 'source': source,
        }

    stream = item['default_stream']
    recommendation = item['base_advice']
    cautions = [item['caution']]
    avoid = [item['avoid']]
    reasons: list[str] = [f"Bạn đã chọn vật thể: {item['name_vi']}; hệ thống không suy ra vật thể cụ thể từ nhãn YOLO."]

    condition = answers.get('condition')
    contamination = answers.get('contamination')

    # Reuse is available only to objects whose ordinary use is safe and plausible.
    if condition == 'usable' and object_id in REUSE_ELIGIBLE:
        stream = 'reuse'
        recommendation = 'Chỉ cân nhắc tiếp tục sử dụng hoặc chuyển cho nơi nhận khi vật còn nguyên vẹn, sạch, an toàn và phù hợp với người nhận.'
        reasons.append('Tình trạng còn sử dụng được do người dùng xác nhận; vẫn cần bảo đảm vệ sinh và an toàn.')
    elif condition in {'damaged', 'unknown'} and object_id in REUSE_ELIGIBLE:
        stream = 'special_collection'
        recommendation = 'Không mặc định món đồ phù hợp để sử dụng lại hoặc cho tặng. Kiểm tra tình trạng an toàn và hỏi nơi tiếp nhận phù hợp.'
        reasons.append('Không có xác nhận rằng vật còn an toàn để tái sử dụng.')

    # Contamination rules are applied before any material recovery suggestion.
    if contamination == 'hazardous':
        stream = 'hazardous'
        recommendation = 'Không rửa, súc, đổ bỏ, trộn chung, ủ phân, tái sử dụng hoặc đưa vào tái chế thông thường. Tránh tiếp xúc nếu không rõ an toàn; hỏi cơ quan/đơn vị xử lý phù hợp.'
        avoid.append('Không tự làm sạch hoặc trung hòa chất lạ; không trộn với vật liệu tái chế hay rác hữu cơ.')
        reasons.append('Bạn cho biết vật có thể dính hóa chất, dịch cơ thể hoặc chất không rõ; an toàn được ưu tiên hơn thu hồi vật liệu.')
    elif contamination == 'unknown':
        if stream not in FIXED_SAFETY_STREAMS:
            stream = 'special_collection'
        recommendation = 'Tình trạng bám bẩn chưa rõ. Giữ riêng khi có thể làm vậy an toàn và xác minh thành phần/tuyến tiếp nhận trước khi rửa, tái sử dụng, ủ phân hoặc tái chế.'
        avoid.append('Không mặc định vật sạch hoặc phù hợp cho tái chế/tái sử dụng.')
        cautions.append('Chưa xác minh được chất bám trên vật.')
        reasons.append('Thông tin tình trạng chưa đủ để xác nhận cách thu hồi thông thường.')
    elif contamination == 'food' and item['default_stream'] == 'recyclable':
        stream = 'special_collection'
        recommendation = 'Nếu có thể làm sạch mà không gặp rủi ro, loại bỏ phần thức ăn nhìn thấy được; để khô và hỏi nơi thu gom có tiếp nhận vật này không. Nếu chưa xác minh được, làm theo hướng dẫn rác còn lại tại địa phương.'
        reasons.append('Dư lượng thức ăn có thể ảnh hưởng khả năng tiếp nhận vật liệu; khả năng thu hồi chưa được xác nhận.')

    # Specific high-risk situations override generic material and reuse rules.
    battery_state = answers.get('battery_state')
    if battery_state == 'active_incident':
        stream = 'hazardous'
        recommendation = 'Không chạm, di chuyển, sạc, mở hoặc tự xử lý pin đang nóng, bốc khói hay cháy. Đưa người xung quanh ra xa và liên hệ lực lượng khẩn cấp/cứu hỏa để được hướng dẫn.'
        avoid.append('Không tự vận chuyển, chọc thủng, dội chất lỏng hoặc xử lý pin đang có sự cố theo kinh nghiệm.')
        reasons.append('Pin đang có dấu hiệu sự cố nhiệt/cháy; cần ưu tiên an toàn khẩn cấp.')
    elif battery_state in {'damaged', 'unknown'}:
        stream = 'hazardous'
        recommendation = 'Không sử dụng, sạc, bán như pin còn tốt, tháo rời hoặc chọc thủng. Tránh thao tác trực tiếp; cách cô lập/vận chuyển phụ thuộc loại pin và tình trạng thực tế, nên hỏi đơn vị chuyên trách hoặc cơ quan địa phương.'
        avoid.append('Không bỏ pin hư hại vào rác sinh hoạt hoặc tự vận chuyển khi chưa có hướng dẫn phù hợp.')
        reasons.append('Pin phồng, rò rỉ, hư hại hoặc chưa xác định tình trạng cần được xử lý theo hướng dẫn an toàn riêng.')

    if answers.get('hot') == 'no':
        stream = 'hazardous'
        recommendation = 'Không chạm hoặc bỏ đầu thuốc vào thùng rác khi chưa chắc chắn đã tắt và nguội hoàn toàn. Giữ khoảng cách và làm theo hướng dẫn an toàn phòng cháy tại nơi ở.'
        avoid.append('Không cầm hoặc bỏ đầu thuốc còn nóng/đang cháy vào rác thông thường.')
        reasons.append('Đầu thuốc có thể còn cháy âm ỉ; cần xử lý nguy cơ cháy trước khi thu gom.')

    if answers.get('pressure') == 'yes':
        stream = 'hazardous'
        recommendation = 'Giữ nguyên bình, tránh nguồn nhiệt và hỏi đơn vị tiếp nhận cách bàn giao khi bình còn hoặc có thể còn áp suất/chất bên trong.'
        avoid.append('Không đục thủng, ép, đốt hoặc tháo van bình xịt.')
        reasons.append('Áp suất hoặc thành phần còn lại chưa được xác nhận an toàn.')

    if answers.get('bulb_type') in {'fluorescent', 'unknown'}:
        stream = 'hazardous'
        recommendation = 'Giữ bóng nguyên vẹn nếu an toàn, tránh làm vỡ và hỏi tuyến tiếp nhận phù hợp với loại bóng. Không xử lý như thủy tinh/chai lọ thông thường.'
        reasons.append('Bóng huỳnh quang/compact hoặc loại chưa xác định cần được xử lý thận trọng.')

    if answers.get('chemical_state') == 'yes':
        stream = 'hazardous'
        recommendation = 'Giữ nguyên bao bì/nhãn nếu an toàn; tránh tiếp xúc, đổ bỏ, trộn hoặc súc rửa. Hỏi đơn vị xử lý chất thải nguy hại phù hợp.'
        avoid.append('Không đổ hóa chất xuống cống, trộn hóa chất hoặc tự súc rửa vật chứa.')
        reasons.append('Vật chứa có thể còn hóa chất hoặc chưa xác nhận thành phần.')
    elif answers.get('coating') == 'yes' and contamination != 'hazardous':
        stream = 'special_collection'
        recommendation = 'Không đốt hoặc tái sử dụng lớp phủ không rõ thành phần. Xác minh loại sơn/chất bảo quản và hỏi tuyến tiếp nhận phù hợp.'
        cautions.append('Ảnh và câu trả lời không xác định được thành phần hóa chất của lớp phủ.')
        reasons.append('Lớp phủ có thể ảnh hưởng an toàn và khả năng tiếp nhận.')

    if answers.get('material') == 'unknown':
        cautions.append('Vật liệu lót chưa xác định; không mặc định thuộc dòng giấy tái chế.')
        reasons.append('Lớp lót có thể là giấy phủ hoặc màng polymer; hệ thống giữ nguyên trạng thái chưa biết.')
    elif answers.get('material') in {'coated_paper', 'plastic_film'}:
        cautions.append('Vật liệu do người dùng cung cấp nhưng chưa xác minh khả năng thu hồi tại địa phương.')
        reasons.append('Phân loại này dựa trên câu trả lời người dùng; không xác nhận khả năng tái chế.')

    sharp = answers.get('sharp') == 'yes'
    if sharp and object_id in {'glass_bottle', 'glass_jar', 'broken_glass', 'ceramic_bowl', 'razor', 'needle'}:
        if contamination == 'hazardous':
            stream = 'medical' if object_id == 'needle' else 'hazardous'
            recommendation = 'Không chạm hoặc tự làm sạch vật sắc có thể dính chất nguy hiểm. Giữ khoảng cách và liên hệ cơ sở/đơn vị có thẩm quyền để được hướng dẫn an toàn.'
            avoid.append('Không rửa, súc, cầm tay trần hoặc bỏ vật sắc nhiễm bẩn vào túi mềm.')
        elif object_id == 'needle':
            # The medical/sharps stream remains primary; never suggest household handling.
            stream = 'medical'
            recommendation = 'Không chạm, đậy lại nắp, bẻ hoặc tháo kim. Liên hệ cơ sở y tế/đơn vị có thẩm quyền để được hướng dẫn tiếp nhận vật sắc y tế.'
        else:
            stream = 'sharps'
            recommendation = 'Không chạm tay trần. Nếu có thể làm an toàn, dùng dụng cụ để đặt vật vào hộp cứng chống đâm xuyên, đóng kín và ghi chú vật sắc; xác minh tuyến tiếp nhận phù hợp.'
        avoid.append('Không để vật sắc nhọn rời trong túi mềm hoặc thùng rác có thể gây thương tích.')
        reasons.append('Cạnh sắc đang lộ hoặc có nguy cơ gây thương tích nên hướng dẫn an toàn được ưu tiên.')
    elif (object_id in {'glass_bottle', 'glass_jar'} and condition in {'damaged', 'unknown'}
          and contamination != 'hazardous'):
        stream = 'special_collection'
        recommendation = 'Không áp dụng hướng dẫn cho chai/lọ nguyên vẹn. Đặt riêng khi có thể làm vậy an toàn, không cầm tay trần; xác minh cách thu gom trước khi chuyển đi.'
        cautions.append('Câu trả lời chưa xác định được vật có nứt/vỡ hoặc lộ cạnh sắc hay không.')
        reasons.append('Tình trạng chai/lọ chưa đủ rõ để dùng hướng dẫn tái sử dụng hoặc thu gom thủy tinh nguyên vẹn.')

    # Fixed object streams prevent a generic reuse/recycling answer from taking over.
    if item['default_stream'] in FIXED_SAFETY_STREAMS:
        stream = item['default_stream']
        if item['id'] == 'needle':
            recommendation = 'Không chạm hoặc đậy lại nắp kim bằng tay. Đặt theo quy trình vật sắc y tế của cơ sở phát sinh; nếu nhặt được ở nơi công cộng, tránh tiếp xúc và liên hệ cơ sở y tế/đơn vị có thẩm quyền.'
        elif item['id'] == 'broken_glass':
            recommendation = 'Tránh tay trần; nếu có thể làm an toàn, dùng dụng cụ và hộp cứng chống đâm xuyên có ghi chú vật sắc. Xác minh tuyến tiếp nhận phù hợp.'
        elif item['id'] == 'razor':
            recommendation = 'Không chạm lưỡi dao rời bằng tay trần. Nếu có thể làm an toàn, đặt vào hộp cứng chống đâm xuyên, đóng kín và ghi chú vật sắc.'
        if contamination == 'hazardous':
            cautions.append('Vật có thể dính chất nguy hiểm; tránh thao tác và làm theo hướng dẫn của đơn vị có thẩm quyền.')

    if detected_category_id and detected_category_id != item['category_id']:
        cautions.append('Nhóm YOLO khác nhóm của vật thể bạn đã chọn; khuyến nghị dựa trên vật thể bạn chọn, không coi nhãn YOLO là xác nhận.')

    authored = RESPONSE_OBJECTS[object_id]
    guidance = authored['guidance']
    # A condition/contamination branch is used as natural-language guidance only
    # after the deterministic safety rules above have had the final say.
    safety_override = (
        contamination in {'hazardous', 'unknown'}
        or battery_state in {'active_incident', 'damaged', 'unknown'}
        or answers.get('hot') == 'no'
        or answers.get('pressure') == 'yes'
        or answers.get('bulb_type') in {'fluorescent', 'unknown'}
        or answers.get('chemical_state') == 'yes'
        or answers.get('coating') == 'yes'
        or (sharp and object_id in {'glass_bottle', 'glass_jar', 'broken_glass', 'ceramic_bowl', 'razor', 'needle'})
        or (object_id in {'glass_bottle', 'glass_jar'} and condition in {'damaged', 'unknown'})
        or item['default_stream'] in FIXED_SAFETY_STREAMS
    )
    context_response = recommendation
    if not safety_override:
        # Food residue gets its own object-specific branch. If the user also
        # reported a condition, keep both pieces of guidance together.
        selected_responses = []
        if contamination == 'food' and 'food' in guidance['contamination_responses']:
            selected_responses.append(guidance['contamination_responses']['food'])
            if condition in guidance['condition_responses']:
                selected_responses.append(guidance['condition_responses'][condition])
        elif condition in guidance['condition_responses']:
            selected_responses.append(guidance['condition_responses'][condition])
        elif contamination in guidance['contamination_responses']:
            selected_responses.append(guidance['contamination_responses'][contamination])
        if condition in guidance['condition_responses'] and condition != 'unknown' and not selected_responses:
            selected_responses.append(guidance['condition_responses'][condition])
        if selected_responses:
            context_response = ' '.join(selected_responses)

    safety_text = guidance['safety'].get('Nếu có vật sắc, hóa chất, mốc nặng hoặc chất bẩn không rõ')
    if safety_text and contamination not in {'hazardous', 'unknown'} and not safety_override:
        cautions.append(safety_text)

    reasons.append(f"Hướng xử lý tham khảo: {STREAMS[stream]}; chưa xác minh khả năng tiếp nhận tại địa phương.")
    # Preserve order while removing duplicate notices from layered safety rules.
    cautions = list(dict.fromkeys(cautions))
    avoid = list(dict.fromkeys(avoid))
    return {
        'status': 'complete', 'object_id': object_id, 'object_name': item['name_vi'],
        'category_id': item['category_id'], 'source': source,
        'detected_category_id': detected_category_id,
        'answers': answers, 'stream_id': stream, 'stream_label': STREAMS[stream],
        'recommendation': recommendation, 'avoid': avoid, 'cautions': cautions,
        'context_response': context_response,
        'reasons': reasons, 'evidence_level': item['evidence_level'],
        'headline': guidance['headline'], 'assessment': guidance['assessment'],
        'practical_steps': [step['text'] for step in guidance['practical_steps']],
        'why': guidance['why'], 'next_step': guidance['no_collection'] or guidance['end_of_use'],
        'source_ids': authored['source_ids'], 'review_status': authored['review_status'],
        'sources': [{'id': source_id, **RESPONSE_CATALOG['sources'][source_id]}
                    for source_id in authored['source_ids']],
        'safety_override': safety_override,
        'local_collection_verified': False,
        'notice': KB['notice'], 'kb_version': KB['version'],
    }
