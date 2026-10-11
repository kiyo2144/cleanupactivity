# ひろまち データベース設計書

## 1. この文書について

この文書は、「ひろまち」初版（MVP）で使用するSQLiteデータベースの構造を定めるものです。機能要件は`docs/requirements.md`、画面と処理の流れは`docs/routes.md`を基準とします。

- ORMにはPeeweeを使用します。
- 日時はUTCで保存し、画面表示時に`Asia/Tokyo`へ変換します。
- 初版で使用するテーブルと、将来機能の候補テーブルを分けて記載します。
- 本文中の型は、SQLite上の型と対応するPeeweeフィールドを併記します。

## 2. 初版のテーブル一覧

| テーブル名 | 用途 | 必要な理由 |
| --- | --- | --- |
| `users` | 利用者の認証情報と表示名を保存する | ログインした利用者を識別し、活動の投稿者を特定するため |
| `activities` | 清掃活動の内容と成果を保存する | 活動の登録、一覧、詳細、マイページの集計に必要なため |
| `waste_types` | 選択可能なゴミの種類を管理する | 種類名の表記揺れを防ぎ、将来の集計にも利用できるようにするため |
| `activity_waste_types` | 活動とゴミの種類を関連付ける | 1件の活動で複数のゴミの種類を選択できるようにするため |

初版では、セッション、フラッシュメッセージ、確認用パスワード、マイページの集計結果をSQLiteの業務テーブルへ保存しません。

- 認証セッションはFlask-SessionとCacheLibを使い、`instance/sessions`へサーバー側保存します。ブラウザーのCookieにはセッション識別子だけを保持します。
- 確認用パスワードは登録時の検証だけに使用します。
- 活動回数、累計活動時間、累計袋数は`activities`から都度集計します。

## 3. `users`テーブル

### 3.1 用途

ログインに必要なユーザー名とパスワードハッシュ、他の利用者へ表示する表示名を保存します。

### 3.2 カラム

| カラム名 | SQLite型 | Peeweeフィールド | 必須 | キー・制約 | 説明 |
| --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | `AutoField` | 必須 | 主キー | 利用者を識別する連番ID |
| `username` | VARCHAR(30) | `CharField(max_length=30)` | 必須 | 一意、大小文字を区別しない | ログインに使用するユーザー名 |
| `display_name` | VARCHAR(50) | `CharField(max_length=50)` | 必須 | なし | 活動一覧などで公開する名前 |
| `password_hash` | VARCHAR(255) | `CharField(max_length=255)` | 必須 | なし | ハッシュ化されたパスワード |
| `created_at` | DATETIME | `DateTimeField` | 必須 | なし | アカウント作成日時（UTC） |

### 3.3 制約

- 主キー：`id`
- ユニーク制約：`username`
- `username`はASCIIの半角英字、数字、アンダースコアだけを許可します。
- `username`は3～30文字とします。
- `username`の前後に空白を許可しません。
- `username`はSQLiteの`NOCASE`照合順序を使用し、`Sato`と`sato`を同じ値として扱います。
- `display_name`は前後の空白を除いた状態で1～50文字とします。
- `password_hash`は空文字を許可しません。

想定するチェック制約は次のとおりです。

- `length(username) BETWEEN 3 AND 30`
- `username NOT GLOB '*[^A-Za-z0-9_]*'`
- `length(trim(display_name)) BETWEEN 1 AND 50`
- `length(password_hash) > 0`

許可文字や前後空白はアプリケーション側でも検証します。SQLiteの`NOCASE`がASCII向けのため、ユーザー名をASCIIに限定する仕様と整合します。

### 3.4 インデックス

- `username`のユニークインデックス
  - ログイン時の検索と重複防止に使用します。
  - `NOCASE`の照合順序を列とインデックスで一致させます。

## 4. `activities`テーブル

### 4.1 用途

清掃活動の日付、場所、所要時間、成果、コメント、投稿者を保存します。

### 4.2 カラム

| カラム名 | SQLite型 | Peeweeフィールド | 必須 | キー・制約 | 説明 |
| --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | `AutoField` | 必須 | 主キー | 活動を識別する連番ID |
| `user_id` | INTEGER | `ForeignKeyField(User)` | 必須 | 外部キー | 投稿者。`users.id`を参照 |
| `activity_date` | DATE | `DateField` | 必須 | チェック | 実際に清掃した日 |
| `location` | VARCHAR(100) | `CharField(max_length=100)` | 必須 | チェック | 利用者が入力した活動場所 |
| `duration_minutes` | INTEGER | `IntegerField` | 必須 | チェック | 所要時間（分） |
| `bag_count` | INTEGER | `IntegerField` | 必須 | チェック | 拾ったゴミのおおよその袋数 |
| `comment` | TEXT | `TextField(null=True)` | 任意 | チェック | 活動の感想や補足 |
| `created_at` | DATETIME | `DateTimeField` | 必須 | なし | 記録の作成日時（UTC） |
| `updated_at` | DATETIME | `DateTimeField` | 必須 | なし | 記録の最終更新日時（UTC） |

### 4.3 制約

- 主キー：`id`
- 外部キー：`user_id` → `users.id`
- ユーザー削除時：`ON DELETE RESTRICT`
  - 活動が存在するユーザーは削除できません。
- `activity_date`は当日以前の日付とします。
- `location`は前後の空白を除いた状態で1～100文字とします。
- `duration_minutes`は1～1440の整数とします。
- `bag_count`は0～99の整数とします。
- `comment`はNULLまたは500文字以内とします。
- 作成時は`created_at`と`updated_at`へ同じUTC日時を設定します。

想定するチェック制約は次のとおりです。

- `length(trim(location)) BETWEEN 1 AND 100`
- `duration_minutes BETWEEN 1 AND 1440`
- `bag_count BETWEEN 0 AND 99`
- `comment IS NULL OR length(comment) <= 500`

`activity_date`が未来でないことは、リクエストを処理する日の影響を受けるため、アプリケーション側で必ず検証します。SQLiteのチェック制約では、保存時点に依存する日付判定を行いません。

### 4.4 インデックス

初版で次の複合インデックスを作成します。

| インデックス対象 | 用途 |
| --- | --- |
| `created_at DESC, id DESC` | 「みんなの活動」を新しい順に安定して表示する |
| `user_id, created_at DESC, id DESC` | マイページで本人の活動を新しい順に取得する |

`activity_date`は初版で検索条件に使わないため、単独インデックスは作成しません。日付検索機能を追加するときに再検討します。

## 5. `waste_types`テーブル

### 5.1 用途

活動記録で選べるゴミの種類をマスタデータとして管理します。

### 5.2 カラム

| カラム名 | SQLite型 | Peeweeフィールド | 必須 | キー・制約 | 説明 |
| --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | `AutoField` | 必須 | 主キー | ゴミの種類を識別する連番ID |
| `code` | VARCHAR(30) | `CharField(max_length=30)` | 必須 | 一意 | プログラム内で使う変更しない識別子 |
| `name` | VARCHAR(50) | `CharField(max_length=50)` | 必須 | 一意 | 画面へ表示する日本語名 |
| `sort_order` | INTEGER | `IntegerField` | 必須 | 一意、チェック | フォームと詳細画面での表示順 |

### 5.3 初期データ

| `code` | `name` | `sort_order` |
| --- | --- | --- |
| `burnable` | 燃えるごみ | 1 |
| `plastic_bottle` | プラスチック・ペットボトル | 2 |
| `cans_bottles` | 缶・びん | 3 |
| `other` | その他 | 4 |

### 5.4 制約とインデックス

- 主キー：`id`
- ユニーク制約：`code`、`name`、`sort_order`
- チェック制約：`length(code) BETWEEN 1 AND 30`
- チェック制約：`length(trim(name)) BETWEEN 1 AND 50`
- チェック制約：`sort_order > 0`
- 各ユニーク制約に対応するユニークインデックスを使用します。
- 初期データは`code`を基準に冪等に登録し、初期化を複数回実行しても重複させません。

初版の画面では4種類を固定候補として扱います。表示名を変更する場合でも、関連付けには変更しない`code`とIDを使用します。

## 6. `activity_waste_types`テーブル

### 6.1 用途

1件の活動と、そこで拾った1種類以上のゴミを関連付ける中間テーブルです。

### 6.2 カラム

| カラム名 | SQLite型 | Peeweeフィールド | 必須 | キー・制約 | 説明 |
| --- | --- | --- | --- | --- | --- |
| `activity_id` | INTEGER | `ForeignKeyField(Activity)` | 必須 | 複合主キー、外部キー | `activities.id`を参照 |
| `waste_type_id` | INTEGER | `ForeignKeyField(WasteType)` | 必須 | 複合主キー、外部キー | `waste_types.id`を参照 |

### 6.3 制約とインデックス

- 複合主キー：`activity_id, waste_type_id`
  - 同じ活動へ同じ種類を重複登録できません。
- 外部キー：`activity_id` → `activities.id`
  - 活動削除時は`ON DELETE CASCADE`とし、関連行だけを同時に削除します。
- 外部キー：`waste_type_id` → `waste_types.id`
  - 使用中のマスタ削除を防ぐため`ON DELETE RESTRICT`とします。
- 複合主キーのインデックスに加え、`waste_type_id`単独のインデックスを候補とします。
  - 初版では種類から活動を検索しないため必須ではありません。

中間テーブルだけでは「活動に種類が一つ以上必要」という条件を表現できません。活動と関連行を一つのトランザクションで保存し、アプリケーション側で一つ以上選択されていることを保証します。

## 7. テーブル間の関係

```text
users
  1
  |
  | 投稿者
  |
  N
activities
  1
  |
  | activity_waste_types
  |
  N          N
              \
               1
          waste_types
```

- `users`と`activities`は1対多です。
  - 1人の利用者は0件以上の活動を持ちます。
  - 1件の活動には必ず1人の投稿者がいます。
- `activities`と`waste_types`は、`activity_waste_types`を介した多対多です。
  - 1件の活動には1種類以上のゴミが関連します。
  - 1種類のゴミは複数の活動に関連できます。

## 8. Peeweeで実装するときの注意点

### 8.1 モデルと命名

- モデル名は`User`、`Activity`、`WasteType`、`ActivityWasteType`とします。
- `Meta.table_name`で、この文書の複数形テーブル名を明示します。
- すべてのモデルが共通の`BaseModel`を継承し、同じデータベース接続を使用する構成にします。
- 実行環境ごとにDBを差し替えられるよう、`DatabaseProxy`などで接続を注入できる構成にします。

### 8.2 SQLite接続

- 接続時に`foreign_keys=1`を有効にします。無効だと`RESTRICT`や`CASCADE`が機能しません。
- Flaskのリクエスト開始時に必要なら接続し、終了時に閉じます。
- 既に開いている接続を重ねて開いたり、閉じた接続を利用したりしないようにします。
- SQLiteファイルはソースコードとは分け、書き込み可能な`instance`領域などへ保存します。

### 8.3 ユーザー名

- `username`には`collation='NOCASE'`を指定し、ユニーク制約も同じ照合順序で作成します。
- 保存前に前後の空白を除き、半角英数字とアンダースコアだけであることを検証します。
- ログイン検索でも登録時と同じ大小文字を区別しないルールを使用します。
- ユニーク制約違反は事前確認だけに頼らず、保存時の`IntegrityError`も処理します。

### 8.4 パスワード

- `password_hash`だけを保存し、平文パスワードと確認用パスワードは保存しません。
- ハッシュ化と照合にはWerkzeugなど実績のあるライブラリを使用します。
- パスワード、ハッシュ、認証フォームの内容をログへ出力しません。

### 8.5 日時

- 日時の初期値には、アプリ起動時に評価された値ではなく、保存時にUTCの現在日時を返す関数を指定します。
- SQLiteの日時にはタイムゾーン情報が保持されないため、「保存値はUTC」という規約をアプリ全体で統一します。
- 画面へ出す直前にUTCとして解釈し、`Asia/Tokyo`へ変換します。
- `updated_at`はPeeweeが自動更新しないため、将来編集機能を追加するときは更新処理で明示的に変更します。
- 初版は編集機能を持たないため、作成後の`updated_at`は`created_at`と同じ値です。

### 8.6 トランザクション

- 活動作成と`activity_waste_types`の登録は`database.atomic()`内で行います。
- 種類が0件の場合や関連行の保存に失敗した場合は、活動本体も含めて取り消します。
- ユーザー登録も、ハッシュ生成後の保存に失敗した場合に中途半端なデータを残さないようにします。

### 8.7 一覧と集計

- 一覧は`created_at DESC, id DESC`で並べ、同じ作成日時でも順序が変わらないようにします。
- マイページでは`user_id`で絞り込み、`COUNT`と`SUM`で活動回数、累計時間、累計袋数を算出します。
- 活動が0件の場合、`SUM`はNULLになるため0へ変換します。
- ゴミの種類を一覧表示するときは関連データをまとめて取得し、活動ごとに追加クエリが発生するN+1問題を避けます。

### 8.8 初期化と変更管理

- テーブルは`users`、`waste_types`、`activities`、`activity_waste_types`の依存順を考慮して作成します。
- テーブル作成後に4件のゴミ種類マスタを登録します。
- 初期化処理は既存データを消さず、繰り返し実行できるものにします。
- `create_tables(..., safe=True)`は既存テーブルの列を更新しません。運用開始後のスキーマ変更には、バックアップを取得したうえでバージョン管理されたマイグレーションを使用します。
- テストでは本番用SQLiteファイルを使わず、テスト専用の一時データベースを使用します。

## 9. 将来追加を検討するテーブル

以下は初版では作成しません。対応する機能を実装すると決まった時点で、改めて要件と詳細設計を行います。

| 候補テーブル | 対応する将来機能 | 想定する関係 |
| --- | --- | --- |
| `activity_photos` | 活動写真の添付 | `activities`と1対0または1。将来複数枚にする場合は1対多 |
| `comments` | 他の利用者によるコメント | `users`および`activities`と多対1 |
| `reactions` | 活動へのリアクション | `users`と`activities`を結ぶ中間テーブル |
| `events` | 合同清掃イベントの募集 | 作成者として`users`を参照 |
| `event_participants` | イベントへの参加 | `users`と`events`を結ぶ中間テーブル |
| `cleanup_routes` | 清掃ルートの記録 | `activities`と1対1または1対多 |

ランキング、バッジ、通知は仕様が未確定のため、現時点ではテーブル構造を定めません。活動記録の編集・削除は既存テーブルの操作であり、それだけを理由に新しいテーブルは追加しません。

## 10. 初版スキーマの確認事項

- 初版のテーブルは4つだけであること。
- ユーザー名が大小文字を区別せず一意であること。
- パスワードを平文で保存しないこと。
- 活動には必ず投稿者が存在すること。
- 活動があるユーザーを削除できないこと。
- 活動にゴミの種類を一つ以上関連付けること。
- 活動作成と種類の関連付けを一つのトランザクションで処理すること。
- 日時をUTCで保存すること。
- 一覧とマイページに必要な複合インデックスがあること。
- 将来機能の候補テーブルを初版では作成しないこと。
