#!/usr/bin/env python3
"""
基本情報抽出スクリプト（結果データ完全削除・完全版）
"""

def extract_basic_info(json_data):
    """基本情報を抽出（結果データ完全削除版）"""
    # データ形式の検証
    if not isinstance(json_data, list):
        print(f"Warning: extract_basic_info received {type(json_data)}, expected list")
        if isinstance(json_data, dict):
            json_data = [json_data]
        else:
            return []

    basic_info_list = []

    for i, player in enumerate(json_data):
        # 各プレイヤーが辞書であることを確認
        if not isinstance(player, dict):
            print(f"Warning: Player {i} is {type(player)}, expected dict. Skipping...")
            continue

        # 数値キーのデータ（配列形式）をスキップ
        if player and isinstance(list(player.keys())[0], int):
            print(f"Player {i}: 数値キー形式のデータをスキップ")
            continue

        # player_noが存在しない場合もスキップ
        if not player.get('player_no'):
            print(f"Player {i}: player_noがないデータをスキップ")
            continue

        basic_info = {
            # 選手基本情報
            '選手番号': player.get('player_no'),
            '選手名': player.get('player_name'),
            '選手名カナ': player.get('name_kana'),
            '年齢': player.get('age'),
            '支部': player.get('shibu'),
            '出身': player.get('shusshin'),
            '級別': player.get('kyubetsu'),
            '養成期間': player.get('yousei_kikan'),
            '体重': player.get('taiju'),
            '性別': player.get('seibetsu'),

            # 【削除：コース、順位、周回タイム、スタート平均】

            # レース情報
            'レース年': player.get('race_year'),
            'レース名': player.get('race_name'),
            '場所番号': player.get('place_no'),
            'レース番号': player.get('race_no'),
            'レース日付': player.get('hiduke'),
            'レースランク': player.get('race_rank'),
            'グレード': player.get('grade'),

            # 全国成績
            '全国勝率': player.get('zenkoku_shoritsu'),
            '全国2連率': player.get('zenkoku_niren'),
            '全国3連率': player.get('zenkoku_sanren'),

            # 当地成績
            '当地勝率': player.get('touchi_shoritsu'),
            '当地2連率': player.get('touchi_niren'),
            '当地3連率': player.get('touchi_sanren'),

            # 機械情報
            'モーター番号': player.get('motor'),
            'ボート番号': player.get('boat'),
            'モーター2連率': player.get('motor_niren'),
            'ボート2連率': player.get('boat_niren'),
            'モーター3連率': player.get('motor_sanren'),
            'ボート3連率': player.get('boat_sanren'),

            # 過去スタート情報（結果ではない平均データ）
            '平均スタート': player.get('ave_start'),                # "015" 形式（過去平均）
            'スタート順位': player.get('ave_start_rank'),           # "260" 形式（過去平均順位）

            # 能力指数・得点
            '前期能力指数': player.get('zenki_nouryoku_shisuu'),
            '今期能力指数': player.get('konki_nouryoku_shisuu'),
            '得点率': player.get('tokutenritsu'),
            '最近勝率': player.get('saikin_shoritsu'),

            # フライング・事故情報
            'フライング': player.get('flying'),
            '事故点': player.get('jiko_ten'),
            '事故率': player.get('jiko_ritsu'),
            '遅れ0': player.get('late0'),
            '遅れ1': player.get('late1'),
            '欠場0': player.get('ketsujo0'),
            '欠場1': player.get('ketsujo1'),
            '失格0': player.get('shikkaku0'),
            '失格1': player.get('shikkaku1'),
            '失格2': player.get('shikkaku2'),

            # 勝数・着順情報
            '1着回数': player.get('kaisuuOne'),
            '2着回数': player.get('kaisuuTwo'),
            '3着回数': player.get('kaisuuThree'),
            '4着回数': player.get('kaisuuFour'),
            '5着回数': player.get('kaisuuFive'),
            '6着回数': player.get('kaisuuSix'),
            '1着総数': player.get('rank1_count'),
            '準優出回数': player.get('junyu_count'),
            '優出回数': player.get('yushutsu_count'),
            '優勝回数': player.get('yusho_count'),

            # 決まり手
            '決まり手_逃げ': player.get('kimete_nige'),
            '決まり手_差し': player.get('kimete_sashi'),
            '決まり手_捲り': player.get('kimete_makuri'),
            '決まり手_捲り差し': player.get('kimete_makurisashi'),
            '決まり手_抜き': player.get('kimete_nuki'),
            '決まり手_恵まれ': player.get('kimete_megumare'),

            # 早見番号と進入
            '早見': player.get('hayami'),
            '進入': player.get('shinnyuu'),

            # 成績（文字列形式）
            '成績1': player.get('seiseki1'),
            '成績2': player.get('seiseki2'),
            '成績3': player.get('seiseki3'),
            '成績4': player.get('seiseki4'),
            '成績5': player.get('seiseki5'),
            '成績6': player.get('seiseki6'),

            # 福勝関連
            '福勝': player.get('fukusho'),
            '過去福勝': player.get('kako_fukusho'),
            '過去3連': player.get('kako_sanren'),

            # 波高別成績
            '波5cm進入数': player.get('nami5_shinnyuu'),
            '波5cm1着率': player.get('nami5_rank1'),
            '波5cm2着率': player.get('nami5_rank2'),
            '波5cm3着率': player.get('nami5_rank3'),

            # チルト情報
            'チルト': player.get('chiruto'),

            # 進入平均
            '進入平均': player.get('shinnyu_ave'),

            # 今節情報
            '今節スタート平均': player.get('konsetsu_start_ave'),
            '今節展示平均': player.get('konsetsu_display_ave'),
            '順番': player.get('junban'),
        }

        basic_info_list.append(basic_info)

    return basic_info_list

if __name__ == "__main__":
    # テスト用
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        result = extract_basic_info(test_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("使用方法: python basic_info.py [JSONファイルパス]")
