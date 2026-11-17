"""Add 35 provisional household objects to both guidance catalogs.

Run once from the repository root. The source tuples remain here so later KB
additions can be reviewed as actual item-specific advice before regeneration.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'backend'
KB_PATH = ROOT / 'recommendation_kb.json'
RESPONSE_PATH = ROOT / 'response_catalog_v21.json'

# id, Vietnamese name, category, stream, action, avoid, caution, aliases
ITEMS = [
    ('shampoo_bottle','Chai dầu gội đã dùng','plastic','recyclable','Bạn hãy làm rỗng chai và chỉ tráng nhẹ nếu bên trong là dầu gội thông thường; sau đó để khô và hỏi nơi thu gom có nhận loại chai này không.','Bạn đừng trộn chai còn nhiều dung dịch với nhựa sạch.','Nếu chai từng chứa hóa chất khác hoặc không rõ chất bên trong, bạn hãy giữ nguyên nhãn và hỏi đơn vị tiếp nhận phù hợp.',['vỏ chai dầu gội']),
    ('yogurt_cup','Hũ sữa chua nhựa','plastic','special_collection','Bạn hãy vét hết thức ăn còn lại và kiểm tra nơi thu gom có nhận loại hũ nhựa này không.','Bạn đừng bỏ hũ còn dính nhiều sữa chua vào dòng nhựa khô.','Mã nhựa trên đáy hũ không tự xác nhận rằng địa phương có thể tái chế hũ.',['cốc sữa chua']),
    ('margarine_tub','Hộp bơ thực vật nhựa','plastic','special_collection','Bạn hãy lấy hết phần bơ còn lại, để hộp khô rồi hỏi nơi nhận có tiếp nhận loại hộp này không.','Bạn đừng đưa hộp còn dính nhiều dầu mỡ vào túi nhựa sạch.','Nắp và thân hộp có thể làm từ vật liệu khác nhau; bạn hãy kiểm tra yêu cầu của nơi nhận.',['hộp bơ nhựa']),
    ('takeout_plastic_box','Hộp nhựa đựng đồ ăn mang về','plastic','special_collection','Bạn hãy bỏ thức ăn thừa, làm sạch sơ bộ nếu an toàn và kiểm tra loại nhựa mà nơi thu gom nhận.','Bạn đừng mặc định mọi hộp đồ ăn đều được tái chế.','Hộp dính dầu mỡ hoặc làm từ nhiều lớp vật liệu có thể cần tuyến xử lý khác.',['hộp cơm mang về']),
    ('plastic_cutlery','Muỗng, nĩa nhựa dùng một lần','plastic','residual','Bạn hãy gạt sạch thức ăn còn bám và làm theo hướng dẫn rác còn lại tại địa phương nếu không có nơi nhận riêng.','Bạn đừng tự bỏ muỗng nhựa vào dòng chai nhựa tái chế.','Vật nhỏ và dính thức ăn thường khó được tiếp nhận cùng chai, hộp nhựa; bạn nên hỏi chương trình thu gom cụ thể.',['thìa nhựa','dĩa nhựa']),
    ('zip_bag','Túi nhựa có khóa kéo','plastic','special_collection','Bạn hãy làm rỗng và để túi khô; nếu còn sạch, bạn có thể dùng lại hoặc hỏi điểm nhận màng nhựa.','Bạn đừng trộn túi nhựa mềm vào thùng thu gom chai, hộp nhựa khi nơi nhận không cho phép.','Khóa kéo có thể làm quy trình thu hồi khác màng nhựa thông thường.',['túi zip','túi zipper']),
    ('plastic_cup_lid','Nắp ly nhựa mang đi','plastic','special_collection','Bạn hãy tách nắp khỏi ly, bỏ phần đồ uống còn sót và hỏi nơi nhận có thu gom loại nắp này không.','Bạn đừng coi nắp ly là cùng vật liệu với phần thân ly giấy.','Nhựa của nắp và lớp phủ của ly có thể cần cách phân loại khác nhau.',['nắp cốc nhựa']),
    ('plastic_bottle_label','Màng nhãn chai nhựa','plastic','special_collection','Bạn hãy giữ hoặc tách nhãn theo đúng yêu cầu của nơi thu gom chai; nếu không rõ, bạn cứ để nguyên chai và hỏi trước.','Bạn đừng tự khẳng định màng nhãn được nhận cùng chai chỉ vì nó cũng là nhựa.','Nhãn co nhiệt và keo dán có thể khác vật liệu thân chai.',['nhãn co chai','tem chai nhựa']),
    ('plastic_sauce_bottle','Chai nhựa đựng nước sốt','plastic','special_collection','Bạn hãy làm rỗng, loại bỏ phần nước sốt nhìn thấy được nếu an toàn rồi hỏi nơi thu gom có nhận chai không.','Bạn đừng đưa chai còn nhiều nước sốt vào dòng nhựa sạch.','Nếu chai từng chứa hóa chất khác hoặc có mùi lạ, bạn hãy giữ riêng và xác minh trước khi rửa.',['chai tương ớt','chai nước mắm nhựa']),
    ('cereal_box','Hộp giấy đựng ngũ cốc','paper','recyclable','Bạn hãy lấy túi lót bên trong ra, giữ hộp giấy khô và gấp gọn nếu nơi thu gom nhận giấy bìa.','Bạn đừng trộn túi lót nhựa với phần hộp giấy.','Nếu hộp bị ướt hoặc dính nhiều thức ăn, bạn cần hỏi nơi thu gom trước khi đưa vào giấy sạch.',['hộp ngũ cốc']),
    ('shoebox','Hộp giày bằng bìa giấy','paper','recyclable','Bạn có thể dùng lại hộp còn tốt; nếu bỏ đi, hãy lấy vật lót ra và gấp gọn hộp giấy khô.','Bạn đừng bỏ xốp lót hoặc túi nhựa vào cùng dòng giấy bìa.','Hộp có phủ nhựa hoặc dính bẩn cần được nơi thu gom xác nhận trước.',['hộp đựng giày']),
    ('paper_folder','Bìa hồ sơ giấy','paper','recyclable','Bạn hãy giữ bìa giấy khô và tách các kẹp kim loại hoặc màng nhựa dễ tháo trước khi bàn giao.','Bạn đừng coi toàn bộ bìa có lớp phủ nhựa là giấy tái chế thông thường.','Nếu bìa có nhiều lớp dán chặt, bạn hãy hỏi nơi thu gom về khả năng tiếp nhận.',['bìa kẹp giấy','folder giấy']),
    ('sticky_notes','Giấy ghi chú có keo','paper','special_collection','Bạn hãy gom giấy ghi chú khô và hỏi nơi thu gom có nhận giấy dính keo hay không.','Bạn đừng tự khẳng định mọi loại giấy có keo đều đi cùng giấy văn phòng.','Lớp keo và màu phủ khác nhau tùy sản phẩm nên khả năng thu hồi phụ thuộc nơi nhận.',['giấy note','giấy nhớ']),
    ('greeting_card','Thiệp chúc mừng bằng giấy','paper','special_collection','Bạn có thể giữ lại thiệp còn tốt; khi bỏ đi, hãy tách phụ kiện nhựa, pin hoặc kim tuyến nếu có thể làm an toàn.','Bạn đừng đưa thiệp có nhạc điện tử hoặc pin vào giấy thuần.','Thiệp phủ nhũ, ép màng hoặc có linh kiện cần được phân loại theo thành phần thực tế.',['thiệp sinh nhật','thiệp giấy']),
    ('cardboard_sleeve','Vỏ bọc giấy của ly mang đi','paper','recyclable','Bạn hãy tháo vỏ bọc khỏi ly, giữ khô và hỏi nơi nhận có thu gom giấy bìa này không.','Bạn đừng bỏ cả ly tráng phủ vào cùng vỏ bọc giấy.','Vỏ bọc và thân ly có thể đi theo hai tuyến xử lý khác nhau.',['áo giấy ly cà phê']),
    ('paper_plate','Đĩa giấy dùng một lần','paper','special_collection','Bạn hãy bỏ thức ăn thừa và kiểm tra đĩa có lớp phủ chống thấm trước khi hỏi nơi thu gom.','Bạn đừng mặc định đĩa giấy dính dầu mỡ là giấy sạch có thể tái chế.','Loại phủ nhựa và mức bẩn quyết định khả năng tiếp nhận; ảnh chụp không đủ để xác nhận.',['dĩa giấy']),
    ('paper_coffee_filter','Giấy lọc cà phê đã dùng','paper','special_collection','Bạn hãy tách bã cà phê và hỏi nơi nhận hữu cơ hoặc chương trình ủ phân có chấp nhận giấy lọc này không.','Bạn đừng bỏ giấy lọc ướt vào giấy tái chế khô.','Giấy lọc có thể được xử lý khác nhau tùy chất liệu và hệ thống ủ phân địa phương.',['phin giấy cà phê']),
    ('metal_bottle_cap','Nắp chai kim loại','metal','recyclable','Bạn hãy tách nắp khỏi chai, giữ khô và hỏi nơi nhận kim loại cách thu gom vật nhỏ.','Bạn đừng để nắp sắc nhọn rời trong túi mềm có người phải cầm bằng tay.','Vì nắp rất nhỏ, một số nơi có thể yêu cầu gom trong hộp kim loại lớn hơn.',['nắp bia','nắp chai sắt']),
    ('biscuit_tin','Hộp bánh quy bằng kim loại','metal','recyclable','Bạn có thể dùng lại hộp còn tốt; nếu bỏ đi, hãy làm rỗng và giữ khô trước khi hỏi nơi thu gom kim loại.','Bạn đừng để bánh vụn hoặc vật khác bên trong khi bàn giao.','Lớp sơn và chi tiết nhựa trên hộp có thể ảnh hưởng yêu cầu của nơi nhận.',['hộp bánh sắt']),
    ('aluminum_food_tray','Khay nhôm đựng thực phẩm','metal','special_collection','Bạn hãy gạt sạch phần thức ăn nhìn thấy được nếu làm vậy an toàn, rồi hỏi nơi nhận nhôm có tiếp nhận khay không.','Bạn đừng đưa khay dính nhiều dầu mỡ vào dòng kim loại sạch.','Khay rất mỏng hoặc phủ vật liệu khác có thể không được thu gom như lon nhôm.',['khay nhôm nướng']),
    ('metal_hanger','Móc áo bằng kim loại','metal','special_collection','Bạn có thể dùng lại móc còn chắc; nếu hỏng, hãy gom riêng và hỏi nơi nhận kim loại hoặc tiệm giặt là có tiếp nhận không.','Bạn đừng để đầu dây nhọn lộ ra ngoài túi thu gom.','Móc có lớp nhựa hoặc nhiều vật liệu nên cần xác minh trước khi phân loại.',['móc áo sắt']),
    ('tea_tin','Hộp trà bằng kim loại','metal','recyclable','Bạn hãy làm rỗng hộp, giữ khô và hỏi nơi thu gom kim loại có nhận loại hộp này không.','Bạn đừng để túi trà hoặc gói hút ẩm trong hộp khi bàn giao.','Nắp nhựa và thân kim loại có thể cần tách riêng theo yêu cầu nơi nhận.',['lon trà']),
    ('glass_sauce_bottle','Chai thủy tinh đựng nước sốt','glass','special_collection','Bạn hãy làm rỗng chai, giữ nguyên vẹn và hỏi nơi thu gom thủy tinh có nhận loại chai này không.','Bạn đừng bỏ chai nứt vỡ vào cùng chai nguyên vẹn.','Nếu chai có cạnh sắc hoặc từng chứa chất lạ, bạn cần chuyển sang hướng dẫn an toàn phù hợp.',['chai nước mắm thủy tinh','chai tương thủy tinh']),
    ('candle_jar','Hũ thủy tinh đựng nến','glass','special_collection','Bạn hãy để hũ nguội hoàn toàn, giữ nguyên vẹn và hỏi nơi nhận thủy tinh cách xử lý phần sáp còn lại.','Bạn đừng đổ sáp nóng xuống cống hoặc cố cạy hũ đang nứt.','Sáp, bấc và lớp phủ trên hũ có thể khiến nơi thu gom từ chối tiếp nhận.',['lọ nến thơm']),
    ('glass_vase','Bình hoa thủy tinh','glass','special_collection','Bạn có thể dùng lại bình còn nguyên; nếu bỏ đi, hãy làm rỗng, giữ riêng và hỏi nơi nhận thủy tinh gia dụng.','Bạn đừng trộn bình hoa nứt vỡ với chai lọ nguyên vẹn.','Loại thủy tinh gia dụng có thể khác dòng chai lọ được thu gom; cần xác nhận tại địa phương.',['lọ hoa thủy tinh']),
    ('onion_skin','Vỏ hành, vỏ tỏi','organic','organic','Bạn hãy để vỏ hành tỏi riêng khỏi bao bì và hỏi chương trình thu gom hữu cơ hoặc nơi ủ phân có nhận không.','Bạn đừng trộn vỏ rau củ với túi nilon rồi đưa vào dòng hữu cơ.','Nếu vỏ dính hóa chất không rõ, bạn hãy giữ riêng và xác minh trước khi ủ.',['vỏ tỏi']),
    ('watermelon_rind','Vỏ dưa hấu','organic','organic','Bạn hãy cắt nhỏ nếu cần, để ráo và đưa vào dòng hữu cơ khi nơi thu gom hoặc hệ thống ủ phân chấp nhận.','Bạn đừng để vỏ ướt lẫn bao bì nhựa trong thời gian dài.','Khối lượng và độ ẩm lớn có thể gây mùi nếu lưu trữ không phù hợp.',['cùi dưa hấu']),
    ('avocado_pit','Hạt bơ','organic','organic','Bạn hãy tách hạt khỏi bao bì, kiểm tra nơi ủ phân có nhận vật hữu cơ phân hủy chậm như hạt bơ không.','Bạn đừng cho rằng hạt lớn sẽ phân hủy nhanh trong mọi hệ thống ủ tại nhà.','Nếu nơi thu gom không nhận, bạn cần làm theo hướng dẫn rác còn lại của địa phương.',['hột bơ']),
    ('grass_clippings','Cỏ vừa cắt','organic','organic','Bạn hãy giữ cỏ sạch riêng khỏi đất đá và hỏi nơi thu gom rác vườn hoặc hệ thống ủ phân có nhận không.','Bạn đừng ủ cỏ có dính thuốc diệt cỏ khi chưa xác minh tính an toàn.','Cỏ ướt chất đống dễ phát sinh mùi; bạn nên xử lý sớm theo hướng dẫn phù hợp.',['cỏ sân vườn']),
    ('vegetable_stems','Cuống rau và lá rau bỏ đi','organic','organic','Bạn hãy tách cuống lá rau khỏi dây buộc và bao bì, rồi dùng dòng hữu cơ nếu nơi thu gom chấp nhận.','Bạn đừng trộn dây thun và túi nhựa vào phần rau củ để ủ.','Nếu rau dính chất lạ hoặc thuốc bảo vệ thực vật chưa rõ, bạn hãy hỏi đơn vị thu gom trước.',['gốc rau','lá rau thừa']),
    ('old_socks','Tất, vớ cũ','textile','special_collection','Bạn hãy giặt và phơi khô đôi tất còn dùng được trước khi hỏi nơi nhận đồ cũ; tất hỏng cần hỏi nơi thu gom vải.','Bạn đừng cho tặng tất ẩm mốc hoặc bẩn như món đồ còn sử dụng tốt.','Khả năng nhận hàng dệt may nhỏ phụ thuộc từng chương trình địa phương.',['vớ cũ']),
    ('denim_jeans','Quần jean cũ','textile','special_collection','Bạn có thể sửa hoặc dùng lại quần còn tốt; nếu không, hãy giặt khô và hỏi nơi nhận quần áo cũ.','Bạn đừng đưa quần dính dầu máy hoặc hóa chất vào dòng đồ cho tặng.','Khóa kéo và nút kim loại có thể ảnh hưởng cách thu hồi sợi vải.',['quần bò cũ']),
    ('cloth_tote','Túi vải mua hàng cũ','textile','special_collection','Bạn hãy giặt sạch và dùng lại túi còn chắc; nếu rách hỏng, hãy hỏi chương trình thu gom vải có nhận không.','Bạn đừng cho tặng túi mốc hoặc dính chất không rõ.','Túi có lớp phủ nhựa có thể không đi cùng vải thuần.',['túi tote','túi canvas']),
    ('wooden_cutting_board','Thớt gỗ cũ','wood','special_collection','Bạn hãy ngừng dùng thớt nứt sâu hoặc mốc; hãy hỏi nơi nhận đồ gỗ nhỏ cách bàn giao.','Bạn đừng đốt thớt có lớp sơn, keo hoặc chất bảo quản không rõ.','Thớt từng tiếp xúc thực phẩm và có thể có lớp phủ, nên không mặc định phù hợp để ủ phân.',['thớt tre cũ']),
    ('popsicle_sticks','Que kem gỗ đã dùng','wood','special_collection','Bạn hãy bỏ phần kem còn dính, giữ que riêng và hỏi nơi thu gom rác hữu cơ có nhận gỗ chưa xử lý không.','Bạn đừng tự đưa que có sơn hoặc mực in vào đống ủ tại nhà.','Gỗ đã phủ màu hoặc keo có thể cần hướng xử lý khác gỗ mộc.',['que kem gỗ']),
]

REUSABLE_IDS = {
    'zip_bag', 'shoebox', 'paper_folder', 'greeting_card', 'biscuit_tin',
    'metal_hanger', 'tea_tin', 'glass_vase', 'old_socks', 'denim_jeans',
    'cloth_tote', 'wooden_cutting_board',
}

def questions_for(object_id: str) -> list[str]:
    # A condition question is useful for durable items. For a single-use
    # wrapper, only contamination changes the safe handling route.
    return ['condition', 'contamination'] if object_id in REUSABLE_IDS else ['contamination']

def make_rows(row):
    object_id, name, category, stream, action, avoid, caution, aliases = row
    questions = questions_for(object_id)
    evidence = 'general_guidance_requires_local_verification'
    kb_row = dict(id=object_id, name_vi=name, category_id=category, aliases_vi=aliases,
                  default_stream=stream, base_advice=action, avoid=avoid, caution=caution,
                  question_ids=questions, evidence_level=evidence)
    source_ids = ['EPA-C', 'VN'] if category == 'organic' else ['EPA-R', 'VN']
    if category == 'textile':
        source_ids = ['REUSE', 'VN']
    elif category == 'wood':
        source_ids = ['VN']
    condition_responses = ({
        'usable': f'Nếu {name.lower()} vẫn còn dùng tốt và an toàn, bạn có thể tiếp tục sử dụng trước khi cân nhắc bỏ đi. {action}',
        'damaged': f'Nếu {name.lower()} đã hỏng hoặc mất an toàn khi sử dụng, bạn nên ngừng dùng và không cho tặng như đồ còn tốt. {action}',
        'unknown': f'Nếu bạn chưa rõ tình trạng của {name.lower()}, hãy kiểm tra trước khi quyết định xử lý. {caution}',
    } if 'condition' in questions else {})
    food_response = (
        f'Nếu {name.lower()} lẫn thức ăn hoặc bao bì, bạn hãy tách phần không phải hữu cơ trước khi thu gom. {action}'
        if category == 'organic' else
        f'Nếu {name.lower()} còn dính thức ăn, bạn hãy loại bỏ phần bám nhìn thấy được khi có thể làm vậy an toàn và để khô. {action}'
        if category in {'plastic', 'paper', 'metal', 'glass'} else
        f'Nếu {name.lower()} dính thức ăn, bạn chỉ nên làm sạch khi việc đó an toàn; sau đó hãy để khô và xác minh nơi tiếp nhận. {action}'
    )
    reduce_waste = (
        'Bạn có thể giảm lượng rác hữu cơ bằng cách dùng vừa đủ thực phẩm và tách phần còn lại cho tuyến thu gom hữu cơ phù hợp.'
        if category == 'organic' else
        f'Nếu {name.lower()} còn sạch và an toàn để dùng lại, bạn có thể kéo dài thời gian sử dụng trước khi bỏ đi.'
        if object_id in REUSABLE_IDS else
        f'Bạn có thể giảm phát sinh {name.lower()} bằng cách chọn đồ dùng bền hoặc dùng lượng vừa đủ khi có thể.'
    )
    guidance = {
        'headline': f'Bạn đang xem hướng dẫn cho {name.lower()}',
        'assessment': f'Mình sẽ giúp bạn xem cách xử lý {name.lower()} theo tình trạng thực tế. {caution}',
        'default_action': action,
        'end_of_use': f'Khi không còn sử dụng {name.lower()}, bạn hãy giữ riêng món đồ và xác minh tuyến tiếp nhận tại địa phương.',
        'why': f'Mình gợi ý như vậy vì vật liệu, mức bẩn và cách thu gom của {name.lower()} có thể khác nhau giữa các nơi. {caution}',
        'explanation': caution,
        'default_caution': avoid,
        'condition_responses': condition_responses,
        'contamination_responses': {
            'clean': f'Bạn cho biết {name.lower()} không dính chất lạ. {action}',
            'food': food_response,
            'hazardous': f'Nếu {name.lower()} có thể dính hóa chất hoặc chất không rõ, bạn đừng tự rửa hay đưa vào dòng tái chế thông thường. Hãy hỏi đơn vị có thẩm quyền.',
            'unknown': f'Nếu chưa rõ {name.lower()} đã dính chất gì, bạn hãy giữ riêng và xác minh trước khi xử lý.',
        },
        'practical_steps': [
            {'label':'Kiểm tra', 'text':f'Bạn hãy xác nhận chất liệu, tình trạng và mức bẩn của {name.lower()}.'},
            {'label':'Xử lý', 'text':action},
            {'label':'Xác minh', 'text':'Bạn hãy hỏi nơi thu gom tại địa phương có tiếp nhận đúng loại vật này không.'},
        ],
        'safety': {
            'Nếu có vật sắc, hóa chất, mốc nặng hoặc chất bẩn không rõ': f'Nếu {name.lower()} có dấu hiệu nguy hiểm hoặc chất bẩn không rõ, bạn hãy dừng thao tác và hỏi đơn vị có thẩm quyền.',
            'Vì sao cần lưu ý': caution,
            'Tuyệt đối tránh / Không tự suy diễn': avoid,
            'Phạm vi': 'Đây là hướng dẫn chung; chưa xác minh điểm tiếp nhận tại địa phương.',
        },
        'reduce_waste': reduce_waste,
        'no_collection': f'Nếu nơi thu gom không nhận {name.lower()}, bạn hãy hỏi đơn vị quản lý chất thải tại địa phương về tuyến phù hợp; đừng tự khẳng định món đồ được tái chế.',
        'source_limit': 'Các nguồn chỉ hỗ trợ nguyên tắc chung; địa phương có thể áp dụng cách thu gom khác.',
    }
    response_row = dict(id=object_id, name_vi=name, category_id=category, aliases_vi=aliases,
        default_stream=stream, question_ids=questions, risk_profile='ordinary_conditional',
        response_policy='xử lý theo tình trạng thực tế; xác minh nơi tiếp nhận địa phương',
        source_ids=source_ids, evidence_status=evidence, review_status='pending_human_review',
        guidance=guidance, human_review_requirement='required_before_public_release')
    return kb_row, response_row

def main():
    kb = json.loads(KB_PATH.read_text(encoding='utf-8'))
    response = json.loads(RESPONSE_PATH.read_text(encoding='utf-8'))
    assert len(ITEMS) == 35
    kb_positions = {item['id']: index for index, item in enumerate(kb['objects'])}
    response_positions = {item['id']: index for index, item in enumerate(response['objects'])}
    for row in ITEMS:
        kb_row, response_row = make_rows(row)
        object_id = row[0]
        if (object_id in kb_positions) != (object_id in response_positions):
            raise ValueError(f'{object_id} exists in only one catalog')
        if object_id in kb_positions:
            kb['objects'][kb_positions[object_id]] = kb_row
            response['objects'][response_positions[object_id]] = response_row
        else:
            kb['objects'].append(kb_row)
            response['objects'].append(response_row)
    kb['version'] = '2026-11-17.1'
    KB_PATH.write_text(json.dumps(kb, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    RESPONSE_PATH.write_text(json.dumps(response, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
