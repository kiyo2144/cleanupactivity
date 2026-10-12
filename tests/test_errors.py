def test_not_found_uses_html_error_page(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert "ページが見つかりません" in response.text


def test_csrf_rejects_state_changing_request(app):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    response = client.post(
        "/register",
        data={
            "username": "new_user",
            "display_name": "利用者",
            "password": "password123",
            "password_confirm": "password123",
        },
    )

    assert response.status_code == 400
    assert "リクエストを処理できませんでした" in response.text


def test_request_over_size_limit_uses_413_page(client, app):
    response = client.post(
        "/register",
        data={"username": "x" * (app.config["MAX_CONTENT_LENGTH"] + 1)},
    )

    assert response.status_code == 413
    assert "写真のファイルサイズが大きすぎます" in response.text
