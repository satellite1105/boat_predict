#!/usr/bin/env python3

"""
ボートレース情報取得スクリプト
【注意】
ボートレース公式サイト(boatrace.jp)の利用規約に従って使用してください。
特に以下の禁止事項に留意してください：
「5.不正アクセス、大量の情報送受信及び大量のアクセスなど、本サイトの運営に支障を与える行為」
このスクリプトは適切な待機時間とキャッシュ機能を実装し、サーバーに負荷をかけないよう設計されています。
"""

import requests
from bs4 import BeautifulSoup
import sys
import re
import pandas as pd
from tabulate import tabulate
import traceback
import json
import time
from datetime import datetime
import os
import subprocess # Mac通知用
import random # ランダム待機用
import hashlib # URLハッシュ用

# 会場名とコードのマッピング
STADIUM_CODES = {
    "桐生": "01", "戸田": "02", "江戸川": "03", "平和島": "04",
    "多摩川": "05", "浜名湖": "06", "蒲郡": "07", "常滑": "08",
    "津": "09", "三国": "10", "びわこ": "11", "住之江": "12",
    "尼崎": "13", "鳴門": "14", "丸亀": "15", "児島": "16",
    "宮島": "17", "徳山": "18", "下関": "19", "若松": "20",
    "芦屋": "21", "福岡": "22", "唐津": "23", "大村": "24",
}

# サーバー負荷対策の設定 - 公式サイト禁止事項「5.不正アクセス...」に対応
ACCESS_INTERVAL_MIN = 1  # 最小待機時間（秒）
ACCESS_INTERVAL_MAX = 3  # 最大待機時間（秒）
CACHE_DURATION = 3600    # キャッシュの有効期間（秒）

# URLキャッシュ（メモリ）
URL_CACHE = {}

def notify_mac(title, message):
    """macOSの通知センターに通知を送信"""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception as e:
        print(f"通知の送信に失敗しました: {e}")
        return False

def get_stadium_code(stadium):
    """会場名または会場コードから会場コードを取得"""
    if stadium in STADIUM_CODES.keys():
        return STADIUM_CODES[stadium]
    elif stadium in STADIUM_CODES.values():
        return stadium
    else:
        print(f"エラー: 無効な会場名または会場コード '{stadium}'")
        print("有効な会場名:", ", ".join(STADIUM_CODES.keys()))
        sys.exit(1)

def get_new_session():
    """新しいセッションを作成"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://www.boatrace.jp/",
        "Upgrade-Insecure-Requests": "1"
    })
    return session

def fetch_with_backoff(url, headers, max_retries=3, debug=False):
    """バックオフ戦略でリクエストを送信する関数
    ボートレース公式サイトの禁止事項「5.不正アクセス、大量の情報送受信及び大量のアクセスなど、
    本サイトの運営に支障を与える行為」に違反しないよう、以下の対策を実装:
    - ランダムな待機時間（1〜3秒）
    - リクエスト失敗時の指数関数的バックオフ
    - 新しいセッションの使用
    """
    for attempt in range(max_retries):
        try:
            # ランダムな待機時間（1〜3秒）- boatrace.jpの負荷軽減のため
            wait_time = ACCESS_INTERVAL_MIN + random.random() * (ACCESS_INTERVAL_MAX - ACCESS_INTERVAL_MIN)
            if debug:
                print(f"アクセス前に{wait_time:.1f}秒待機します...")
            time.sleep(wait_time)
            
            # 新しいセッションを取得して使用
            session = get_new_session()
            response = session.get(url)
            
            if response.status_code == 200:
                return response, 200
            elif response.status_code in [429, 503]:
                # エラーの場合、次の試行までの待機時間を指数関数的に増加
                backoff_time = (2 ** attempt) * 15  # boatrace.jpなのでバックオフ時間を短縮
                print(f"アクセス制限を検出（{response.status_code}）: {backoff_time}秒待機します")
                time.sleep(backoff_time)
            else:
                print(f"エラー: ステータスコード {response.status_code}")
                return None, response.status_code
        except Exception as e:
            print(f"リクエスト中にエラーが発生しました: {e}")
            time.sleep(15)
    
    print(f"最大試行回数（{max_retries}回）に達しました。アクセスできません。")
    return None, 0

def cached_request(url, headers, cache_time=3600, debug=False):
    """ファイルベースのキャッシュ付きリクエスト関数"""
    global URL_CACHE
    now = time.time()
    
    # キャッシュディレクトリを作成
    os.makedirs("cache", exist_ok=True)
    
    # URLからキャッシュファイル名を生成
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = f"cache/{url_hash}.json"
    
    # メモリキャッシュにあり、有効期限内ならキャッシュから返す
    if url in URL_CACHE and now - URL_CACHE[url]["time"] < cache_time:
        if debug:
            print(f"メモリキャッシュからデータを取得: {url}")
        return URL_CACHE[url]["response"], URL_CACHE[url]["status_code"]
    
    # ファイルキャッシュがあり、有効期限内ならファイルから読み込む
    if os.path.exists(cache_file):
        file_time = os.path.getmtime(cache_file)
        if (now - file_time) < cache_time:
            if debug:
                print(f"ファイルキャッシュからデータを取得: {url}")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                
                # 疑似レスポンスオブジェクトを作成
                class CachedResponse:
                    def __init__(self, text, status_code):
                        self.text = text
                        self.status_code = status_code
                        self.apparent_encoding = "utf-8"
                
                response = CachedResponse(cache_data["text"], cache_data["status_code"])
                
                # メモリキャッシュにも保存
                URL_CACHE[url] = {
                    "response": response,
                    "status_code": response.status_code,
                    "time": now
                }
                
                return response, response.status_code
            except Exception as e:
                print(f"キャッシュ読み込みエラー: {e}")
    
    # キャッシュがない場合、バックオフ戦略でリクエスト
    response, status_code = fetch_with_backoff(url, headers, debug=debug)
    
    # レスポンスが成功したらキャッシュに保存
    if response and status_code == 200:
        # メモリキャッシュに保存
        URL_CACHE[url] = {
            "response": response,
            "status_code": status_code,
            "time": now
        }
        
        # ファイルキャッシュに保存
        try:
            cache_data = {
                "text": response.text,
                "status_code": response.status_code,
                "url": url,
                "time": now
            }
            
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)
            
            if debug:
                print(f"キャッシュを保存しました: {cache_file}")
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    return response, status_code

def scrape_boatrace_data(jcd, rno, hd, debug=True, clipboard=False):
    """ボートレースの出走表と直前情報をスクレイピング"""
    # URLを構築
    race_list_url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={hd}"
    before_info_url = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={hd}"
    
    output = []
    output.append(f"出走表URL: {race_list_url}")
    output.append(f"直前情報URL: {before_info_url}")
    
    if debug:
        print(f"出走表URL: {race_list_url}")
        print(f"直前情報URL: {before_info_url}")
    
    # 出走表データを取得 - 修正:級別を確実に取得
    race_data = fetch_race_list_data(race_list_url, debug, output)
    
    # 直前情報データを取得 - 修正:展示タイム・ST・チルトを確実に取得
    before_data = fetch_before_info_data(before_info_url, debug, output)
    
    # デバッグ情報を表示
    if debug:
        print("\n=== 出走表データ ===")
        for i, player in enumerate(race_data):
            print(
                f"枠{player.get('枠', '?')}: 級別={player.get('級別', '不明')}, ボート番号={player.get('ボート番号', '不明')}, モーター番号={player.get('モーター番号', '不明')}"
            )
        
        print("\n=== 直前情報データ ===")
        for player in before_data.get("players", []):
            print(
                f"枠{player.get('枠', '?')}: 展示タイム={player.get('展示タイム', '不明')}, ST={player.get('ST', '不明')}, チルト={player.get('チルト', '不明')}"
            )
    
    # データ結合問題を診断
    if debug:
        diagnose_combination_issue(race_data, before_data)
    
    # データを結合 - 修正:データ結合の安定性向上
    combined_data = combine_data_fixed(race_data, before_data)
    
    # 最終データをデバッグ表示
    if debug:
        print("\n=== 最終結合データ ===")
        for player in combined_data["players"]:
            print(f"枠{player.get('枠', '?')}: {player.get('選手名', '不明')}, 級別={player.get('級別', '不明')}")
            print(
                f"  ボート番号: {player.get('ボート番号', '不明')}, ボート: {player.get('ボート', '不明')}"
            )
            print(
                f"  展示タイム: {player.get('展示タイム', '不明')}, ST: {player.get('ST', '不明')}, チルト: {player.get('チルト', '不明')}"
            )
    
    # 結果を表示・保存
    result_text = display_results(combined_data, output)
    
    # 必ず結果をターミナルに出力する
    print("\n==== レース情報 ====")
    print(f"会場: {jcd} レース: {rno} 日付: {hd}")
    print(result_text)
    
    # データ取得状況の概要を表示
    print("\n=== データ取得状況概要 ===")
    got_kyubetsu = all(p.get("級別", "") != "" for p in combined_data["players"])
    got_boat_numbers = all(
        p.get("ボート番号", "") != "" for p in combined_data["players"]
    )
    got_exhibition_times = all(
        p.get("展示タイム", "") != "" for p in combined_data["players"]
    )
    got_st_times = all(p.get("ST", "") != "" for p in combined_data["players"])
    got_tilts = all(p.get("チルト", "") != "" for p in combined_data["players"])
    
    print(f"級別: {'✓' if got_kyubetsu else '×'}")
    print(f"ボート番号: {'✓' if got_boat_numbers else '×'}")
    print(f"展示タイム: {'✓' if got_exhibition_times else '×'}")
    print(f"STデータ: {'✓' if got_st_times else '×'}")
    print(f"チルト: {'✓' if got_tilts else '×'}")
    
    return combined_data, "\n".join(output)

def diagnose_combination_issue(race_data, before_data):
    """データ結合問題の診断関数"""
    print("\n=== データ結合問題の診断 ===")
    
    # 直前情報データから選手情報を取得
    before_players = before_data.get("players", [])
    
    # 両方のデータセットの枠情報を表示
    print("\n枠番号の比較:")
    print("出走表データ枠 | 直前情報データ枠 | 一致?")
    print("-------------|----------------|-------")
    
    # 出走表の各選手について直前情報とマッチするか確認
    for i, race_player in enumerate(race_data):
        race_waku = race_player.get("枠", "")
        # 出走表の選手名
        name = race_player.get("選手名", "不明")
        
        # 同じインデックスの直前情報枠
        before_waku = (
            before_players[i].get("枠", "") if i < len(before_players) else "なし"
        )
        
        # 直接一致するか
        match = "✓" if race_waku == before_waku else "✗"
        print(
            f"{race_waku:13} | {before_waku:14} | {match} (出走表:{ord(race_waku[0]) if race_waku else 'なし'}, 直前:{ord(before_waku[0]) if before_waku else 'なし'}) {name}"
        )
    
    # 文字コード変換テスト
    print("\n=== 文字コード変換テスト ===")
    
    # 全角から半角、半角から全角への変換マップ
    zenkaku = "１２３４５６"
    hankaku = "123456"
    zen_to_han = dict(zip(zenkaku, hankaku))
    han_to_zen = dict(zip(hankaku, zenkaku))
    
    for i, race_player in enumerate(race_data):
        race_waku = race_player.get("枠", "")
        if not race_waku:
            continue
        
        # 変換テスト
        converted = ""
        for char in race_waku:
            if char in zen_to_han:
                converted += zen_to_han[char]
            else:
                converted += char
        
        # 変換後の文字と直前情報枠を比較
        matching = [p for p in before_players if p.get("枠", "") == converted]
        match_result = "✓" if matching else "✗"
        
        print(f"枠{race_waku} -> 変換後:{converted} | 一致: {match_result}")
        if matching:
            print(
                f"  一致する直前情報: 展示タイム={matching[0].get('展示タイム', '')}, ST={matching[0].get('ST', '')}, チルト={matching[0].get('チルト', '')}"
            )

def combine_data_fixed(race_data, before_data):
    """出走表と直前情報のデータを結合(修正版:文字コード対応)"""
    combined_data = {"players": [], "weather": before_data.get("weather", {})}
    
    # 全角から半角への変換マップ
    zenkaku = "１２３４５６"
    hankaku = "123456"
    zen_to_han = dict(zip(zenkaku, hankaku))
    
    # 直前情報の選手データ
    before_players = before_data.get("players", [])
    
    # インデックス用辞書作成(半角数字で統一)
    before_dict = {}
    for p in before_players:
        waku = p.get("枠", "")
        # 半角数字に統一
        normalized_waku = ""
        for char in waku:
            if char in zen_to_han:
                normalized_waku += zen_to_han[char]
            else:
                normalized_waku += char
        before_dict[normalized_waku] = p
        # デバッグ用
        print(f"直前情報枠変換: {waku} -> {normalized_waku}")
    
    # 出走表の選手ごとに処理
    for player in race_data:
        combined_player = player.copy()
        
        # 枠番号を取得して半角に変換
        waku = player.get("枠", "")
        normalized_waku = ""
        for char in waku:
            if char in zen_to_han:
                normalized_waku += zen_to_han[char]
            else:
                normalized_waku += char
        
        print(f"出走表枠変換: {waku} -> {normalized_waku}")
        
        # 変換した枠番号で直前情報を検索
        if normalized_waku in before_dict:
            print(f"  一致! 枠{waku}({normalized_waku}) -> 直前情報あり")
            before_player = before_dict[normalized_waku]
            combined_player["展示タイム"] = before_player.get("展示タイム", "")
            combined_player["ST"] = before_player.get("ST", "")
            combined_player["チルト"] = before_player.get("チルト", "")
            combined_player["プロペラ"] = before_player.get("プロペラ", "")
        else:
            print(f"  不一致! 枠{waku}({normalized_waku}) -> 直前情報なし")
            combined_player["展示タイム"] = ""
            combined_player["ST"] = ""
            combined_player["チルト"] = ""
            combined_player["プロペラ"] = ""
        
        combined_data["players"].append(combined_player)
    
    return combined_data

def fetch_race_list_data(url, debug=False, output=None):
    """出走表ページからデータを抽出(改良版:級別確実取得)"""
    if output is None:
        output = []
    
    try:
        # ユーザーエージェントを設定してアクセス
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"出走表 Status code: {status_code}")
            output.append(f"出走表 Status code: {status_code}")
            return []
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        if debug:
            print(f"出走表 Status code: {status_code}")
            print(f"Content length: {len(response.text)}")
        output.append(f"出走表 Status code: {status_code}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # レースタイトルを取得
        race_title = soup.select_one(".heading2_titleName")
        if race_title:
            race_title_text = race_title.text.strip()
            if debug:
                print(f"レースタイトル: {race_title_text}")
            output.append(f"レースタイトル: {race_title_text}")
        else:
            if debug:
                print("レースタイトルが見つかりません。")
            output.append("レースタイトルが見つかりません。")
        
        # 選手データを格納する配列
        players_data = []
        
        # 選手データが含まれるtbodyタグを取得
        player_tbodies = soup.select("table tbody.is-fs12")
        
        if debug:
            print(f"出走表 選手データ行数: {len(player_tbodies)}")
        output.append(f"出走表 選手データ行数: {len(player_tbodies)}")
        
        for idx, tbody in enumerate(player_tbodies):
            try:
                # 枠番を取得
                waku_elem = tbody.select_one(
                    ".is-boatColor1, .is-boatColor2, .is-boatColor3, .is-boatColor4, .is-boatColor5, .is-boatColor6"
                )
                waku = waku_elem.text.strip() if waku_elem else str(idx + 1)
                
                # 選手名を取得
                name_elem = tbody.select_one(".is-fs18.is-fBold a")
                name = name_elem.text.strip() if name_elem else "名前不明"
                
                # 選手登録番号を取得(URLから)
                regno = ""
                if name_elem and name_elem.has_attr("href"):
                    regno_match = re.search(r"toban=(\d+)", name_elem["href"])
                    if regno_match:
                        regno = regno_match.group(1)
                
                # 級別を取得 - 改良: 複数箇所から検索
                player_class = ""
                
                # 方法1: 登録番号の横にある級別を検索
                class_elem = tbody.select_one(".is-fs11")
                if class_elem:
                    class_text = class_elem.text.strip()
                    class_match = re.search(r'(A1|A2|B1|B2)', class_text)
                    if class_match:
                        player_class = class_match.group(1)
                
                # 方法2: 色付きの級別表示を検索
                if not player_class:
                    class_color_elem = tbody.select_one(".is-fColor1")
                    if class_color_elem:
                        player_class = class_color_elem.text.strip()
                
                # 方法3: 登録番号と級別がスラッシュで区切られている場合
                if not player_class and regno:
                    reg_class_elem = tbody.select_one(f"a[href*='toban={regno}'] + span")
                    if reg_class_elem:
                        class_text = reg_class_elem.text.strip()
                        class_match = re.search(r'/(A1|A2|B1|B2)', class_text)
                        if class_match:
                            player_class = class_match.group(1)
                
                # 全国成績を取得
                national_stats_elems = tbody.select(".is-lineH2")
                if len(national_stats_elems) >= 1:
                    national_stats = national_stats_elems[1].text.strip().split("\n")
                    national_stats = [s.strip() for s in national_stats if s.strip()]
                    national_result = "-".join(national_stats)
                else:
                    national_result = ""
                
                # 当地成績を取得
                if len(national_stats_elems) >= 2:
                    local_stats = national_stats_elems[2].text.strip().split("\n")
                    local_stats = [s.strip() for s in local_stats if s.strip()]
                    local_result = "-".join(local_stats)
                else:
                    local_result = ""
                
                # モーター情報を取得 - 修正: インデックス3を使用
                motor_no = ""
                motor_result = ""
                
                # HTMLの詳細構造をデバッグ表示
                if debug and len(national_stats_elems) >= 4:
                    print(f"\n枠{waku} モーター情報の詳細:")
                    print(f"テキスト: {national_stats_elems[3].text.strip()}")
                    motor_lines = national_stats_elems[3].text.strip().split("\n")
                    print(f"分割後: {motor_lines}")
                
                if len(national_stats_elems) >= 4:
                    motor_stats = national_stats_elems[3].text.strip().split("\n")
                    motor_stats = [s.strip() for s in motor_stats if s.strip()]
                    if motor_stats:
                        motor_no = motor_stats[0]
                        motor_rates = (
                            motor_stats[1:] if len(motor_stats) > 1 else ["", ""]
                        )
                        motor_result = f"{motor_no}({'-'.join(motor_rates)})"
                
                # ボート情報を取得 - 修正: インデックス4を使用
                boat_no = ""
                boat_result = ""
                
                # HTMLの詳細構造をデバッグ表示
                if debug and len(national_stats_elems) >= 5:
                    print(f"\n枠{waku} ボート情報の詳細:")
                    print(f"テキスト: {national_stats_elems[4].text.strip()}")
                    boat_lines = national_stats_elems[4].text.strip().split("\n")
                    print(f"分割後: {boat_lines}")
                
                if len(national_stats_elems) >= 5:
                    boat_stats = national_stats_elems[4].text.strip().split("\n")
                    boat_stats = [s.strip() for s in boat_stats if s.strip()]
                    if boat_stats:
                        boat_no = boat_stats[0]
                        boat_rates = boat_stats[1:] if len(boat_stats) > 1 else ["", ""]
                        boat_result = f"{boat_no}({'-'.join(boat_rates)})"
                
                # F数、L数、平均STを処理
                f_number = "F0"
                l_number = "L0"
                avg_st = "0.00"
                
                if len(national_stats_elems) >= 1:
                    fst_text = national_stats_elems[0].text.strip()
                    f_match = re.search(r"F(\d+)", fst_text)
                    if f_match:
                        f_number = f"F{f_match.group(1)}"
                    
                    l_match = re.search(r"L(\d+)", fst_text)
                    if l_match:
                        l_number = f"L{l_match.group(1)}"
                    
                    st_match = re.search(r"(\d+\.\d+)", fst_text)
                    if st_match:
                        avg_st = st_match.group(1)
                
                player_info = {
                    "枠": waku,
                    "選手番号": regno,
                    "選手名": name,
                    "級別": player_class,
                    "F数": f_number,
                    "L数": l_number,
                    "平均ST": avg_st,
                    "全国成績": national_result,
                    "当地成績": local_result,
                    "モーター番号": motor_no,
                    "モーター": motor_result,
                    "ボート番号": boat_no,
                    "ボート": boat_result,
                }
                
                if debug:
                    print(
                        f"枠{waku} データ取得: 級別={player_class}, ボート番号={boat_no}, モーター番号={motor_no}"
                    )
                
                players_data.append(player_info)
                
            except Exception as e:
                error_msg = f"選手データ {idx+1} の解析中にエラーが発生しました: {e}"
                print(error_msg)
                if debug:
                    print(traceback.format_exc())
                output.append(error_msg)
        
        return players_data
        
    except Exception as e:
        error_msg = f"出走表の取得中にエラーが発生しました: {e}"
        print(error_msg)
        if debug:
            print(traceback.format_exc())
        output.append(error_msg)
        return []

def fetch_before_info_data(url, debug=False, output=None):
    """直前情報ページからデータを抽出(改良版: 展示タイム・ST・チルト確実取得)"""
    if output is None:
        output = []
    
    default_result = {"weather": {}, "players": []}
    
    try:
        # ユーザーエージェントを設定してアクセス
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"直前情報 Status code: {status_code}")
            output.append(f"直前情報 Status code: {status_code}")
            return default_result
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        if debug:
            print(f"直前情報 Status code: {status_code}")
        output.append(f"直前情報 Status code: {status_code}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 天候情報を抽出
        weather_info = {}
        weather_section = soup.select_one(".weather1")
        
        if weather_section:
            # 天候(晴れなど)を抽出
            weather_type_elem = weather_section.select_one(".weather1_bodyUnit.is-weather")
            if weather_type_elem:
                weather_classes = weather_type_elem.select_one(".weather1_bodyUnitImage")
                if weather_classes and "class" in weather_classes.attrs:
                    weather_class = weather_classes.get("class")
                    weather_type = "晴れ"  # デフォルト
                    if "is-weather1" in weather_class:
                        weather_type = "晴れ"
                    elif "is-weather2" in weather_class:
                        weather_type = "曇り"
                    elif "is-weather3" in weather_class:
                        weather_type = "雨"
                    elif "is-weather4" in weather_class:
                        weather_type = "雪"
                    weather_info["天候"] = weather_type
            
            # 気温、水温、風速、波高を抽出
            temp_labels = weather_section.select(".weather1_bodyUnitLabel")
            for label in temp_labels:
                title_elem = label.select_one(".weather1_bodyUnitLabelTitle")
                data_elem = label.select_one(".weather1_bodyUnitLabelData")
                
                if title_elem and data_elem:
                    title = title_elem.text.strip()
                    data = data_elem.text.strip()
                    
                    if "気温" in title:
                        weather_info["気温"] = data
                    elif "水温" in title:
                        weather_info["水温"] = data
                    elif "風速" in title:
                        weather_info["風速"] = data
                    elif "波高" in title:
                        weather_info["波高"] = data
            
            # 風向を抽出
            wind_dir_elem = weather_section.select_one(
                ".weather1_bodyUnit.is-windDirection .weather1_bodyUnitImage"
            )
            if wind_dir_elem and "class" in wind_dir_elem.attrs:
                wind_classes = wind_dir_elem.get("class")
                wind_dir = "不明"
                
                # 風向きの判定(クラス名から)
                for wind_class in wind_classes:
                    if "is-wind" in wind_class:
                        direction_num = wind_class.replace("is-wind", "")
                        try:
                            direction_num = int(direction_num)
                            if 1 <= direction_num <= 4:
                                wind_dir = "追い風"
                            elif 5 <= direction_num <= 12:
                                wind_dir = "横風"
                            else:
                                wind_dir = "向かい風"
                        except ValueError:
                            pass
                
                weather_info["風向"] = wind_dir
        
        # 選手ごとの基本情報を格納する辞書を作成
        player_info_by_waku = {}
        
        # 1. 直前情報テーブルから展示タイムとチルト情報を取得
        exhibition_table = soup.select_one("table.is-w748")
        
        if exhibition_table:
            # テーブルのヘッダー行から列インデックスを取得
            header_row = exhibition_table.select_one("thead tr")
            header_cells = header_row.select("th") if header_row else []
            
            # 列名とインデックスのマッピングを作成
            column_indices = {}
            for i, cell in enumerate(header_cells):
                column_name = cell.text.strip()
                column_indices[column_name] = i
            
            # デバッグ表示
            if debug:
                print("\n直前情報テーブル列インデックス:")
                for name, idx in column_indices.items():
                    print(f"{name}: {idx}")
            
            # 各選手の行(tbody要素)を取得
            player_rows = exhibition_table.select("tbody")
            
            if debug:
                print(f"\n直前情報 選手データ行数: {len(player_rows)}")
            output.append(f"直前情報 選手データ行数: {len(player_rows)}")
            
            for player_row in player_rows:
                try:
                    # 枠番を取得
                    waku_elem = player_row.select_one(
                        ".is-boatColor1, .is-boatColor2, .is-boatColor3, .is-boatColor4, .is-boatColor5, .is-boatColor6"
                    )
                    if waku_elem:
                        waku = waku_elem.text.strip()
                        
                        # すべてのtd要素を取得
                        td_elements = player_row.select("td")
                        
                        # 展示タイム、チルト、プロペラを取得
                        # 列名からインデックスを特定
                        exhibition_time = ""
                        tilt_value = ""
                        propeller_info = ""
                        
                        # 展示タイム（通常は5列目）
                        exhibition_idx = column_indices.get("展示タイム", 4)
                        if 0 <= exhibition_idx < len(td_elements):
                            exhibition_time = td_elements[exhibition_idx].text.strip()
                        
                        # チルト（通常は6列目）
                        tilt_idx = column_indices.get("チルト", 5)
                        if 0 <= tilt_idx < len(td_elements):
                            tilt_value = td_elements[tilt_idx].text.strip()
                        
                        # プロペラ（通常は7列目）
                        propeller_idx = column_indices.get("プロペラ", 6)
                        if 0 <= propeller_idx < len(td_elements):
                            propeller_info = td_elements[propeller_idx].text.strip()
                        
                        if debug:
                            print(
                                f"枠{waku} 直前情報: 展示タイム={exhibition_time}, チルト={tilt_value}"
                            )
                        
                        # 選手情報の辞書に保存
                        player_info_by_waku[waku] = {
                            "枠": waku,
                            "展示タイム": exhibition_time,
                            "チルト": tilt_value,
                            "プロペラ": propeller_info,
                            "ST": "",  # STは後で別テーブルから取得
                        }
                
                except Exception as e:
                    error_msg = (
                        f"展示タイム・チルト情報の取得中にエラーが発生しました: {e}"
                    )
                    print(error_msg)
                    if debug:
                        print(traceback.format_exc())
                    output.append(error_msg)
        
        # 2. スタート展示テーブルからSTを取得
        st_table = soup.select_one("table.is-w238")
        
        if st_table:
            # 各艇のST情報を含む div要素を取得
            boat_divs = st_table.select(".table1_boatImage1")
            
            for boat_div in boat_divs:
                try:
                    # 枠番取得
                    number_elem = boat_div.select_one(".table1_boatImage1Number")
                    if number_elem:
                        # クラス名から枠番を特定
                        waku = None
                        for class_name in number_elem.get("class", []):
                            if class_name.startswith("is-type"):
                                waku_match = re.search(r"is-type(\d+)", class_name)
                                if waku_match:
                                    waku = waku_match.group(1)
                                    break
                        
                        # クラスから取得できなければテキストから取得
                        if not waku:
                            waku = number_elem.text.strip()
                        
                        # STタイム取得
                        time_elem = boat_div.select_one(".table1_boatImage1Time")
                        if time_elem:
                            st_value = time_elem.text.strip()
                            
                            if debug:
                                print(f"枠{waku} ST値: {st_value}")
                            
                            if waku in player_info_by_waku:
                                player_info_by_waku[waku]["ST"] = st_value
                            else:
                                # 枠番が見つからなければ新規作成
                                player_info_by_waku[waku] = {
                                    "枠": waku,
                                    "展示タイム": "",
                                    "チルト": "",
                                    "プロペラ": "",
                                    "ST": st_value,
                                }
                
                except Exception as e:
                    error_msg = f"ST情報の取得中にエラーが発生しました: {e}"
                    print(error_msg)
                    if debug:
                        print(traceback.format_exc())
                    output.append(error_msg)
        
        # ST情報を直接テーブルからも取得（2つ目の方法）
        if len(player_info_by_waku) < 6 or any(not p.get("ST") for p in player_info_by_waku.values()):
            st_time_table = soup.select_one(".table1_boatImage")
            if st_time_table:
                # テーブル内の全STデータを取得
                all_st_data = st_time_table.select(".table1_boatImage1Time")
                all_numbers = st_time_table.select(".table1_boatImage1Number")
                
                if len(all_st_data) == len(all_numbers) and len(all_numbers) > 0:
                    for i, (num_elem, st_elem) in enumerate(zip(all_numbers, all_st_data)):
                        try:
                            waku = num_elem.text.strip()
                            st_value = st_elem.text.strip()
                            
                            if waku in player_info_by_waku:
                                if not player_info_by_waku[waku].get("ST"):
                                    player_info_by_waku[waku]["ST"] = st_value
                            else:
                                player_info_by_waku[waku] = {
                                    "枠": waku,
                                    "展示タイム": "",
                                    "チルト": "",
                                    "プロペラ": "",
                                    "ST": st_value,
                                }
                        except Exception as e:
                            if debug:
                                print(f"追加ST取得でエラー(枠{i+1}): {e}")
        
        # 最終的な選手データを配列に変換
        before_data = []
        for waku in sorted(
            player_info_by_waku.keys(), key=lambda x: int(x) if x.isdigit() else 999
        ):
            before_data.append(player_info_by_waku[waku])
        
        if debug:
            print(f"\n直前情報 データ取得完了: 選手数={len(before_data)}")
            for player in before_data:
                print(
                    f"枠{player['枠']}: 展示タイム={player.get('展示タイム', 'なし')}, "
                    f"ST={player.get('ST', 'なし')}, チルト={player.get('チルト', 'なし')}"
                )
        
        return {"weather": weather_info, "players": before_data}
        
    except Exception as e:
        error_msg = f"直前情報の取得中にエラーが発生しました: {e}"
        print(error_msg)
        if debug:
            print(traceback.format_exc())
        output.append(error_msg)
        return default_result

def display_results(data, output):
    """データの表示と出力（修正版）"""
    result_text = []
    
    # 選手データをテーブル形式で表示
    if "players" in data and data["players"]:
        # 天候データを表示
        if "weather" in data and data["weather"]:
            result_text.append("\n【天候情報】")
            for key, value in data["weather"].items():
                result_text.append(f"{key}: {value}")
        
        # 選手データを表で表示
        result_text.append("\n【選手データ】")
        player_table = []
        
        # ヘッダーを設定 - 修正:級別を追加
        headers = [
            "枠",
            "選手名",
            "級別",
            "スタート成績",
            "全国成績",
            "当地成績",
            "モーター",
            "ボート",
            "展示タイム",
            "ST",
            "チルト",
        ]
        player_table.append(headers)
        
        # 各選手のデータを追加
        for player in data["players"]:
            # スタート成績のみをF数-L数-平均STの形式で表示
            f_num = player.get("F数", "F0")
            l_num = player.get("L数", "L0")
            avg_st = player.get("平均ST", "0.00")
            start_perf = f"{f_num}-{l_num}-{avg_st}"
            
            row = [
                player.get("枠", ""),
                player.get("選手名", ""),
                player.get("級別", ""),  # 級別
                start_perf,  # スタート成績
                player.get("全国成績", ""),  # 全国成績はそのまま表示
                player.get("当地成績", ""),
                player.get("モーター", ""),
                player.get("ボート", ""),
                player.get("展示タイム", ""),
                player.get("ST", ""),
                player.get("チルト", ""),
            ]
            
            player_table.append(row)
        
        table_output = tabulate(player_table, headers="firstrow", tablefmt="grid")
        result_text.append(table_output)
        output.append(table_output)  # 出力リストにも追加
        
        return "\n".join(result_text)
    else:
        result_text.append("データが取得できませんでした。")
        return "\n".join(result_text)

def fetch_racer_basic_info(regno, debug=False, output=None):
    """選手の基本情報を取得"""
    if output is None:
        output = []
    
    url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/profile?toban={regno}"
    
    if debug:
        print(f"選手基本情報URL: {url}")
    output.append(f"選手基本情報URL: {url}")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"選手基本情報取得失敗: {status_code}")
            return {"登録番号": regno}
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 選手名と登録番号を取得
        racer_info = {"登録番号": regno}
        
        # 名前を取得
        name_elem = soup.select_one(".is-p10")
        if name_elem:
            full_name = name_elem.text.strip()
            racer_info["名前"] = full_name
        
        # プロフィール情報を取得
        profile_table = soup.select_one(".is-w495")
        if profile_table:
            rows = profile_table.select("tr")
            for row in rows:
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    key = th.text.strip()
                    value = td.text.strip()
                    racer_info[key] = value
        
        # 級別を取得
        class_elem = soup.select_one(".is-kyu1")
        if class_elem:
            racer_info["級別"] = class_elem.text.strip()
        
        # 登録期を取得
        term_elem = soup.select_one('a[href*="/tterm/"]')
        if term_elem:
            racer_info["期別"] = term_elem.text.strip()
        
        # 所属支部を取得
        branch_elem = soup.select_one('a[href*="/branch/"]')
        if branch_elem:
            racer_info["支部"] = branch_elem.text.strip()
        
        return racer_info
        
    except Exception as e:
        print(f"選手基本情報の取得中にエラーが発生しました: {e}")
        if debug:
            print(traceback.format_exc())
        return {"登録番号": regno}

def fetch_racer_back3_data(regno, debug=False):
    """選手の過去3節成績を取得"""
    url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/back3?toban={regno}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"過去3節成績取得失敗: {status_code}")
            return {}
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 過去3節の成績データを取得
        back3_data = {
            "tournaments": [],
            "recent_win": {}
        }
        
        # 過去3節の大会情報を取得
        tournament_rows = soup.select(".table1 > table > tbody")
        
        for row in tournament_rows:
            try:
                # 開催期間
                date_cell = row.select_one("td:nth-child(1)")
                if date_cell:
                    date_text = date_cell.text.strip().replace('\n', '～')
                else:
                    date_text = ""
                
                # 会場
                place_cell = row.select_one("td:nth-child(2) img")
                place = place_cell.get("alt", "") if place_cell else ""
                
                # グレード
                grade_cell = row.select_one("td:nth-child(3)")
                grade_classes = grade_cell.get("class", []) if grade_cell else []
                grade = ""
                for cls in grade_classes:
                    if "is-" in cls and not cls == "is-p10-5":
                        grade = cls.replace("is-", "")
                
                # 開催時間帯
                time_cell = row.select_one("td:nth-child(4)")
                time_classes = time_cell.get("class", []) if time_cell else []
                time_type = ""
                for cls in time_classes:
                    if "is-" in cls:
                        time_type = cls.replace("is-", "")
                
                # タイトル
                title_cell = row.select_one("td:nth-child(5) a")
                title = title_cell.text.strip() if title_cell else ""
                title_url = title_cell.get("href", "") if title_cell else ""
                if title_url and title_url.startswith("/"):
                    title_url = f"https://www.boatrace.jp{title_url}"
                
                # 節間成績
                result_cell = row.select_one("td:nth-child(6)")
                results_raw = result_cell.text.strip() if result_cell else ""
                
                # 節間成績をより詳細に解析
                results_links = result_cell.select("a") if result_cell else []
                detailed_results = []
                
                for link in results_links:
                    result_text = link.text.strip()
                    result_url = link.get("href", "")
                    if result_url and result_url.startswith("/"):
                        result_url = f"https://www.boatrace.jp{result_url}"
                    
                    # URLからレース番号、会場コード、日付を抽出
                    race_info = {}
                    if result_url:
                        url_params = result_url.split("?")[1].split("&") if "?" in result_url else []
                        for param in url_params:
                            if "=" in param:
                                key, value = param.split("=")
                                race_info[key] = value
                    
                    detailed_results.append({
                        "result": result_text,
                        "url": result_url,
                        "race_info": race_info
                    })
                
                tournament_info = {
                    "date": date_text,
                    "place": place,
                    "grade": grade,
                    "time_type": time_type,
                    "title": title,
                    "title_url": title_url,
                    "results_raw": results_raw,
                    "detailed_results": detailed_results
                }
                
                back3_data["tournaments"].append(tournament_info)
                
            except Exception as e:
                if debug:
                    print(f"過去3節成績の行解析でエラー: {e}")
        
        # 直近の優勝情報を取得
        win_row = soup.select_one(".table1:nth-of-type(2) > table > tbody > tr")
        if win_row:
            try:
                # 日付
                date_cell = win_row.select_one("td:nth-child(1)")
                win_date = date_cell.text.strip() if date_cell else ""
                
                # 会場
                place_cell = win_row.select_one("td:nth-child(2) img")
                win_place = place_cell.get("alt", "") if place_cell else ""
                
                # グレード
                grade_cell = win_row.select_one("td:nth-child(3)")
                grade_classes = grade_cell.get("class", []) if grade_cell else []
                win_grade = ""
                for cls in grade_classes:
                    if "is-" in cls and not cls == "is-p10-5":
                        win_grade = cls.replace("is-", "")
                
                # 開催時間帯
                time_cell = win_row.select_one("td:nth-child(4)")
                time_classes = time_cell.get("class", []) if time_cell else []
                win_time_type = ""
                for cls in time_classes:
                    if "is-" in cls:
                        win_time_type = cls.replace("is-", "")
                
                # タイトル
                title_cell = win_row.select_one("td:nth-child(5) a")
                win_title = title_cell.text.strip() if title_cell else ""
                win_title_url = title_cell.get("href", "") if title_cell else ""
                if win_title_url and win_title_url.startswith("/"):
                    win_title_url = f"https://www.boatrace.jp{win_title_url}"
                
                back3_data["recent_win"] = {
                    "date": win_date,
                    "place": win_place,
                    "grade": win_grade,
                    "time_type": win_time_type,
                    "title": win_title,
                    "title_url": win_title_url
                }
                
            except Exception as e:
                if debug:
                    print(f"直近の優勝情報解析でエラー: {e}")
        
        return back3_data
        
    except Exception as e:
        print(f"過去3節成績の取得中にエラーが発生しました: {e}")
        if debug:
            traceback.print_exc()
        return {}

def fetch_racer_season_data(regno, debug=False):
    """選手の期別成績を取得"""
    url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/season?toban={regno}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"期別成績取得失敗: {status_code}")
            return {}
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 集計期間を取得
        period_text = soup.select_one(".text p")
        period = period_text.text.strip().replace('集計期間：', '') if period_text else ""
        
        # 成績データを取得
        season_data = {"period": period, "stats": {}}
        
        # テーブルからデータを抽出
        table_rows = soup.select(".table1 > table > tbody > tr")
        
        for row in table_rows:
            try:
                # 項目名と値を取得
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    item_name = th.text.strip()
                    item_value = td.text.strip()
                    season_data["stats"][item_name] = item_value
                
                # 2つ目の項目名と値も取得
                th2 = row.select_one("th:nth-of-type(2)")
                td2 = row.select_one("td:nth-of-type(2)")
                if th2 and td2:
                    item_name2 = th2.text.strip()
                    item_value2 = td2.text.strip()
                    season_data["stats"][item_name2] = item_value2
                    
            except Exception as e:
                if debug:
                    print(f"期別成績の行解析でエラー: {e}")
        
        return season_data
        
    except Exception as e:
        print(f"期別成績の取得中にエラーが発生しました: {e}")
        if debug:
            traceback.print_exc()
        return {}

def fetch_racer_course_data(regno, debug=False):
    """選手のコース別成績を取得"""
    url = f"https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={regno}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response, status_code = cached_request(url, headers, debug=debug)
        
        if not response or status_code != 200:
            if debug:
                print(f"コース別成績取得失敗: {status_code}")
            return {}
        
        if hasattr(response, 'encoding'):
            response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # コース別成績データ
        course_data = {"courses": {}}
        
        # コース別進入率
        entry_rate_table = soup.select_one(".grid_unit:nth-of-type(1) .table1:nth-of-type(1) table")
        if entry_rate_table:
            for course in range(1, 7):
                try:
                    course_row = entry_rate_table.select_one(f"tbody:nth-of-type({course}) tr")
                    if course_row:
                        rate_text = course_row.select_one(".table1_progress2Label").text.strip()
                        rate = rate_text.replace("%", "")
                        
                        if course not in course_data["courses"]:
                            course_data["courses"][course] = {}
                        course_data["courses"][course]["entry_rate"] = rate
                        
                except Exception as e:
                    if debug:
                        print(f"コース{course}の進入率解析でエラー: {e}")
        
        # コース別3連対率
        triad_rate_table = soup.select_one(".grid_unit:nth-of-type(1) .table1:nth-of-type(2) table")
        if triad_rate_table:
            for course in range(1, 7):
                try:
                    course_row = triad_rate_table.select_one(f"tbody:nth-of-type({course}) tr")
                    if course_row:
                        # 合計の3連対率
                        rate_text = course_row.select_one(".table1_progress2Label").text.strip()
                        total_rate = rate_text.replace("%", "")
                        
                        # 内訳（1着率、2着率、3着率）
                        progress_spans = course_row.select(".table1_progress2Bar .is-progress")
                        rates = []
                        for i, span in enumerate(progress_spans[:3], 1):
                            style = span.get("style", "")
                            width_match = re.search(r"width:\s*([0-9.]+)%", style)
                            if width_match:
                                rate = width_match.group(1)
                                rates.append(rate)
                            else:
                                rates.append("0")
                        
                        if course not in course_data["courses"]:
                            course_data["courses"][course] = {}
                        
                        if len(rates) >= 3:
                            course_data["courses"][course]["triad_rate"] = {
                                "total": total_rate,
                                "win_rate": rates[0],
                                "second_rate": rates[1],
                                "third_rate": rates[2]
                            }
                            
                except Exception as e:
                    if debug:
                        print(f"コース{course}の3連対率解析でエラー: {e}")
        
        # コース別平均スタートタイミング
        st_timing_table = soup.select_one(".grid_unit:nth-of-type(2) .table1:nth-of-type(1) table")
        if st_timing_table:
            for course in range(1, 7):
                try:
                    course_row = st_timing_table.select_one(f"tbody:nth-of-type({course}) tr")
                    if course_row:
                        timing_text = course_row.select_one(".table1_progress2Label").text.strip()
                        
                        if course not in course_data["courses"]:
                            course_data["courses"][course] = {}
                        course_data["courses"][course]["avg_st_timing"] = timing_text
                        
                except Exception as e:
                    if debug:
                        print(f"コース{course}の平均スタートタイミング解析でエラー: {e}")
        
        # コース別スタート順
        st_order_table = soup.select_one(".grid_unit:nth-of-type(2) .table1:nth-of-type(2) table")
        if st_order_table:
            for course in range(1, 7):
                try:
                    course_row = st_order_table.select_one(f"tbody:nth-of-type({course}) tr")
                    if course_row:
                        order_text = course_row.select_one(".table1_progress2Label").text.strip()
                        
                        if course not in course_data["courses"]:
                            course_data["courses"][course] = {}
                        course_data["courses"][course]["avg_st_order"] = order_text
                        
                except Exception as e:
                    if debug:
                        print(f"コース{course}のスタート順解析でエラー: {e}")
        
        return course_data
        
    except Exception as e:
        print(f"コース別成績の取得中にエラーが発生しました: {e}")
        if debug:
            traceback.print_exc()
        return {}

def fetch_racer_detailed_profile(regno, debug=False):
    """選手の詳細プロファイルを取得する統合関数"""
    output = []
    output.append(f"選手番号: {regno}")
    
    try:
        # 基本情報を取得
        basic_info = fetch_racer_basic_info(regno, debug, output)
        
        # 過去3節成績を取得
        back3_data = fetch_racer_back3_data(regno, debug)
        
        # 期別成績を取得
        season_data = fetch_racer_season_data(regno, debug)
        
        # コース別成績を取得
        course_data = fetch_racer_course_data(regno, debug)
        
        # 結果をまとめる
        racer_data = {
            "basic_info": basic_info,
            "back3_data": back3_data,
            "season_data": season_data,
            "course_data": course_data,
        }
        
        return racer_data, "\n".join(output)
        
    except Exception as e:
        error_msg = f"選手詳細データの取得中にエラーが発生しました: {e}"
        print(error_msg)
        output.append(error_msg)
        if debug:
            print(traceback.format_exc())
        return None, "\n".join(output)

# BoatRaceDataCollector クラスの実装（公式サイト対応版）
class BoatRaceDataCollector:
    """ボートレースのデータを収集するクラス（公式サイト版）"""
    
    def __init__(self):
        """初期化"""
        self.boatrace_url = "https://www.boatrace.jp"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # データ保存用のディレクトリがなければ作成
        os.makedirs("data/races", exist_ok=True)
    
    def get_race_info(self, stadium, race_no, date, debug=False):
        """レース情報を取得（既存の関数を活用）"""
        stadium_code = get_stadium_code(stadium)
        data, _ = scrape_boatrace_data(
            jcd=stadium_code, rno=race_no, hd=date, debug=debug
        )
        return data
    
    def analyze_race(self, race_info, debug=False):
        """レース情報を分析"""
        analysis = {
            "概要": f"{race_info.get('場名', '')} {race_info.get('レース番号', '')}R {race_info.get('日付', '')}",
            "スタート": [],
            "展示タイム": [],
            "選手評価": [],
        }
        
        # プレイヤー情報から分析データを構築
        if "players" in race_info:
            for player in race_info["players"]:
                # スタート情報
                if "ST" in player and player["ST"]:
                    st_info = {
                        "枠番": player.get("枠", ""),
                        "ST": player.get("ST", ""),
                        "コメント": "",
                    }
                    
                    if player["ST"].startswith("F"):
                        st_info["コメント"] = "フライング"
                    elif (
                        player["ST"] != "-"
                        and float(player["ST"].replace("F", "").replace(".", "0."))
                        < 0.1
                    ):
                        st_info["コメント"] = "好スタート"
                    
                    analysis["スタート"].append(st_info)
                
                # 展示タイム
                if "展示タイム" in player and player["展示タイム"]:
                    try:
                        float_time = float(player["展示タイム"])
                        time_info = {
                            "枠番": player.get("枠", ""),
                            "タイム": player.get("展示タイム", ""),
                            "調整": player.get("チルト", ""),
                            "コメント": "",
                        }
                        analysis["展示タイム"].append(time_info)
                    except (ValueError, TypeError):
                        # 数値に変換できない場合はスキップ
                        pass
                
                # 選手評価
                if "選手名" in player:
                    win_rate = "0"
                    if "全国成績" in player and "-" in player["全国成績"]:
                        parts = player["全国成績"].split("-")
                        if parts and parts[0]:
                            win_rate = parts[0]
                    
                    player_info = {
                        "枠番": player.get("枠", ""),
                        "選手名": player.get("選手名", ""),
                        "勝率": win_rate,
                        "コメント": "",
                    }
                    
                    try:
                        rate = float(win_rate)
                        if rate >= 7.5:
                            player_info["コメント"] = "勝率上位"
                        elif rate >= 6.5:
                            player_info["コメント"] = "好調"
                        elif rate <= 5.0:
                            player_info["コメント"] = "低調"
                    except (ValueError, TypeError):
                        pass
                    
                    analysis["選手評価"].append(player_info)
        
        if debug:
            print("レース分析が完了しました")
        
        return analysis
    
    def save_race_info(self, race_info, debug=False):
        """レース情報をJSONファイルとして保存"""
        try:
            stadium = race_info.get("場名", "unknown")
            race_no = race_info.get("レース番号", "0")
            date = race_info.get("日付", "").replace("/", "")
            
            filename = f"data/races/{date}_{stadium}_{race_no}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(race_info, f, ensure_ascii=False, indent=2)
            
            if debug:
                print(f"レース情報を{filename}に保存しました")
            
            return True
            
        except Exception as e:
            print(f"レース情報の保存中にエラーが発生しました: {e}")
            if debug:
                traceback.print_exc()
            return False

# メイン実行部分
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ボートレース情報を取得（公式サイト版）")
    parser.add_argument("stadium", help="会場名または会場コード")
    parser.add_argument("race", help="レース番号")
    parser.add_argument("date", help="開催日(YYYYMMDD)")
    parser.add_argument("--debug", "-d", action="store_true", help="デバッグモード")
    parser.add_argument("--skip-racer", "-s", action="store_true", help="選手詳細データの取得をスキップ")
    args = parser.parse_args()

    # 実行開始の出力
    print(f"スクリプトを開始: {args.stadium} {args.race} {args.date}")

    # 日付ディレクトリを作成
    date_dir = f"data/races/{args.date}"
    os.makedirs(date_dir, exist_ok=True)
    
    # 選手詳細情報用の日付ディレクトリも作成
    racers_date_dir = f"data/racers/{args.date}"
    os.makedirs(racers_date_dir, exist_ok=True)

    # 会場コードを取得
    stadium_code = get_stadium_code(args.stadium)

    # レース情報を取得（出走表と直前情報）
    data, output = scrape_boatrace_data(
        jcd=stadium_code,
        rno=args.race,
        hd=args.date,
        debug=args.debug,
        clipboard=False # クリップボード機能は使用しない
    )

    # 選手詳細情報を格納する辞書を初期化
    racer_details = {}

    # 選手詳細情報の取得（スキップが指定されていない場合）
    if not args.skip_racer:
        print("\n=== 選手詳細情報の取得を開始 ===")
        for player in data["players"]:
            regno = player.get("選手番号", "")
            if regno:
                print(f"選手番号 {regno} ({player.get('選手名', '')}) の詳細データを取得中...")
                try:
                    # 選手の詳細情報を取得
                    detailed_profile, _ = fetch_racer_detailed_profile(regno, debug=args.debug)
                    if detailed_profile:
                        # 詳細データを日付ディレクトリに保存
                        regno_filename = f"{racers_date_dir}/{regno}.json"
                        with open(regno_filename, "w", encoding="utf-8") as f:
                            json.dump(detailed_profile, f, ensure_ascii=False, indent=2)
                        print(f"選手 {regno} の詳細データを {regno_filename} に保存しました")

                        # 詳細データを辞書に追加
                        racer_details[regno] = detailed_profile

                        # キャッシュ機能で対応するため待機は不要
                except Exception as e:
                    print(f"選手 {regno} の詳細データ取得中にエラー: {e}")
                    if args.debug:
                        traceback.print_exc()

    # レース分析
    race_info = {
        "場名": args.stadium,
        "レース番号": args.race,
        "日付": args.date,
        "players": data["players"],
    }

    # 分析器のインスタンス化
    collector = BoatRaceDataCollector()
    analysis = collector.analyze_race(race_info, args.debug)

    print("\n==== レース分析結果 ====")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))

    # 最終的な結合データを作成
    final_data = {
        "基本情報": {
            "会場": args.stadium,
            "会場コード": stadium_code,
            "レース番号": args.race,
            "日付": args.date
        },
        "レース結果": data,
        "テキスト出力": output,
        "分析結果": analysis,
        "選手詳細情報": racer_details
    }

    # 結果のサマリーを表示
    print("\n==== 取得データサマリー ====")
    print(f"レース情報: {len(data['players'])}人の選手データを取得")
    print(f"選手詳細情報: {len(racer_details)}人分を取得")

    # 天候情報があれば表示
    if "weather" in data and data["weather"]:
        weather_info = []
        for key, value in data["weather"].items():
            weather_info.append(f"{key}: {value}")
        print(f"天候情報: {', '.join(weather_info)}")

    # 会場名の取得（コードから日本語名に変換）
    stadium_name = args.stadium
    if args.stadium in STADIUM_CODES.values():
        # コードから日本語名を逆引き
        for name, code in STADIUM_CODES.items():
            if code == args.stadium:
                stadium_name = name
                break

    # データをJSONファイルに日付ディレクトリ内に保存
    unified_filename = f"{date_dir}/{args.date}_{stadium_name}_{args.race}.json"
    with open(unified_filename, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print(f"レース情報を{unified_filename}に保存しました")

    # Mac通知機能
    try:
        script = f'display notification "処理が完了しました: {stadium_name} {args.race}R {args.date}" with title "データ取得完了"'
        subprocess.run(["osascript", "-e", script], check=True)
        print("完了通知を送信しました")
    except Exception as e:
        print(f"通知の送信に失敗しました: {e}")

    # 選手ごとの情報サマリーを表示
    print("\n==== 選手情報サマリー ====")
    for player in data["players"]:
        regno = player.get("選手番号", "")
        name = player.get("選手名", "不明")
        waku = player.get("枠", "?")
        kyubetsu = player.get("級別", "不明") # 級別を表示

        # 詳細情報の有無を確認
        has_details = regno in racer_details

        # 展示タイムとSTとチルトを取得
        ex_time = player.get("展示タイム", "-")
        st_time = player.get("ST", "-")
        tilt = player.get("チルト", "-")

        print(f"枠{waku}: {name} (級別:{kyubetsu}, 選手番号:{regno}) - 展示:{ex_time} ST:{st_time} チルト:{tilt} 詳細情報:{'あり' if has_details else 'なし'}")

    print("\n処理を完了しました")
