#!/usr/bin/env python3
"""
競艇データ取得メインスクリプト（直前情報API対応・完全版）
"""

import sys
import json
import requests
import time
import random
from datetime import datetime
import os
import subprocess

# 各情報抽出モジュールをインポート
from basic_info import extract_basic_info
from course_info import extract_course_info
from motor_info import extract_motor_info
from session_results import extract_session_results
from before_info import extract_before_info, calculate_display_rankings

# 会場名とコードのマッピング（琵琶湖・びわこ両対応）
STADIUM_CODES = {
    "桐生": 1, "戸田": 2, "江戸川": 3, "平和島": 4,
    "多摩川": 5, "浜名湖": 6, "蒲郡": 7, "常滑": 8,
    "津": 9, "三国": 10, "びわこ": 11, "琵琶湖": 11, "住之江": 12,
    "尼崎": 13, "鳴門": 14, "丸亀": 15, "児島": 16,
    "宮島": 17, "徳山": 18, "下関": 19, "若松": 20,
    "芦屋": 21, "福岡": 22, "唐津": 23, "大村": 24
}

def notify_mac(title, message):
    """macOSの通知センターに通知を送信"""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception as e:
        print(f"通知の送信に失敗しました: {e}")
        return False

def setup_directories(date_str):
    """データ保存用ディレクトリを作成"""
    try:
        os.makedirs("data/races", exist_ok=True)
        os.makedirs("data/racers", exist_ok=True)
        
        date_dir = f"data/races/{date_str}"
        os.makedirs(date_dir, exist_ok=True)
        
        racers_date_dir = f"data/racers/{date_str}"
        os.makedirs(racers_date_dir, exist_ok=True)
        
        print(f"ディレクトリ作成完了: {date_dir}, {racers_date_dir}")
        return date_dir, racers_date_dir
    except Exception as e:
        print(f"ディレクトリ作成エラー: {e}")
        return None, None

class KyoteiBiyoriScraper:
    def __init__(self):
        self.base_url = "https://kyoteibiyori.com/request_race_shusso_detail_v4.php"
        self.chokuzen_url = "https://kyoteibiyori.com/request_chokuzen_info_v2.php"
        self.session = requests.Session()
        
    def get_race_data(self, place_no, race_no, hiduke, mode=0):
        """競艇データを取得（基本・コース・モーター・今節成績用）"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://kyoteibiyori.com',
            'Referer': f'https://kyoteibiyori.com/race_shusso.php?place_no={place_no}&race_no={race_no}&hiduke={hiduke}&slider=1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        data = {
            'data': json.dumps({
                'place_no': place_no,
                'race_no': race_no,
                'hiduke': hiduke,
                'mode': mode
            })
        }
        
        try:
            time.sleep(random.uniform(1, 3))
            
            response = self.session.post(self.base_url, headers=headers, data=data)
            response.raise_for_status()
            
            json_data = response.json()
            
            if isinstance(json_data, dict):
                if 'race_list' in json_data:
                    race_list = json_data['race_list']
                    return race_list
                else:
                    return json_data
            else:
                return json_data
                
        except requests.exceptions.RequestException as e:
            print(f"リクエストエラー (mode={mode}): {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSONデコードエラー (mode={mode}): {e}")
            return None

    def get_chokuzen_data(self, place_no, race_no, hiduke):
        """直前情報を取得（新API）"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://kyoteibiyori.com',
            'Referer': f'https://kyoteibiyori.com/race_shusso.php?place_no={place_no}&race_no={race_no}&hiduke={hiduke}&slider=1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        data = {
            'data': json.dumps({
                'place_no': place_no,
                'race_no': race_no,
                'hiduke': hiduke
            })
        }
        
        try:
            time.sleep(random.uniform(1, 3))
            
            response = self.session.post(self.chokuzen_url, headers=headers, data=data)
            response.raise_for_status()
            
            json_data = response.json()
            
            return json_data
                
        except requests.exceptions.RequestException as e:
            print(f"直前情報リクエストエラー: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"直前情報JSONデコードエラー: {e}")
            return None

def get_stadium_code(stadium_name):
    """会場名から会場コードを取得（琵琶湖・びわこ両対応）"""
    if stadium_name in STADIUM_CODES:
        return STADIUM_CODES[stadium_name]
    else:
        # エラーメッセージで対応会場名を表示
        available_stadiums = list(STADIUM_CODES.keys())
        raise ValueError(f"無効な会場名: {stadium_name}\n利用可能な会場名: {', '.join(available_stadiums)}")

def main():
    """メイン処理"""
    if len(sys.argv) != 4:
        print("使用方法: python main.py [日付] [会場名] [レース番号]")
        print("例: python main.py 20250530 戸田 1")
        print("例: python main.py 20250530 琵琶湖 1")
        print("例: python main.py 20250530 びわこ 1")
        sys.exit(1)
    
    # 引数を解析
    hiduke = sys.argv[1]
    stadium_name = sys.argv[2]
    race_no = int(sys.argv[3])
    
    try:
        # 会場コードを取得（琵琶湖・びわこ両対応）
        place_no = get_stadium_code(stadium_name)
        
        print(f"=== 競艇データ取得開始 ===")
        print(f"日付: {hiduke}, 会場: {stadium_name} (コード: {place_no}), レース: {race_no}R")
        
        # ディレクトリ構造をセットアップ
        date_dir, racers_date_dir = setup_directories(hiduke)
        if not date_dir:
            print("ディレクトリの作成に失敗しました")
            sys.exit(1)
        
        # データ取得
        scraper = KyoteiBiyoriScraper()
        
        print("\n=== 基本データ取得 ===")
        basic_raw_data = scraper.get_race_data(place_no, race_no, hiduke, mode=0)
        
        if not basic_raw_data:
            print("基本データの取得に失敗しました")
            sys.exit(1)
        
        print(f"✓ 基本データを取得: {len(basic_raw_data)}件")
        
        # 直前情報を取得（新API）
        print("\n=== 直前情報取得 ===")
        chokuzen_raw_data = scraper.get_chokuzen_data(place_no, race_no, hiduke)
        
        if chokuzen_raw_data:
            print(f"✓ 直前情報を取得: {len(chokuzen_raw_data)}件")
            
            # 展示順位の確認表示
            rankings = calculate_display_rankings(chokuzen_raw_data)
            print("展示順位:")
            for item in rankings:
                print(f"  {item['rank']}位: {item['course']}コース - {item['display_time']}")
        else:
            print("⚠️  直前情報の取得に失敗しました（基本データから代替抽出します）")
        
        # 各種情報を抽出
        print("\n=== 情報抽出開始 ===")
        
        final_data = {
            "race_info": {
                "date": hiduke,
                "stadium": stadium_name,
                "stadium_code": place_no,
                "race_no": race_no,
                "generated_at": datetime.now().isoformat()
            }
        }
        
        # 基本情報を抽出
        print("基本情報を抽出中...")
        if isinstance(basic_raw_data, list) and len(basic_raw_data) > 0:
            basic_data = extract_basic_info(basic_raw_data)
            final_data['basic_info'] = basic_data
            print(f"✓ 基本情報: {len(basic_data)}名分を抽出")
        else:
            print("✗ 基本情報: データ形式が無効")
            sys.exit(1)
        
        # 枠別情報を抽出
        print("枠別情報を抽出中...")
        course_data = extract_course_info(basic_raw_data)
        final_data['course_info'] = course_data
        print(f"✓ 枠別情報: {len(course_data)}名分を抽出")
        
        # モーター情報を抽出
        print("モーター情報を抽出中...")
        motor_data = extract_motor_info(basic_raw_data)
        final_data['motor_info'] = motor_data
        print(f"✓ モーター情報: {len(motor_data)}名分を抽出")
        
        # 今節成績を抽出（別モードのデータ使用）
        print("今節成績を取得中...")
        session_raw_data = scraper.get_race_data(place_no, race_no, hiduke, mode=3)
        
        if session_raw_data and isinstance(session_raw_data, list):
            session_data = extract_session_results(session_raw_data)
            final_data['session_results'] = session_data
            print(f"✓ 今節成績: {len(session_data)}名分を抽出")
        else:
            print("⚠️  今節成績データが取得できません（基本データから代替抽出）")
            session_data = extract_session_results(basic_raw_data)
            final_data['session_results'] = session_data
            print(f"✓ 今節成績（基本データから）: {len(session_data)}名分を抽出")
        
        # 直前情報を抽出（新API使用）
        print("直前情報を抽出中...")
        if chokuzen_raw_data and isinstance(chokuzen_raw_data, list):
            before_data = extract_before_info(chokuzen_raw_data)
            final_data['before_info'] = before_data
            print(f"✓ 直前情報: {len(before_data)}名分を抽出")
        else:
            print("⚠️  直前情報データが取得できません（基本データから代替抽出）")
            before_data = extract_before_info(basic_raw_data)
            final_data['before_info'] = before_data
            print(f"✓ 直前情報（基本データから）: {len(before_data)}名分を抽出")
        
        # JSONファイルに保存
        filename = f"{date_dir}/{hiduke}_{stadium_name}_{race_no}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        # 完了ログ
        file_size = os.path.getsize(filename)
        print(f"\n=== 完了 ===")
        print(f"ファイル名: {filename}")
        print(f"ファイルサイズ: {file_size} bytes")
        
        # 統計情報
        total_data_count = 0
        for section_name, section_data in final_data.items():
            if section_name != 'race_info' and isinstance(section_data, list):
                total_data_count += len(section_data)
                print(f"{section_name}: {len(section_data)}名分")
        
        print(f"合計データ数: {total_data_count}件")
        print("データ取得が完了しました！")
        
        # Mac通知機能
        notify_mac("データ取得完了", f"処理が完了しました: {stadium_name} {race_no}R {hiduke}")
        
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
        # エラー時も通知
        notify_mac("データ取得エラー", f"エラーが発生しました: {stadium_name} {race_no}R {hiduke}")
        sys.exit(1)

if __name__ == "__main__":
    main()
