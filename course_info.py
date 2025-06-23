#!/usr/bin/env python3
"""
枠別情報抽出スクリプト（修正版）
"""

def extract_course_info(json_data):
    """枠別情報を抽出"""
    course_info_list = []

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

        # 基本情報
        course_data = {
            '選手番号': player.get('player_no'),
            '選手名': player.get('player_name'),
            '総進入回数': player.get('shinnyu_kaisu'),
        }

        # 各コース（1-6）の詳細データ
        for course_num in range(1, 7):
            prefix = f'course{course_num}_'
            # 基本成績
            course_data.update({
                f'{course_num}コース進入回数': player.get(f'{prefix}shinnyu'),
                f'{course_num}コース1着率': player.get(f'{prefix}1_ave'),
                f'{course_num}コース2着率': player.get(f'{prefix}2_ave'),
                f'{course_num}コース3着率': player.get(f'{prefix}3_ave'),
                f'{course_num}コース2着内率': player.get(f'{prefix}2_chaku'),
                f'{course_num}コース3着内率': player.get(f'{prefix}3_chaku'),
            })

            # スタート情報
            course_data.update({
                f'{course_num}コーススタート平均': player.get(f'start{course_num}_ave'),
                f'{course_num}コース平均ST順位': player.get(f'st_junban_{course_num}'),
            })

            # 決まり手情報
            if course_num == 1:
                # 1コースの決まり手
                course_data.update({
                    f'{course_num}コース逃げ率': player.get(f'{prefix}nigeritsu'),
                    f'{course_num}コース差され率': player.get(f'{prefix}sasare'),
                    f'{course_num}コースまくられ率': player.get(f'{prefix}makurare'),
                    f'{course_num}コースまくられ差し率': player.get(f'{prefix}makuraresashi'),
                })
            else:
                # 2-6コースの決まり手
                course_data.update({
                    f'{course_num}コース差し率': player.get(f'{prefix}sashi'),
                    f'{course_num}コースまくり率': player.get(f'{prefix}makuri'),
                    f'{course_num}コースまくり差し率': player.get(f'{prefix}makurisashi'),
                })

                # 2コースのみ逃がし率
                if course_num == 2:
                    course_data[f'{course_num}コース逃がし率'] = player.get(f'{prefix}nigashi')

            # 期間別成績（直近1節、2節、3節、6節、当地）
            periods = ['_choku1', '_choku2', '_choku3', '_choku6', '_tochi']
            period_names = ['直近1節', '直近2節', '直近3節', '直近6節', '当地']

            for period, period_name in zip(periods, period_names):
                course_data.update({
                    f'{course_num}コース進入回数_{period_name}': player.get(f'{prefix}shinnyu{period}'),
                    f'{course_num}コース1着率_{period_name}': player.get(f'{prefix}1_ave{period}'),
                    f'{course_num}コース2着率_{period_name}': player.get(f'{prefix}2_ave{period}'),
                    f'{course_num}コース3着率_{period_name}': player.get(f'{prefix}3_ave{period}'),
                    f'{course_num}コース2着内率_{period_name}': player.get(f'{prefix}2_chaku{period}'),
                    f'{course_num}コース3着内率_{period_name}': player.get(f'{prefix}3_chaku{period}'),
                })

            # SG/G1・一般戦・女子戦別成績
            race_types = ['_sg', '_nomal', '_woman']
            type_names = ['SG/G1', '一般戦', '女子戦']

            for race_type, type_name in zip(race_types, type_names):
                course_data.update({
                    f'{course_num}コース進入回数_{type_name}': player.get(f'{prefix}shinnyu{race_type}'),
                    f'{course_num}コース1着率_{type_name}': player.get(f'{prefix}1_ave{race_type}'),
                    f'{course_num}コース2着率_{type_name}': player.get(f'{prefix}2_ave{race_type}'),
                    f'{course_num}コース3着率_{type_name}': player.get(f'{prefix}3_ave{race_type}'),
                    f'{course_num}コース2着内率_{type_name}': player.get(f'{prefix}2_chaku{race_type}'),
                    f'{course_num}コース3着内率_{type_name}': player.get(f'{prefix}3_chaku{race_type}'),
                })

            # 勝率情報
            course_data[f'{course_num}コース勝率'] = player.get(f'course{course_num}_shoritsu')

        # 全体スタート情報
        course_data.update({
            '全体スタート平均': player.get('start_ave'),
            '全体ST順位平均': player.get('st_junban'),
            '進入平均コース': player.get('shinnyu_ave'),
        })

        # 期間別全体成績
        periods = ['', '_choku1', '_choku2', '_choku3', '_choku6', '_tochi']
        period_names = ['全期間', '直近1節', '直近2節', '直近3節', '直近6節', '当地']

        for period, period_name in zip(periods, period_names):
            course_data.update({
                f'総進入回数_{period_name}': player.get(f'shinnyu{period}'),
                f'勝率_{period_name}': player.get(f'shoritsu{period}'),
                f'2連率_{period_name}': player.get(f'fukusho{period}'),
                f'3連率_{period_name}': player.get(f'sanren{period}'),
                f'スタート平均_{period_name}': player.get(f'start_ave{period}'),
                f'ST順位平均_{period_name}': player.get(f'st_junban{period}'),
            })

        # レースタイプ別全体成績
        race_types = ['_sg', '_nomal', '_woman']
        type_names = ['SG/G1', '一般戦', '女子戦']

        for race_type, type_name in zip(race_types, type_names):
            course_data.update({
                f'総進入回数_{type_name}': player.get(f'shinnyu{race_type}'),
                f'勝率_{type_name}': player.get(f'shoritsu{race_type}'),
                f'2連率_{type_name}': player.get(f'fukusho{race_type}'),
                f'3連率_{type_name}': player.get(f'sanren{race_type}'),
                f'スタート平均_{type_name}': player.get(f'start_ave{race_type}'),
                f'ST順位平均_{type_name}': player.get(f'st_junban{race_type}'),
            })

        # 決まり手関連の詳細情報
        for course_num in range(1, 7):
            # 期間別決まり手
            periods = ['_choku12']
            period_names = ['直近12']

            for period, period_name in zip(periods, period_names):
                if course_num == 1:
                    course_data.update({
                        f'{course_num}コース逃げ率_{period_name}': player.get(f'course{course_num}_nigeritsu{period}'),
                        f'{course_num}コース差され率_{period_name}': player.get(f'course{course_num}_sasare{period}'),
                        f'{course_num}コースまくられ率_{period_name}': player.get(f'course{course_num}_makurare{period}'),
                        f'{course_num}コースまくられ差し率_{period_name}': player.get(f'course{course_num}_makuraresashi{period}'),
                    })
                else:
                    course_data.update({
                        f'{course_num}コース差し率_{period_name}': player.get(f'course{course_num}_sashi{period}'),
                        f'{course_num}コースまくり率_{period_name}': player.get(f'course{course_num}_makuri{period}'),
                        f'{course_num}コースまくり差し率_{period_name}': player.get(f'course{course_num}_makurisashi{period}'),
                    })

                if course_num == 2:
                    course_data[f'{course_num}コース逃がし率_{period_name}'] = player.get(f'course{course_num}_nigashi{period}')

        # 逃がし関連の詳細データ
        for course_num in range(2, 7):
            course_data.update({
                f'{course_num}コース2着逃がし': player.get(f'course{course_num}_2_nigashi'),
                f'{course_num}コース3着逃がし': player.get(f'course{course_num}_3_nigashi'),
                f'{course_num}コース2着逃がし進入数': player.get(f'course{course_num}_2_nigashi_shinnyuu'),
                f'{course_num}コース3着逃がし回数': player.get(f'course{course_num}_3_nigashi_count'),
            })

            # 期間別逃がしデータ
            periods = ['_choku12']
            for period in periods:
                course_data.update({
                    f'{course_num}コース2着逃がし進入数{period}': player.get(f'course{course_num}_2_nigashi_shinnyuu{period}'),
                    f'{course_num}コース3着逃がし回数{period}': player.get(f'course{course_num}_3_nigashi_count{period}'),
                })

        course_info_list.append(course_data)

    return course_info_list

if __name__ == "__main__":
    # テスト用
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        result = extract_course_info(test_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("使用方法: python course_info.py [JSONファイルパス]")