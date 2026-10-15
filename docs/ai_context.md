# ひろまち AI開発コンテキスト

## 1. この文書の目的

この文書は、AIが「ひろまち」の目的、固定技術、現在の実装状態を短時間で把握するための要約です。詳細仕様は各設計書を参照し、未確認の機能を推測で追加しないでください。

## 2. アプリの目的

「ひろまち」は、地域住民がゴミ拾い・清掃活動の終了後に内容を記録し、登録利用者同士で共有するWebアプリです。

- 主な利用者：徒歩や自転車で町内を移動し、日常的に清掃活動を行う地域住民
- 優先する価値：記録や競争ではなく、現実の清掃活動を増やして続けやすくすること
- 主な利用端末：スマートフォン

MVPの基本導線は次のとおりです。

1. ユーザー登録
2. ログイン
3. 清掃活動後に活動を記録
4. 全利用者の活動一覧・詳細を閲覧
5. マイページで自分の活動と累計を確認
6. POSTでログアウト

## 3. 固定技術

次の技術は変更しません。

- Python 3.13
- Flask 3系
- Peewee 4系
- SQLite
- Jinjaテンプレートと独自CSS

採用済みの主なパッケージは次のとおりです。

- Flask-Login：認証状態とログイン必須制御
- Flask-Session＋CacheLib：サーバー側セッション
- Flask-WTF＋WTForms：フォーム、入力検証、CSRF対策
- python-dotenv：ローカル環境変数
- pytest、pytest-cov：自動テスト
- tzdata：Windowsでの`Asia/Tokyo`タイムゾーン対応
- Pillow：活動写真の実内容検証、向き補正、縮小、メタデータ除去
- pillow-heif：HEIC・HEIFの読み込みとJPEG・PNGへの変換
- Leaflet 1.9.4（アプリ内配置）：清掃ルートの入力・地図表示

依存関係の定義は`pyproject.toml`、検証済みバージョンは`requirements-lock.txt`を参照します。

## 4. プロジェクト構成

- `hiromachi/__init__.py`：`create_app()`を持つアプリファクトリ
- `hiromachi/config.py`：環境変数からの設定読込
- `hiromachi/extensions.py`：LoginManager、Session、CSRFProtect
- `hiromachi/database.py`：Peewee接続の初期化と開閉
- `hiromachi/models.py`：現在の7モデル
- `hiromachi/commands.py`：`flask init-db`
- `hiromachi/auth/`：ユーザー登録、ログイン、ログアウト
- `hiromachi/activities/`：活動一覧、作成、詳細、画像処理と配信、「ありがとう」
- `hiromachi/users/`：マイページ
- `hiromachi/errors/`：400、404、413、500ハンドラー
- `hiromachi/templates/`：Jinjaテンプレート
- `hiromachi/static/`：共通CSS、写真プレビュー、清掃ルート地図、Leaflet配布ファイル
- `tests/`：pytestによる自動テスト

Blueprintは`main`、`auth`、`activities`、`users`に分かれています。

## 5. 実装済みルート

| エンドポイント | HTTPメソッド | URL | 用途 |
| --- | --- | --- | --- |
| `main.index` | GET | `/` | ログイン状態による入口の振り分け |
| `auth.register` | GET, POST | `/register` | ユーザー登録 |
| `auth.login` | GET, POST | `/login` | ログイン |
| `auth.logout` | POST | `/logout` | ログアウト |
| `activities.index` | GET | `/activities` | 全利用者の活動一覧 |
| `activities.create` | GET, POST | `/activities/new` | 活動記録の作成 |
| `activities.detail` | GET | `/activities/<int:activity_id>` | 活動詳細 |
| `activities.edit` | GET, POST | `/activities/<int:activity_id>/edit` | 本人限定の活動編集 |
| `activities.delete` | GET, POST | `/activities/<int:activity_id>/delete` | 本人限定の活動削除 |
| `activities.photo` | GET | `/activities/<int:activity_id>/photo` | 認証付き活動写真配信 |
| `activities.toggle_thank` | POST | `/activities/<int:activity_id>/thanks` | 他人の活動への「ありがとう」の送信・取消 |
| `users.me` | GET | `/me` | 自分の活動と集計 |

Flaskのルート表には、上記12ルートに静的ファイル用の`static`を加えた13ルートがあります。

## 6. 初版のデータ

現在使用するテーブルは次の7つです。

- `users`
- `activities`
- `waste_types`
- `activity_waste_types`
- `activity_photos`
- `activity_routes`
- `reactions`

活動とゴミの種類は中間テーブルによる多対多です。活動作成・編集と種類、写真、任意の清掃ルートは同じトランザクションで保存します。

## 7. 保存先と環境変数

- SQLite：`instance/hiromachi.sqlite3`
- サーバー側セッション：`instance/sessions/`
- 活動写真：`instance/uploads/`
- 秘密情報：`.env`
- 設定例：`.env.example`

`.env`、SQLiteファイル、セッションファイル、将来のアップロード実体はGitへ追加しません。

主な環境変数は`SECRET_KEY`、`DATABASE_PATH`、`SESSION_DIR`、`UPLOAD_DIR`、`SESSION_LIFETIME_DAYS`、`SESSION_COOKIE_SECURE`です。本番では推測できない`SECRET_KEY`とHTTPS用Cookie設定が必要です。

### 公開環境

- PythonAnywhere Beginnerへデプロイ済みです。
- コードは`~/camp-app`、仮想環境は`~/.virtualenvs/camp-app`を使用します。
- WSGI入口はリポジトリ直下の`wsgi.py`が公開する`application`です。
- 更新・確認・バックアップの手順は`docs/deployment.md`を参照します。

## 8. 基本コマンド

```powershell
# インストール
python -m pip install -e ".[test]"

# DB初期化
flask --app hiromachi init-db

# 開発サーバー
flask --app hiromachi run --debug

# テスト
pytest

# カバレッジ確認
pytest --cov=hiromachi --cov-report=term-missing
```

## 9. 設計資料の参照順

1. 最新のユーザー指示
2. `docs/requirements.md`：目的、必須機能、対象外機能
3. `docs/screens.md`：画面、表示、画面遷移
4. `docs/routes.md`：URL、HTTPメソッド、正常・異常動作
5. `docs/database.md`：テーブル、制約、保存規則
6. この文書：実装時の要約
7. `docs/coding_rules.md`：コード変更時の規約
8. `docs/tasks.md`：現在の進捗と次の作業
9. `docs/deployment.md`：PythonAnywhereへの反映と運用確認

既存コードと設計資料が食い違う場合は、勝手に片方へ合わせず差異を報告してください。仕様を変更するときは、該当する設計書、実装、テストを同じ作業内で更新します。

`docs/lean_canvas.md`は初期検討時の記録として保持し、今後は更新しません。利用者テストの事実と進捗は`docs/tasks.md`、確定した要件は`docs/requirements.md`、画面・ルート・DBの変更は各設計書へ記録します。

## 10. 現在の状態

- MVPのコードは実装済みです。
- Flaskのアプリルート12件と静的ファイルルートが登録済みです。
- 任意の活動写真1枚の登録と認証付き表示が実装済みです。
- 活動一覧に全利用者・全期間の活動回数、累計時間、累計袋数を表示します。
- HEIC・HEIFをJPEGまたはPNGへ変換するアップロードが実装済みです。
- JPEG拡張子のMPOを通常JPEGへ変換する互換処理が実装済みです。
- 投稿者本人による活動内容と写真の編集が実装済みです。
- 投稿者本人による確認画面付きの活動削除が実装済みです。
- 地図上で手動入力する任意の清掃ルートと、ログイン利用者向けの詳細表示がPythonAnywhereへ反映済みです。
- 空のルートでは、ボタン操作による1回の現在地取得と、ドラッグによる始点修正がローカル実装済みです。
- 清掃ルートの始点と終点はサーバー側で小数点以下3桁へ丸めて保存します。
- 他人の活動へ1人1件だけ送信・取消できる「ありがとう」と、詳細画面の合計件数表示が実装済みです。
- 清掃ルートと「ありがとう」は、2026年10月16日にPythonAnywhereで公開確認済みです。
- PythonAnywhere Beginnerへデプロイ済みです。
- iPhone実機からの写真投稿とサーバー側の画像変換を確認済みです。
- 2026年10月16日時点で自動テスト80件が成功しています。
- 完了済み機能を、明確な理由なく作り直さないでください。

## 11. 初版の対象外

次の機能は、要件と設計が更新されるまで実装しません。

- 複数写真、動画、一覧・マイページのサムネイル
- メールアドレス、メール認証、パスワード再設定
- GPSによる連続・バックグラウンド記録、住所検索、複数ルート
- ランキング、バッジ、連続記録
- コメント、フォロー、「ありがとう」以外のリアクション
- 清掃イベント、通知
- 外部ストレージ、管理者画面、JSON API
