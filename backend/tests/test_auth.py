def signup(client, email="a@b.com", password="password1", name="A"):
    return client.post("/api/v1/auth/signup", json={"email": email, "password": password, "name": name})


def test_signup_sets_cookies_and_me(client):
    r = signup(client)
    assert r.status_code == 201
    assert "access_token" in r.cookies and "refresh_token" in r.cookies
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "a@b.com"


def test_signup_duplicate_email(client):
    signup(client)
    r = signup(client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_login_wrong_password(client):
    signup(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_token(client):
    signup(client)
    old_refresh = client.cookies["refresh_token"]
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    assert client.cookies["refresh_token"] != old_refresh
    # old token is revoked
    client.cookies.set("refresh_token", old_refresh)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_clears_session(client):
    signup(client)
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.delete("access_token")
    assert client.get("/api/v1/auth/me").status_code == 401
