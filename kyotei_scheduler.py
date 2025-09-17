#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import subprocess
from datetime import datetime, timedelta
import time
import schedule
import logging
import argparse
import os
import random

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="kyotei_scheduler.log",
)


def notify_mac(title, message):
    """macOSの通知センターに通知を送信"""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception as e:
        logging.error(f"通知の送信に失敗しました: {e}")
        return False


# 会場名とコードのマッピング（main.py準拠）
STADIUM_CODES = {
    "桐生": 1,
    "戸田": 2,
    "江戸川": 3,
    "平和島": 4,
    "多摩川": 5,
    "浜名湖": 6,
    "蒲郡": 7,
    "常滑": 8,
    "津": 9,
    "三国": 10,
    "びわこ": 11,
    "住之江": 12,
    "尼崎": 13,
    "鳴門": 14,
    "丸亀": 15,
    "児島": 16,
    "宮島": 17,
    "徳山": 18,
    "下関": 19,
    "若松": 20,
    "芦屋": 21,
    "福岡": 22,
    "唐津": 23,
    "大村": 24,
}


def parse_date_flexible(date_str):
    """6桁(YYMMDD)または8桁(YYYYMMDD)の日付文字列を8桁形式に変換"""
    if len(date_str) == 6:
        # YYMMDDの場合、20YYMMDDに変換
        return "20" + date_str
    elif len(date_str) == 8:
        # YYYYMMDDの場合はそのまま返す
        return date_str
    else:
        raise ValueError(
            f"無効な日付形式: {date_str} (YYMMDDまたはYYYYMMDD形式で入力してください)"
        )


def setup_directories(date_str):
    """データ保存用ディレクトリを作成"""
    try:
        os.makedirs("data/races", exist_ok=True)
        os.makedirs("data/racers", exist_ok=True)

        date_dir = f"data/races/{date_str}"
        os.makedirs(date_dir, exist_ok=True)

        racers_date_dir = f"data/racers/{date_str}"
        os.makedirs(racers_date_dir, exist_ok=True)

        logging.info(f"ディレクトリ作成完了: {date_dir}, {racers_date_dir}")
        return True
    except Exception as e:
        logging.error(f"ディレクトリ作成エラー: {e}")
        return False


def get_venue_list(date_str):
    """指定日のレース場一覧を取得（重複排除）"""
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        venues = []
        seen_venues = set()

        venue_bodies = soup.select("div.table1 table tbody")

        for body in venue_bodies:
            venue_cell = body.select_one("td.is-arrow1.is-fBold.is-fs15")
            if venue_cell:
                venue_img = venue_cell.select_one("img")
                if venue_img and venue_img.has_attr("alt"):
                    venue_name = venue_img["alt"]

                    if venue_name in seen_venues:
                        continue

                    venue_link = venue_cell.select_one("a")
                    if venue_link and venue_link.has_attr("href"):
                        href = venue_link["href"]
                        jcd_match = re.search(r"jcd=(\d+)", href)
                        if jcd_match:
                            venue_code = jcd_match.group(1)
                        else:
                            venue_code = get_venue_code_from_name(venue_name)
                    else:
                        venue_code = get_venue_code_from_name(venue_name)

                    venues.append({"code": venue_code, "name": venue_name})
                    seen_venues.add(venue_name)

        logging.info(f"取得したレース場: {[v['name'] for v in venues]}")
        return venues

    except Exception as e:
        logging.error(f"レース場一覧の取得中にエラー: {e}")
        return []


def get_venue_code_from_name(venue_name):
    """会場名からコードを取得（main.py準拠）"""
    for name, code in STADIUM_CODES.items():
        if name == venue_name:
            return str(code).zfill(2)
    return "00"


def get_venue_name_from_code(venue_code):
    """会場コードから会場名を取得（main.py準拠）"""
    code_int = int(venue_code)

    for name, code in STADIUM_CODES.items():
        if code == code_int:
            return name
    return venue_code


def get_race_schedule(venue_code, date_str):
    """特定レース場の全レース時間を取得"""
    url = (
        f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={venue_code}&hd={date_str}"
    )

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        races = []

        race_cells = soup.select("td.is-fs14.is-fBold")

        for cell in race_cells:
            race_link = cell.select_one("a")
            if not race_link or "R" not in race_link.text:
                continue

            race_no = race_link.text.strip().replace("R", "")

            row = cell.find_parent("tr")
            if not row:
                continue

            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            time_cell = cells[1]
            time_text = time_cell.text.strip()

            if ":" in time_text and len(time_text) == 5:
                try:
                    datetime.strptime(time_text, "%H:%M")
                    races.append({"race_no": race_no, "time": time_text})
                except ValueError:
                    logging.warning(
                        f"会場コード{venue_code}, レース{race_no}: 無効な時間形式 '{time_text}'"
                    )

        logging.info(f"会場コード{venue_code}のレース数: {len(races)}")
        return races

    except Exception as e:
        logging.error(f"会場コード{venue_code}のデータ取得中にエラー: {e}")
        return []


def run_prediction(venue_code, race_no, date_str, skip_existing=True):
    """main.pyを実行（デフォルトでファイルスキップ有効）"""
    venue_name = get_venue_name_from_code(venue_code)

    # ファイル存在確認
    if skip_existing:
        output_file = f"data/races/{date_str}/{date_str}_{venue_name}_{race_no}.json"
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            logging.info(
                f"ファイルスキップ: {venue_name} {race_no}R - 既存ファイル: {output_file} ({file_size} bytes)"
            )
            print(f"⏭️  スキップ: {venue_name} {race_no}R (既存ファイル)")
            return True  # スキップも成功扱い

    logging.info(f"予測実行開始: {venue_name} {race_no}R ({date_str})")

    try:
        setup_directories(date_str)

        cmd = ["python3", "main.py", date_str, venue_name, race_no]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if result.stdout:
            logging.info(f"main.py実行結果: {result.stdout[:200]}...")

        output_file = f"data/races/{date_str}/{date_str}_{venue_name}_{race_no}.json"
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            logging.info(
                f"予測成功: {venue_name} {race_no}R - ファイル生成: {output_file} ({file_size} bytes)"
            )
        else:
            logging.warning(
                f"予測完了: {venue_name} {race_no}R - 出力ファイルが見つかりません: {output_file}"
            )

        return True

    except subprocess.CalledProcessError as e:
        logging.error(f"予測失敗: {venue_name} {race_no}R - エラー: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"予測実行中に予期しないエラー: {venue_name} {race_no}R - {e}")
        return False


def execute_batch_mode(
    target_date_str,
    min_interval=60,
    max_interval=80,
    skip_existing=True,
    auto_yes=False,
):
    """指定日の全レースを順次実行（自動実行オプション追加）"""
    print(f"\n=== バッチモード開始: {target_date_str} ===")
    print(f"📅 対象日付: {target_date_str} (固定)")
    print(f"⏱️  レース間隔: {min_interval}〜{max_interval}秒（ランダム）")
    print(f"🔒 日付変更が起きても {target_date_str} のデータを取得し続けます")
    if skip_existing:
        print(f"⏭️  既存ファイルスキップ: 有効")
    else:
        print(f"🔄 既存ファイル再処理: 有効")
    if auto_yes:
        print(f"🤖 自動実行モード: 有効")

    setup_directories(target_date_str)

    venues = get_venue_list(target_date_str)
    if not venues:
        print("レース場が見つかりませんでした")
        notify_mac(
            "競艇スケジューラ", f"{target_date_str}: レース場が見つかりませんでした"
        )
        return False

    print(f"対象レース場: {len(venues)}箇所")

    all_races = []
    skipped_races = []

    # レース情報収集と既存ファイルチェック
    for venue in venues:
        races = get_race_schedule(venue["code"], target_date_str)
        for race in races:
            race_info = {
                "venue_code": venue["code"],
                "venue_name": venue["name"],
                "race_no": race["race_no"],
                "race_time": race["time"],
                "target_date": target_date_str,
            }

            # ファイル存在確認
            if skip_existing:
                output_file = f"data/races/{target_date_str}/{target_date_str}_{venue['name']}_{race['race_no']}.json"
                if os.path.exists(output_file):
                    skipped_races.append(race_info)
                    continue  # 既存ファイルは処理リストに追加しない

            all_races.append(race_info)
        time.sleep(2)

    # 統計情報表示
    total_original = len(all_races) + len(skipped_races)

    print(f"\n📊 レース統計:")
    print(f"総レース数: {total_original}レース")

    if skip_existing and skipped_races:
        print(f"既存ファイル（スキップ）: {len(skipped_races)}レース")
        print(f"処理対象: {len(all_races)}レース")
    else:
        print(f"処理対象: {len(all_races)}レース")

    if not all_races:
        if skip_existing and skipped_races:
            print(
                "\n✅ 全てのファイルが既に存在します。新規実行するレースがありません。"
            )
            notify_mac(
                "競艇スケジューラ", f"{target_date_str}: 全ファイル存在済み（新規なし）"
            )
        else:
            print("\n実行対象のレースが見つかりませんでした")
            notify_mac("競艇スケジューラ", f"{target_date_str}: 実行対象なし")
        return True if skipped_races else False

    # レース時間でソート
    all_races.sort(key=lambda x: x["race_time"])

    # レース一覧表示（処理対象のみ）
    print(f"\n実行予定レース: {len(all_races)}レース")
    for i, race in enumerate(all_races, 1):
        print(
            f"{i:2d}. {race['venue_name']} {race['race_no']}R ({race['race_time']}) - 対象日: {race['target_date']}"
        )

    # 自動実行またはユーザー確認
    if auto_yes:
        print(f"\n🤖 自動実行モードにより、{len(all_races)}レースを実行します")
        response = "y"
    else:
        response = input(
            f"\n{len(all_races)}レースを{min_interval}〜{max_interval}秒ランダム間隔で実行しますか？ (y/N): "
        )

    if response.lower() != "y":
        print("実行をキャンセルしました")
        notify_mac("競艇スケジューラ", "実行をキャンセルしました")
        return False

    success_count = 0
    skip_count = 0
    total_count = len(all_races)

    print(f"\n=== 実行開始 ===")
    print(f"🎯 固定対象日付: {target_date_str}")
    start_time = datetime.now()

    # 開始通知
    notify_mac(
        "競艇スケジューラ", f"バッチ実行開始: {target_date_str} ({total_count}レース)"
    )

    for i, race in enumerate(all_races, 1):
        current_time = datetime.now()
        elapsed_time = current_time - start_time
        current_date_str = current_time.strftime("%Y%m%d")

        print(f"\n[{i}/{total_count}] {race['venue_name']} {race['race_no']}R")
        print(f"📅 システム日付: {current_date_str} / 対象日付: {race['target_date']}")
        print(f"⏰ 経過時間: {elapsed_time}")

        if i > 1:
            remaining_races = total_count - i + 1
            avg_interval = (min_interval + max_interval) / 2
            estimated_remaining = remaining_races * avg_interval
            estimated_finish = current_time + timedelta(seconds=estimated_remaining)
            print(
                f"🔮 推定完了時刻: {estimated_finish.strftime('%H:%M:%S')} (平均{avg_interval}秒間隔で計算)"
            )

        # main.pyを実行（skip_existingを適切に渡す）
        success = run_prediction(
            race["venue_code"],
            race["race_no"],
            race["target_date"],
            skip_existing=skip_existing,
        )

        if success:
            success_count += 1
            # ファイルが既に存在していた場合の判定
            output_file = f"data/races/{race['target_date']}/{race['target_date']}_{race['venue_name']}_{race['race_no']}.json"
            if skip_existing and os.path.exists(output_file):
                skip_count += 1
            else:
                print(f"✓ 成功: {race['venue_name']} {race['race_no']}R")
        else:
            print(f"✗ 失敗: {race['venue_name']} {race['race_no']}R")

        # 待機処理（最後のレース以外）
        if i < total_count:
            wait_time = random.uniform(min_interval, max_interval)
            print(
                f"⏳ {wait_time:.1f}秒待機中... ({min_interval}〜{max_interval}秒ランダム)"
            )

            try:
                time.sleep(wait_time)
            except KeyboardInterrupt:
                print("\n\n実行を中断しました")
                notify_mac("競艇スケジューラ", "バッチ実行を中断しました")
                break

    end_time = datetime.now()
    total_time = end_time - start_time

    print(f"\n=== 実行結果 ===")
    print(f"🎯 対象日付: {target_date_str}")
    print(f"📊 処理レース数: {success_count}/{total_count}")
    if skip_existing:
        print(f"⏭️  スキップ（実行内）: {skip_count}レース")
        print(f"⏭️  スキップ（事前）: {len(skipped_races)}レース")
    print(f"✅ 新規処理: {success_count - skip_count}レース")
    print(f"❌ 失敗: {total_count - success_count}レース")
    print(f"⏱️  実行時間: {total_time}")
    if total_count > 0:
        print(f"📈 成功率: {success_count/total_count*100:.1f}%")

    # 完了通知
    notify_mac(
        "競艇スケジューラ",
        f"バッチ完了: {target_date_str}\n成功: {success_count}/{total_count}レース\n実行時間: {total_time}",
    )

    return success_count > 0


def execute_realtime_batch_mode(date_str, skip_existing=True, auto_yes=False):
    """リアルタイムバッチモード: 過去レースをバッチ処理後、通常スケジュールへ移行（自動実行オプション追加）"""
    print(f"\n=== リアルタイムバッチモード: {date_str} ===")
    initial_time = datetime.now()
    initial_time_str = initial_time.strftime("%H:%M")
    print(f"🕐 開始時刻: {initial_time_str}")
    print(f"📅 対象日付: {date_str}")
    if skip_existing:
        print(f"⏭️  既存ファイルスキップ: 有効")
    else:
        print(f"🔄 既存ファイル再処理: 有効")
    if auto_yes:
        print(f"🤖 自動実行モード: 有効")

    # スケジュール取得
    setup_directories(date_str)
    venues = get_venue_list(date_str)
    if not venues:
        print("レース場が見つかりませんでした")
        notify_mac("競艇スケジューラ", f"{date_str}: レース場が見つかりませんでした")
        return False

    # 全レース情報を収集
    all_races = []
    for venue in venues:
        races = get_race_schedule(venue["code"], date_str)
        for race in races:
            # 実行予定時刻を計算（レース開始10分前）
            race_time_obj = datetime.strptime(race["time"], "%H:%M")
            exec_time_obj = race_time_obj - timedelta(minutes=10)

            race_info = {
                "venue_code": venue["code"],
                "venue_name": venue["name"],
                "race_no": race["race_no"],
                "race_time": race["time"],
                "exec_time": exec_time_obj.strftime("%H:%M"),
                "exec_time_obj": exec_time_obj,
                "target_date": date_str,
            }

            all_races.append(race_info)
        time.sleep(1)

    if not all_races:
        print("実行対象のレースが見つかりませんでした")
        notify_mac("競艇スケジューラ", f"{date_str}: 実行対象なし")
        return False

    # 開始通知
    notify_mac("競艇スケジューラ", f"リアルタイムバッチ開始: {date_str}")

    # メインループ：動的に過去レースを処理
    processed_races = set()  # 処理済みレースを追跡
    min_interval = 60  # デフォルト値
    max_interval = 80  # デフォルト値

    while True:
        current_time = datetime.now()
        current_time_str = current_time.strftime("%H:%M")
        current_time_only = datetime.strptime(current_time_str, "%H:%M")

        # 未処理のレースを分類
        past_races = []
        future_races = []
        skipped_races = []

        for race in all_races:
            # レースIDを生成（重複処理防止）
            race_id = f"{race['venue_name']}_{race['race_no']}"

            # 既に処理済みの場合はスキップ
            if race_id in processed_races:
                continue

            # ファイル存在確認
            if skip_existing:
                output_file = f"data/races/{date_str}/{date_str}_{race['venue_name']}_{race['race_no']}.json"
                if os.path.exists(output_file):
                    skipped_races.append(race)
                    processed_races.add(race_id)  # 処理済みとしてマーク
                    continue

            # 時刻による分類
            if race["exec_time_obj"] <= current_time_only:
                past_races.append(race)
            else:
                future_races.append(race)

        # ソート
        past_races.sort(key=lambda x: x["exec_time"])
        future_races.sort(key=lambda x: x["exec_time"])

        print(f"\n📊 レース分析 ({current_time_str}時点):")
        print(f"処理済み: {len(processed_races)}件")
        if skip_existing and skipped_races:
            print(f"既存ファイル（スキップ）: {len(skipped_races)}件")
        print(f"過去レース（未処理）: {len(past_races)}件")
        print(f"未来レース: {len(future_races)}件")

        # 過去レースがある場合、バッチ処理を実行
        if past_races:
            print(f"\n⚠️  未処理の過去レースが{len(past_races)}件見つかりました")

            # 初回のみ間隔入力を求める（自動実行モードでない場合）
            if len(processed_races) == len(skipped_races):  # 初回判定を修正
                print("\nこれらのレースをバッチ実行します")
                if auto_yes:
                    print(
                        f"🤖 自動実行モード: デフォルト値を使用 ({min_interval}〜{max_interval}秒)"
                    )
                else:
                    while True:
                        try:
                            min_input = input("min-interval (秒) [60]: ").strip()
                            min_interval = int(min_input) if min_input else 60

                            max_input = input("max-interval (秒) [80]: ").strip()
                            max_interval = int(max_input) if max_input else 80

                            if min_interval > 0 and max_interval >= min_interval:
                                break
                            else:
                                print(
                                    "❌ 無効な値です。min > 0 かつ max >= min である必要があります。"
                                )
                        except ValueError:
                            print("❌ 数値を入力してください。")
            else:
                # 2回目以降は前回の設定を使用
                print(f"前回の設定を使用: {min_interval}〜{max_interval}秒")

            print(
                f"\n✅ {min_interval}〜{max_interval}秒のランダム間隔でバッチ実行を開始します..."
            )

            # バッチ実行
            for i, race in enumerate(past_races, 1):
                print(
                    f"\n[{i}/{len(past_races)}] {race['venue_name']} {race['race_no']}R"
                )

                # main.py実行（skip_existingを適切に渡す）
                success = run_prediction(
                    race["venue_code"],
                    race["race_no"],
                    race["target_date"],
                    skip_existing=skip_existing,
                )

                if success:
                    print(f"✓ 処理完了: {race['venue_name']} {race['race_no']}R")
                else:
                    print(f"✗ 失敗: {race['venue_name']} {race['race_no']}R")

                # 処理済みとしてマーク
                race_id = f"{race['venue_name']}_{race['race_no']}"
                processed_races.add(race_id)

                # 待機（最後以外）
                if i < len(past_races):
                    wait_time = random.uniform(min_interval, max_interval)
                    print(f"⏳ {wait_time:.1f}秒待機中...")
                    time.sleep(wait_time)

            # 処理後、再度チェックを行う（ループ継続）
            continue

        # 過去レースが全て処理済みの場合、通常スケジュールモードへ移行
        print(f"\n✅ 全ての過去レースの処理が完了しました！")
        print(f"🔄 通常のスケジュールモードに移行します...")

        # 未来のレースをスケジュール
        schedule.clear()
        scheduled_count = 0

        for race in future_races:
            schedule.every().day.at(race["exec_time"]).do(
                run_prediction,
                venue_code=race["venue_code"],
                race_no=race["race_no"],
                date_str=race["target_date"],
                skip_existing=skip_existing,  # skip_existingを渡す
            )
            scheduled_count += 1

        if scheduled_count > 0:
            print(f"\n次回実行予定：")
            # 直近5件を表示
            for race in future_races[:5]:
                print(
                    f"- {race['venue_name']} {race['race_no']}R - {race['exec_time']}に実行予定"
                )
            if len(future_races) > 5:
                print(f"... 他 {len(future_races) - 5}件")

            print(f"\n🔄 スケジューラが開始されました。{date_str}のレースを監視中...")
            print("Ctrl+Cで停止")

            # スケジューラ開始通知
            notify_mac(
                "競艇スケジューラ", f"スケジューラ開始: {scheduled_count}レース待機中"
            )

            try:
                while True:
                    # 定期的に過去レースの再チェック（5分ごと）
                    if datetime.now().minute % 5 == 0 and datetime.now().second < 30:
                        current_check_time = datetime.now()
                        current_check_str = current_check_time.strftime("%H:%M")
                        current_check_only = datetime.strptime(
                            current_check_str, "%H:%M"
                        )

                        # 新たに過去になったレースをチェック
                        newly_past = []
                        for race in future_races:
                            race_id = f"{race['venue_name']}_{race['race_no']}"
                            if (
                                race_id not in processed_races
                                and race["exec_time_obj"] <= current_check_only
                            ):
                                newly_past.append(race)

                        if newly_past:
                            print(
                                f"\n⚠️  新たに過去になったレースを検出: {len(newly_past)}件"
                            )
                            # メインループに戻る
                            break

                    schedule.run_pending()
                    time.sleep(30)

            except KeyboardInterrupt:
                print("\n🛑 スケジューラを停止しました")
                notify_mac("競艇スケジューラ", "スケジューラを停止しました")
                return True

            # newly_pastが検出された場合、ループの最初に戻る
            if "newly_past" in locals() and newly_past:
                continue
            else:
                break
        else:
            print("\n今後実行予定のレースはありません")
            notify_mac("競艇スケジューラ", f"{date_str}: 実行予定レースなし")
            break

    # 完了通知
    notify_mac("競艇スケジューラ", f"リアルタイムバッチ完了: {date_str}")
    return True


def schedule_races_for_day(date_str=None, test_mode=False, skip_existing=True):
    """その日のレース全てをスケジュール（デフォルトでスキップ有効）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    logging.info(f"{date_str}のレースをスケジュール設定開始")

    if test_mode:
        logging.info("テストモード: スケジュールは設定されません")

    setup_directories(date_str)
    schedule.clear()

    venues = get_venue_list(date_str)
    logging.info(f"本日のレース場: {len(venues)}箇所")

    all_schedules = []

    for venue in venues:
        try:
            races = get_race_schedule(venue["code"], date_str)
            logging.info(f"{venue['name']}({venue['code']}): {len(races)}レース")

            for race in races:
                race_time = race["time"]
                race_no = race["race_no"]

                time_obj = datetime.strptime(race_time, "%H:%M")
                prediction_time = time_obj - timedelta(minutes=10)
                exec_time = prediction_time.strftime("%H:%M")

                all_schedules.append(
                    {
                        "venue_code": venue["code"],
                        "venue_name": venue["name"],
                        "race_no": race_no,
                        "race_time": race_time,
                        "prediction_time": exec_time,
                        "date": date_str,
                    }
                )

                if not test_mode:
                    schedule.every().day.at(exec_time).do(
                        run_prediction,
                        venue_code=venue["code"],
                        race_no=race_no,
                        date_str=date_str,
                        skip_existing=skip_existing,  # skip_existingを渡す
                    )

                logging.info(
                    f"スケジュール{'確認' if test_mode else '追加'}: {venue['name']} {race_no}R - {race_time}（main.py実行: {exec_time}）"
                )

            time.sleep(1)

        except Exception as e:
            logging.error(
                f"エラー: {venue['name']}のデータ取得中に問題が発生しました: {e}"
            )

    if all_schedules:
        df = pd.DataFrame(all_schedules)
        os.makedirs("data/schedules", exist_ok=True)
        output_file = f"data/schedules/race_schedule_{date_str}.csv"
        df.to_csv(output_file, index=False, encoding="utf-8")
        logging.info(f"スケジュールを {output_file} に保存しました")

        total_races = len(all_schedules)
        venues_count = len(venues)
        logging.info(f"スケジュール設定完了: {venues_count}会場, {total_races}レース")

    return len(all_schedules) > 0


def run_continuous_scheduler(skip_existing=True):
    """日付変更対応の連続スケジューラ（デフォルトでスキップ有効）"""
    print("🔄 連続スケジューラ開始（日付変更対応・リアルタイム専用）")
    if skip_existing:
        print("⏭️  既存ファイルスキップ: 有効")
    else:
        print("🔄 既存ファイル再処理: 有効")
    print("Ctrl+Cで停止")

    current_date = None
    last_schedule_check = datetime.now()

    try:
        while True:
            now = datetime.now()
            today = now.strftime("%Y%m%d")

            # 日付が変わった場合または初回実行
            if current_date != today:
                print(f"\n📅 日付変更検出: {current_date} → {today}")
                logging.info(f"日付変更: {current_date} → {today}")

                # 新しい日付のスケジュールを設定
                has_races = schedule_races_for_day(
                    today, test_mode=False, skip_existing=skip_existing
                )

                if has_races:
                    print(f"✅ {today}のスケジュールを設定しました")
                    current_date = today
                else:
                    print(f"⚠️  {today}にはレースがありません")

                last_schedule_check = now

            # 1時間ごとにスケジュールの再確認
            elif (now - last_schedule_check).seconds > 3600:
                print(f"🔍 スケジュール再確認: {today}")
                schedule_races_for_day(
                    today, test_mode=False, skip_existing=skip_existing
                )
                last_schedule_check = now

            # 現在時刻を表示（5分ごと）
            if now.minute % 5 == 0 and now.second == 0:
                job_count = len(schedule.get_jobs())
                print(f"🕐 {now.strftime('%H:%M')} - 待機中ジョブ: {job_count}件")

            # スケジュール実行
            schedule.run_pending()
            time.sleep(30)  # 30秒ごとにチェック

    except KeyboardInterrupt:
        logging.info("連続スケジューラを手動停止しました")
        print("\n🛑 連続スケジューラを停止しました")


def main():
    """メイン実行関数（自動実行オプション追加）"""
    parser = argparse.ArgumentParser(
        description="競艇予測スケジューラ（main.py実行版）"
    )
    parser.add_argument(
        "--date",
        help="対象日付 (YYMMDDまたはYYYYMMDD形式)",
        default=datetime.now().strftime("%Y%m%d"),
    )
    parser.add_argument(
        "--test", action="store_true", help="テストモード（実際にスケジュールしない）"
    )
    parser.add_argument(
        "--batch", action="store_true", help="バッチモード（指定日のレースを順次実行）"
    )
    parser.add_argument(
        "--min-interval", type=int, default=60, help="バッチモードでの最小間隔（秒）"
    )
    parser.add_argument(
        "--max-interval", type=int, default=80, help="バッチモードでの最大間隔（秒）"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="連続実行モード（日付変更対応・リアルタイム専用）",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="既存ファイルを再処理（デフォルトはスキップ）",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="確認プロンプトを自動でYesとして実行"
    )
    args = parser.parse_args()

    # skip_existingの設定（デフォルトTrue、--no-skipでFalse）
    skip_existing = not args.no_skip

    # 自動実行フラグ
    auto_yes = args.yes

    # 日付形式を柔軟に処理
    try:
        args.date = parse_date_flexible(args.date)
    except ValueError as e:
        print(f"❌ {e}")
        notify_mac("競艇スケジューラ", f"エラー: {e}")
        return

    logging.info("競艇予測スケジューラ（main.py版）を開始します")

    # 連続実行モード（リアルタイム専用）
    if args.continuous:
        print("🔄 連続実行モード: 日付変更に対応して継続実行（リアルタイム専用）")
        if auto_yes:
            print("🤖 自動実行モード: 有効")
        run_continuous_scheduler(skip_existing=skip_existing)
        return

    # 日付判定
    today = datetime.now().strftime("%Y%m%d")
    is_past_date = args.date < today
    is_future_date = args.date > today
    is_today = args.date == today

    # バッチモード判定
    interval_specified = args.min_interval != 60 or args.max_interval != 80

    # 今日の日付で、バッチモード指定なし、間隔指定なしの場合
    if is_today and not args.batch and not interval_specified:
        # リアルタイムバッチモードを実行
        print(f"📊 リアルタイムモード: 当日（{args.date}）のレースを処理")
        if skip_existing:
            print("⏭️  既存ファイルスキップ: 有効（--no-skipで無効化可能）")
        else:
            print("🔄 既存ファイル再処理: 有効")
        if auto_yes:
            print("🤖 自動実行モード: 有効")
        success = execute_realtime_batch_mode(
            args.date, skip_existing=skip_existing, auto_yes=auto_yes
        )
        return

    # それ以外は従来のバッチモード
    should_run_batch = (
        args.batch or is_past_date or is_future_date or interval_specified
    )

    if should_run_batch:
        # バッチモード実行
        if is_past_date:
            print(f"⚠️  過去日付が指定されました: {args.date}")
            print("バッチモードで即時実行します")
        elif args.batch:
            print(f"📊 明示的バッチモード: {args.date}")
        elif interval_specified:
            print(f"⏱️  間隔指定バッチモード: {args.date}")
            print(f"指定間隔: {args.min_interval}〜{args.max_interval}秒")

        print(
            f"📊 バッチモード: {args.date}の全レースを{args.min_interval}〜{args.max_interval}秒ランダム間隔で順次実行"
        )
        if skip_existing:
            print("⏭️  既存ファイルスキップ: 有効（--no-skipで無効化可能）")
        else:
            print("🔄 既存ファイル再処理: 有効")
        if auto_yes:
            print("🤖 自動実行モード: 有効")

        success = execute_batch_mode(
            args.date,
            args.min_interval,
            args.max_interval,
            skip_existing=skip_existing,
            auto_yes=auto_yes,
        )

        if success:
            print("✅ バッチ実行が完了しました")
        else:
            print("❌ バッチ実行でエラーが発生しました")


if __name__ == "__main__":
    main()
