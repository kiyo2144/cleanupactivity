# ひろまち

地域のゴミ拾い・清掃活動を記録し、住民同士で共有するFlaskアプリです。

## 開発環境

- Python 3.13
- Flask
- Peewee
- SQLite

## セットアップ

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

検証済みと同じ依存バージョンを使う場合は、続けて次を実行します。

```powershell
python -m pip install -r requirements-lock.txt
```

生成した値を`.env`の`SECRET_KEY`へ設定してください。

## データベース初期化と起動

```powershell
flask --app hiromachi init-db
flask --app hiromachi run --debug
```

ブラウザーで`http://127.0.0.1:5000`を開きます。

## テスト

```powershell
pytest
```

カバレッジ付きで実行する場合は次のとおりです。

```powershell
pytest --cov=hiromachi --cov-report=term-missing
```
