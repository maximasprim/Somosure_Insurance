"""The admin Customers list: everyone, wherever they came from, with what they hold."""

from sqlalchemy import select

from tests.sales_import_fixtures import build_workbook
from tests.test_sales_import_api import _admin, _auth, _make_user, _upload
from tests.test_sales_post_api import P, _link_everyone, _provider
from tests.test_sales_sync_api import _seed_policy

L = "/api/v1/admin/customer-list"


async def _world(client, db_session, seeded_providers):
    """One customer who bought on the platform, one with no policy, three posted from the workbook."""
    from app.models.customer import Customer

    token = await _admin(client, db_session)
    online, policy = await _seed_policy(db_session, seeded_providers[0], "PLAT-1", "20000", name="Online Buyer")
    db_session.add(Customer(full_name="Just Browsing", phone="0722000333", lead_source="website"))
    await db_session.commit()
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    return token, online


async def test_staff_only(client, db_session):
    token = await _make_user(client, db_session, "buyer@example.com", "supersecret1", "customer")
    assert (await client.get(L, headers=_auth(token))).status_code == 403
    assert (await client.get(f"{L}/export", headers=_auth(token))).status_code == 403
    assert (await client.get(L)).status_code in (401, 403)


async def test_one_response_has_the_page_the_counts_and_the_filter_choices(client, db_session, seeded_providers):
    token, _ = await _world(client, db_session, seeded_providers)
    body = (await client.get(L, headers=_auth(token))).json()
    assert set(body) == {"total", "items", "stats", "sources"}
    assert body["stats"]["from_workbook"] == 3 and body["stats"]["with_active_policy"] >= 1
    assert body["stats"]["without_phone"] >= 3  # the workbook clients have no phone number
    assert "workbook" in body["sources"] and "website" in body["sources"]
    row = next(i for i in body["items"] if i["full_name"] == "Online Buyer")
    assert (row["policies"], row["active_policies"], float(row["premium"])) == (1, 1, 20000.0) and row["has_workbook"] is False


async def test_filters_search_and_sorting(client, db_session, seeded_providers):
    token, _ = await _world(client, db_session, seeded_providers)
    get = lambda qs: client.get(f"{L}?{qs}", headers=_auth(token))

    workbook = (await get("lead_source=workbook")).json()
    assert workbook["total"] == 3 and all(i["has_workbook"] and i["phone"] in ("", None) for i in workbook["items"])
    assert {i["full_name"] for i in workbook["items"]} == {"John Doe", "Jane Roe", "Peter Kamau"}

    assert [i["full_name"] for i in (await get("q=online")).json()["items"]] == ["Online Buyer"]
    assert [i["full_name"] for i in (await get("q=0722000333")).json()["items"]] == ["Just Browsing"]  # by phone

    no_policy = (await get("policy=none")).json()
    assert "Just Browsing" in {i["full_name"] for i in no_policy["items"]} and "Online Buyer" not in {i["full_name"] for i in no_policy["items"]}
    assert "Online Buyer" in {i["full_name"] for i in (await get("policy=active")).json()["items"]}
    assert "Just Browsing" not in {i["full_name"] for i in (await get("has_phone=false")).json()["items"]}
    assert "Just Browsing" in {i["full_name"] for i in (await get("has_phone=true&lead_source=website")).json()["items"]}

    names = [i["full_name"] for i in (await get("sort=name&limit=200")).json()["items"]]
    assert names == sorted(names)
    top = (await get("sort=premium&lead_source=workbook")).json()["items"]
    assert float(top[0]["premium"]) >= float(top[-1]["premium"])  # John Doe's 50,000 first

    paged = (await get("limit=2&offset=0")).json()
    assert len(paged["items"]) == 2 and paged["total"] > 2
    assert (await get("limit=2&offset=2")).json()["items"][0]["id"] != paged["items"][0]["id"]
    assert (await get("policy=nonsense")).status_code == 422


async def test_csv_download_follows_the_same_filters(client, db_session, seeded_providers):
    token, _ = await _world(client, db_session, seeded_providers)
    res = await client.get(f"{L}/export?lead_source=workbook", headers=_auth(token))
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    lines = res.text.lstrip("\ufeff").strip().splitlines()
    assert lines[0].startswith("Name,Phone,Email,Source")
    assert len(lines) == 4 and all(",yes" in line for line in lines[1:])  # header + the three workbook customers


async def test_the_existing_customer_page_still_works_and_is_what_a_row_opens(client, db_session, seeded_providers):
    token, online = await _world(client, db_session, seeded_providers)
    listed = (await client.get(f"{L}?q=online", headers=_auth(token))).json()["items"][0]
    assert listed["id"] == str(online.id)
    detail = await client.get(f"/api/v1/admin/customers/{listed['id']}", headers=_auth(token))
    assert detail.status_code == 200 and detail.json()["full_name"] == "Online Buyer"
