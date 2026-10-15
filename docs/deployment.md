# ひろまち デプロイ・運用手順

## 1. 現在の公開環境

- 公開先：PythonAnywhere Beginner
- コード配置：`~/camp-app`
- 仮想環境：`~/.virtualenvs/camp-app`
- WSGI入口：リポジトリ直下の`wsgi.py`が公開する`application`
- アプリ読込指定：`wsgi:application`

2026年10月14日までに、公開環境の主要画面とiPhone実機からの写真投稿・画像変換を確認済みです。2026年10月16日に清掃ルートと「ありがとう」の反映、7テーブル、既存活動・写真の維持を確認済みです。アカウントのパスワード、秘密鍵、利用者データはこの文書へ記載しません。

## 2. 保存先

環境変数で変更していない場合、実行時データは次へ保存します。

- SQLite：`~/camp-app/instance/hiromachi.sqlite3`
- サーバー側セッション：`~/camp-app/instance/sessions/`
- 活動写真：`~/camp-app/instance/uploads/`
- 本番用環境変数：`~/camp-app/.env`

`.env`、DB、セッション、活動写真はGit管理しません。

## 3. 通常の更新手順

PythonAnywhereのBashコンソールで実行します。

```bash
cd ~/camp-app
git pull origin main
source ~/.virtualenvs/camp-app/bin/activate
```

`pyproject.toml`、`requirements.txt`、`requirements-lock.txt`のいずれかに依存関係の変更がある場合だけ、続けて実行します。

```bash
python -m pip install -r requirements.txt
```

更新後、WebタブのReloadを押し、公開URLで変更した機能と主要導線を確認します。PythonAnywhere上で直接ソースコードを編集しません。

## 4. DB初期化の判断

- コード、テンプレート、CSS、JavaScript、既存カラムを使う処理だけの変更では`init-db`を実行しません。
- 新規環境でDBが存在しない場合は、仮想環境を有効にして`flask --app wsgi:application init-db`を実行します。
- `init-db`は既存テーブルの列変更を行いません。運用開始後にDB構造を変更する場合は、先にバックアップと移行手順を設計します。
- 清掃ルート機能の初回反映では、新規`activity_routes`テーブルを追加するため、DBと活動写真をバックアップしてから`flask --app wsgi:application init-db`を1回実行します。既存5テーブルの列やデータは変更しません。
- 「ありがとう」機能の初回反映では、新規`reactions`テーブルを追加するため、DBと活動写真を同じ時点でバックアップしてから`flask --app wsgi:application init-db`を1回実行します。既存テーブルの列やデータは変更しません。

## 5. 公開後の確認

- 登録、ログイン、活動一覧、活動詳細、マイページ、ログアウトが動作する。
- 活動の作成・編集・削除が本人だけに許可される。
- 写真なしの投稿と、対応画像の投稿・表示が動作する。
- ルートなしの投稿と、地図で入力したルートの作成・編集・解除・詳細表示が動作する。
- 他人の活動で「ありがとう」の送信・取消と件数表示が動作し、本人の活動には操作ボタンが表示されない。
- HTTPSの公開URLをiPhoneで開き、「現在地から始める」の許可・始点追加・ドラッグ修正が動作する。許可を拒否しても手動入力できる。
- 地図上にOpenStreetMapの帰属表示があり、始点・終点が丸められる旨の案内が表示される。
- Reload後もDBの活動と保存写真が維持される。
- Error logに新しい例外が継続して出ていない。

削除確認には、本番で必要な活動ではなくテスト用に新規作成した活動を使用します。

## 6. 未完了の運用確認

- `.env`で`APP_ENV=production`が設定されていること。
- 推測困難な`SECRET_KEY`が設定されていること。値そのものは表示・記録しない。
- HTTPS用に`SESSION_COOKIE_SECURE=true`が設定されていること。
- `instance/hiromachi.sqlite3`と`instance/uploads/`を同じ時点でバックアップし、復元できること。
- PythonAnywhere Beginnerのディスク使用量を定期確認すること。
- Webアプリの公開期限を確認し、必要な時期に延長すること。
- WebタブのError logを定期確認すること。

これらは確認できるまで完了扱いにしません。
