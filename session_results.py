#!/usr/bin/env python3
"""
今節成績抽出スクリプト（修正版）
"""

def extract_session_results(json_data):
    """今節成績を抽出"""
    session_results_list = []

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

        session_info = {
            '選手番号': player.get('player_no'),
            '選手名': player.get('player_name'),

            # 今節基本情報
            '順位': player.get('junban'),
            '得点率': player.get('tokutenritsu'),
            '今節スタート平均': player.get('konsetsu_start_ave'),
            '今節展示平均': player.get('konsetsu_display_ave'),

            # 前検情報
            '前検タイム': player.get('zenken_time'),
            '前検モーター順位': player.get('zenken_motor_junban'),
            '前検モーター番号': player.get('zenken_motor_no'),
            '前検モーター2連率': player.get('zenken_motor_niren'),
            '前検ボート番号': player.get('zenken_boat_no'),
            '前検ボート2連率': player.get('zenken_boat_niren'),

            # スタート平均関連（修正）
            'スタート平均': player.get('start_ave'),
            '1コーススタート平均': player.get('start1_ave'),
            '2コーススタート平均': player.get('start2_ave'),
            '3コーススタート平均': player.get('start3_ave'),
            '4コーススタート平均': player.get('start4_ave'),
            '5コーススタート平均': player.get('start5_ave'),
            '6コーススタート平均': player.get('start6_ave'),

            # ST順位関連
            'ST順位': player.get('st_junban'),
            '1コースST順位': player.get('st_junban_1'),
            '2コースST順位': player.get('st_junban_2'),
            '3コースST順位': player.get('st_junban_3'),
            '4コースST順位': player.get('st_junban_4'),
            '5コースST順位': player.get('st_junban_5'),
            '6コースST順位': player.get('st_junban_6'),

            # 勝率・連率（修正）
            '勝率': player.get('shoritsu'),
            '2連率': player.get('fukusho'),
            '3連率': player.get('sanren'),

            # 進入数
            '進入数': player.get('shinnyu'),
            '1コース進入数': player.get('course1_shinnyu'),
            '2コース進入数': player.get('course2_shinnyu'),
            '3コース進入数': player.get('course3_shinnyu'),
            '4コース進入数': player.get('course4_shinnyu'),
            '5コース進入数': player.get('course5_shinnyu'),
            '6コース進入数': player.get('course6_shinnyu'),

            # 各コース1着率
            '1コース1着率': player.get('course1_1_ave'),
            '2コース1着率': player.get('course2_1_ave'),
            '3コース1着率': player.get('course3_1_ave'),
            '4コース1着率': player.get('course4_1_ave'),
            '5コース1着率': player.get('course5_1_ave'),
            '6コース1着率': player.get('course6_1_ave'),

            # 展示成績
            '展示順位平均_直近2節': player.get('display_junban_ave_choku2'),
            '展示順位平均_直近3節': player.get('display_junban_ave_choku3'),

            # 波高別成績
            '波5cm進入数': player.get('nami5_shinnyuu'),
            '波5cm1着率': player.get('nami5_rank1'),
            '波5cm2着率': player.get('nami5_rank2'),
            '波5cm3着率': player.get('nami5_rank3'),
        }

        session_results_list.append(session_info)

    return session_results_list

if __name__ == "__main__":
    # テスト用
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        result = extract_session_results(test_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("使用方法: python session_results.py [JSONファイルパス]")