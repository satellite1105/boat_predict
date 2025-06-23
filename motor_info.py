#!/usr/bin/env python3
"""
モーター情報抽出スクリプト（修正版）
"""

def extract_motor_info(json_data):
    """モーター情報を抽出"""
    motor_info_list = []

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

        motor_info = {
            '選手番号': player.get('player_no'),
            '選手名': player.get('player_name'),

            # 基本機械情報
            'モーター番号': player.get('motor'),
            'ボート番号': player.get('boat'),

            # 通算成績
            'モーター2連率': player.get('motor_niren'),
            'ボート2連率': player.get('boat_niren'),
            'モーター3連率': player.get('motor_sanren'),
            'ボート3連率': player.get('boat_sanren'),

            # モーター詳細成績（当期）
            'モーター期間開始': player.get('motor_kikan_start'),
            'モーター期間終了': player.get('motor_kikan_end'),
            'モーター出走数': player.get('motor_shusso'),
            'モーター優出数': player.get('motor_yushutsu'),
            'モーター優勝数': player.get('motor_yusho'),
            'モーター1着数': player.get('motor_one'),
            'モーター2着数': player.get('motor_two'),
            'モーター3着数': player.get('motor_three'),
            'モーター勝率': player.get('motor_shoritsu'),
            'モーター2連率詳細': player.get('motor_niren_shoritsu'),
            'モーター3連率詳細': player.get('motor_sanren_shoritsu'),
            '2連率順位': player.get('niren_shourisuu_rank'),

            # 全期間モーター成績
            'モーター期間開始_全期間': player.get('motor_kikan_start_all'),
            'モーター期間終了_全期間': player.get('motor_kikan_end_all'),
            'モーター出走数_全期間': player.get('motor_shusso_all'),
            'モーター優出数_全期間': player.get('motor_yushutsu_all'),
            'モーター優勝数_全期間': player.get('motor_yusho_all'),
            'モーター勝率_全期間': player.get('motor_shoritsu_all'),
            'モーター2連率_全期間': player.get('motor_niren_shoritsu_all'),
            'モーター3連率_全期間': player.get('motor_sanren_shoritsu_all'),

            # モーター指数・ランク
            'モーター指数': player.get('motor_shisuu'),
            'モーター1着率': player.get('motor_rank1'),
            'モーター展示順位平均': player.get('motor_display_junban_ave'),
            'モーターランク平均': player.get('motor_rank_ave'),

            # 前検情報
            '前検モーター順位': player.get('zenken_motor_junban'),
            '前検モーター番号': player.get('zenken_motor_no'),
            '前検モーター2連率': player.get('zenken_motor_niren'),
            '前検ボート番号': player.get('zenken_boat_no'),
            '前検ボート2連率': player.get('zenken_boat_niren'),
            '前検タイム': player.get('zenken_time'),

            # 波高別成績
            '波5cm進入数': player.get('nami5_shinnyuu'),
            '波5cm1着率': player.get('nami5_rank1'),
            '波5cm2着率': player.get('nami5_rank2'),
            '波5cm3着率': player.get('nami5_rank3'),
        }

        motor_info_list.append(motor_info)

    return motor_info_list

if __name__ == "__main__":
    # テスト用
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        result = extract_motor_info(test_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("使用方法: python motor_info.py [JSONファイルパス]")