# boat_predict

競艇データ収集・予測のための情報収集スクリプト群

## 概要

このプロジェクトは競艇（ボートレース）のデータを効率的に収集し、予測分析の基盤となるデータを整備するためのPythonスクリプト集です。

## セットアップ

```
git clone https://github.com/satellite1105/boat_predict.git
cd boat_predict
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 主要スクリプト

### kyotei_scheduler.py（スケジューラ）

定期/一括実行でデータ取得を回すスケジューラです（main.pyを呼び出す実行版）。実行状況は kyotei_scheduler.log に記録され、macOSでは通知センターへ通知します。

- 引数
  - `--date`: 対象日付（YYMMDD または YYYYMMDD、未指定は当日）
  - `--test`: テストモード（スケジュールせず実行フローのみ確認）
  - `--batch`: バッチモード（指定日のレースを順次実行）
  - `--min-interval`: バッチ最小間隔（秒、デフォルト 60）
  - `--max-interval`: バッチ最大間隔（秒、デフォルト 80）
  - `--continuous`: 連続実行（リアルタイム・日付跨ぎ対応）
  - `--no-skip`: 既存ファイルも再処理（通常はスキップ）
  - `--yes`/`-y`: 確認プロンプトを自動承認

- 例
```
# 当日の取得を即時実行
python kyotei_scheduler.py

# 指定日をバッチで順次取得（確認なし）
python kyotei_scheduler.py --batch --date 20250917 --yes

# 連続実行（リアルタイム監視）
python kyotei_scheduler.py --continuous

# 既存ファイルも含め再処理
python kyotei_scheduler.py --date 20250917 --no-skip
```

### boatrace_results.py（レース結果取得）

指定した「日付」と「会場名」の組み合わせでレース結果を取得します（引数の順は入れ替え可能）。ログは boatrace_debug.log に出力します。

- 引数
  - `arg1`: 日付（YYYYMMDD）または会場名
  - `arg2`: 会場名または日付（YYYYMMDD）

- 例
```
# 日付→会場名
python boatrace_results.py 20250917 びわこ

# 会場名→日付
python boatrace_results.py 住之江 20250917
```

### main.py（直前情報API対応・完全版）

直前情報を含む包括的なデータ取得を行うメインスクリプトです。基本情報、コース情報、モーター情報、セッション結果、直前情報などを統合して保存します。

- 例
```
python main.py
```

## 補助モジュール

- `basic_info.py`: 基本情報の抽出
- `before_info.py`: 直前情報の抽出と表示ランク算出
- `course_info.py`: コース関連情報の抽出
- `motor_info.py`: モーター情報の抽出
- `session_results.py`: セッション結果の抽出

## データ/ログ

- 実行ログ
  - `kyotei_scheduler.log`: スケジューラの実行記録
  - `boatrace_debug.log`: レース結果取得の詳細

- 取得データ
  - 実行日に応じたフォルダやJSONが生成されます（スクリプト内の保存処理に準拠）

## 対応会場（例）

桐生、戸田、江戸川、平和島、多摩川、浜名湖、蒲郡、常滑、津、三国、びわこ（琵琶湖）、住之江、尼崎、鳴門、丸亀、児島、宮島、徳山、下関、若松、芦屋、福岡、唐津、大村

## トラブルシュート

- 依存関係エラー: `pip install -r requirements.txt` を再実行
- 実行権限エラー: `chmod +x *.py` を付与（必要時）
- 過負荷回避: スケジューラの間隔（min/max）を適切に調整

## ライセンス

研究・個人利用を想定。各公式サイトの利用規約を順守してください。
