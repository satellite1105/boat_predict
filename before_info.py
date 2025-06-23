#!/usr/bin/env python3
"""
直前情報抽出スクリプト（request_chokuzen_info_v2.php対応・展示順位計算付き・完全版）
"""

def extract_before_info(json_data):
    """直前情報を抽出（新API対応・展示順位計算付き）"""
    before_info_list = []

    # まず展示タイムを取得して展示順位を計算
    display_times = {}
    for player in json_data:
        if isinstance(player, dict) and player.get('player_no'):
            course = player.get('course')
            display_time = player.get('display')
            if course and display_time:
                try:
                    # 展示タイムを数値に変換
                    display_times[course] = float(display_time)
                except (ValueError, TypeError):
                    pass
    
    # 展示順位を計算（タイムが速い順）
    display_ranks = {}
    if display_times:
        sorted_times = sorted(display_times.items(), key=lambda x: x[1])
        for rank, (course, time) in enumerate(sorted_times, 1):
            display_ranks[course] = rank

    for i, player in enumerate(json_data):
        # 各プレイヤーが辞書であることを確認
        if not isinstance(player, dict):
            print(f"Warning: Player {i} is {type(player)}, expected dict. Skipping...")
            continue

        # player_noが存在しない場合もスキップ
        if not player.get('player_no'):
            print(f"Player {i}: player_noがないデータをスキップ")
            continue

        course = player.get('course')
        display_time = player.get('display')
        display_rank = display_ranks.get(course, None)

        # 展示タイムを数値に変換
        try:
            display_time_float = float(display_time) if display_time else None
        except (ValueError, TypeError):
            display_time_float = None

        before_info = {
            # 基本情報
            '選手番号': player.get('player_no'),
            '選手名': player.get('name'),
            '選手名カナ': player.get('name_kana'),
            'コース': course,
            '進入': player.get('shinnyuu'),

            # 展示情報（数値統一版）
            '展示タイム': display_time_float,                       # 6.80 形式（数値のみ）
            '展示順位': display_rank,                              # 1, 2, 3... (計算値)
            '展示スタートタイミング': player.get('start'),           # ".09" 形式
            '体重': player.get('taiju'),                           # "52.5kg" 形式
            'チルト': player.get('chiruto'),                       # "-0.5" 形式
            '調整重量': player.get('tyousei'),                     # "0.0" 形式

            # 詳細展示データ（APIから取得可能な場合）
            '展示_生データ': player.get('tenji'),                   # 680 (展示タイム x100?)
            '周回_生データ': player.get('shukai'),                  # 3745 (周回タイム x100?)
            '回り足_生データ': player.get('mawariashi'),            # 567 (回り足タイム x100?)
            '直線_生データ': player.get('chokusen'),               # 680 (直線タイム x100?)

            # 時間変換（推定：÷100）
            '周回タイム': round(player.get('shukai', 0) / 100, 2) if player.get('shukai') else None,     # 37.45秒
            '回り足タイム': round(player.get('mawariashi', 0) / 100, 2) if player.get('mawariashi') else None,  # 5.67秒
            '直線タイム': round(player.get('chokusen', 0) / 100, 2) if player.get('chokusen') else None,       # 6.80秒

            # 選手コメント
            'コメント': player.get('comment'),

            # レース環境情報
            '気温': player.get('kion'),                            # "19.0℃"
            '天候': player.get('weather'),                         # "曇り"
            '風速': player.get('wind_speed'),                      # "0m"
            '風向きアイコン': player.get('wind'),                  # "/img/icon_wind1_17.png"
            '水温': player.get('suion'),                           # "20.0℃"
            '波高': player.get('wave'),                            # "0cm"

            # プロペラ・交換情報
            'プロペラ': player.get('propera'),                     # プロペラ情報
            '交換': player.get('koukan'),                          # 交換情報

            # その他の情報
            '選手画像': player.get('image'),                       # "/player/4579.jpg"
            '性別': player.get('seibetsu'),                        # 1: 男性, 2: 女性

            # レース詳細情報
            '場所番号': player.get('place_no'),
            'レース番号': player.get('race_no'),
            '日付': player.get('hiduke'),

            # 潮汐情報
            '満潮1_高さ': player.get('mancho1_takasa'),
            '満潮1_時間': player.get('mancho1_jikan'),
            '干潮1_時間': player.get('kancho1_jikan'),
            '干潮1_高さ': player.get('kancho1_takasa'),
            '満潮2_高さ': player.get('mancho2_takasa'),
            '満潮2_時間': player.get('mancho2_jikan'),
            '干潮2_時間': player.get('kancho2_jikan'),
            '干潮2_高さ': player.get('kancho2_takasa'),
            '潮': player.get('shio'),

            # その他のデータ
            'スロー_ダッシュ': player.get('slow_dash'),
        }

        before_info_list.append(before_info)

    return before_info_list

def calculate_display_rankings(json_data):
    """展示タイムから展示順位を計算する補助関数"""
    display_times = []
    
    for player in json_data:
        if isinstance(player, dict) and player.get('player_no'):
            course = player.get('course')
            display_time = player.get('display')
            player_no = player.get('player_no')
            
            if course and display_time and player_no:
                try:
                    time_float = float(display_time)
                    display_times.append({
                        'course': course,
                        'player_no': player_no,
                        'display_time': time_float
                    })
                except (ValueError, TypeError):
                    continue
    
    # タイム順にソート
    display_times.sort(key=lambda x: x['display_time'])
    
    # 順位を割り当て
    for rank, item in enumerate(display_times, 1):
        item['rank'] = rank
    
    return display_times

if __name__ == "__main__":
    # テスト用
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 展示順位計算の確認
        rankings = calculate_display_rankings(test_data)
        print("=== 展示順位計算結果 ===")
        for item in rankings:
            print(f"{item['rank']}位: {item['course']}コース (選手{item['player_no']}) - {item['display_time']}")
        
        print("\n=== 直前情報抽出結果 ===")
        result = extract_before_info(test_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("使用方法: python before_info.py [JSONファイルパス]")
