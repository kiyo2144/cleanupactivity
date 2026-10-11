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

依存関係の定義は`pyproject.toml`、検証済みバージョンは`requirements-lock.txt`を参照します。

## 4. プロジェクト構成

- `hiromachi/__init__.py`：`create_app()`を持つアプリファクトリ
- `hiromachi/config.py`：環境変数からの設定読込
- `hiromachi/extensions.py`：LoginManager、Session、CSRFProtect
- `hiromachi/database.py`：Peewee接続の初期化と開閉
- `hiromachi/models.py`：初版の4モデル
- `hiromachi/commands.py`：`flask init-db`
- `hiromachi/auth/`：ユーザー登録、ログイン、ログアウト
- `hiromachi/activities/`：活動一覧、作成、詳細
- `hiromachi/users/`：マイページ
- `hiromachi/errors/`：400、404、500ハンドラー
- `hiromachi/templates/`：Jinjaテンプレート
- `hiromachi/static/`：CSSなどの静的ファイル
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
| `users.me` | GET | `/me` | 自分の活動と集計 |

Flaskのルート表には、上記8ルートに静的ファイル用の`static`を加えた9ルートがあります。

## 6. 初版のデータ

初版で使用するテーブルは次の4つです。

- `users`
- `activities`
- `waste_types`
- `activity_waste_types`

活動とゴミの種類は中間テーブルによる多対多です。活動作成と種類の関連付けは、同じトランザクションで保存します。

## 7. 保存先と環境変数

- SQLite：`instance/hiromachi.sqlite3`
- サーバー側セッション：`instance/sessions/`
- 将来の画像：追加する場合も`instance/`配下。初版では未実装
- 秘密情報：`.env`
- 設定例：`.env.example`

`.env`、SQLiteファイル、セッションファイル、将来のアップロード実体はGitへ追加しません。

主な環境変数は`SECRET_KEY`、`DATABASE_PATH`、`SESSION_DIR`、`SESSION_LIFETIME_DAYS`、`SESSION_COOKIE_SECURE`です。本番では推測できない`SECRET_KEY`とHTTPS用Cookie設定が必要です。

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

既存コードと設計資料が食い違う場合は、勝手に片方へ合わせず差異を報告してください。仕様を変更するときは、該当する設計書、実装、テストを同じ作業内で更新します。

## 10. 現在の状態

- MVPのコードは実装済みです。
- Flaskのアプリルート8件と静的ファイルルートが登録済みです。
- 2026年10月12日時点で自動テスト15件が成功しています。
- 完了済み機能を、明確な理由なく作り直さないでください。

## 11. 初版の対象外

次の機能は、要件と設計が更新されるまで実装しません。

- 活動写真
- 活動記録の編集・削除
- メールアドレス、メール認証、パスワード再設定
- 地図、位置情報、清掃ルート
- ランキング、バッジ、連続記録
- コメント、リアクション、フォロー
- 清掃イベント、通知
- 外部ストレージ、管理者画面、JSON API

