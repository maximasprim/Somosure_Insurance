"""Formats Safaricom is strict about (phone, amount, timestamp, password, callback
address, callback body, status-query answer). Pure unit tests."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.payments import daraja_util as du


@pytest.mark.parametrize("raw", ["0712345678", "+254712345678", "254712345678", "712345678", "0712 345 678", "0112345678"])
def test_phone_numbers_are_normalised_to_254_form(raw):
    assert du.normalise_msisdn(raw).startswith("254") and len(du.normalise_msisdn(raw)) == 12


@pytest.mark.parametrize("raw", [None, "", "12345", "0812345678", "abc", "07123456789"])
def test_bad_phone_numbers_are_refused(raw):
    with pytest.raises(ValueError):
        du.normalise_msisdn(raw)


def test_amounts_are_whole_shillings_rounded_half_up_and_never_below_one():
    assert du.whole_shillings("1000.49") == 1000
    assert du.whole_shillings("1000.50") == 1001
    assert du.whole_shillings(Decimal("0.2")) == 1
    assert du.amounts_match("1001.00", "1000.50") is True
    assert du.amounts_match("1000", "1000.50") is False
    assert du.amounts_match("garbage", "1000") is False


def test_timestamp_is_east_africa_time_and_password_is_base64_of_the_three_parts():
    ts = du.daraja_timestamp(datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc))
    assert ts == "20261012130000"  # UTC+3
    import base64

    assert base64.b64decode(du.daraja_password("174379", "KEY", ts)).decode() == "174379KEY20261012130000"


def test_callback_address_rules():
    ok = du.callback_url("https://somosure-backend.onrender.com/", "a-long-random-secret-123")
    assert ok == "https://somosure-backend.onrender.com/api/v1/webhooks/pay/a-long-random-secret-123"
    with pytest.raises(ValueError):
        du.callback_url("http://insecure.example.com", "a-long-random-secret-123")  # must be https
    with pytest.raises(ValueError):
        du.callback_url("https://x.example.com", "short")  # secret too short
    with pytest.raises(ValueError):
        du.callback_url("https://x.example.com", "contains-mpesa-word-123456")  # Safaricom rejects the word


def test_a_successful_callback_is_parsed():
    body = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_1", "ResultCode": 0, "ResultDesc": "ok", "CallbackMetadata": {"Item": [
        {"Name": "Amount", "Value": 1500}, {"Name": "MpesaReceiptNumber", "Value": "QJK123"}, {"Name": "PhoneNumber", "Value": 254712345678}]}}}}
    parsed = du.parse_stk_callback(body)
    assert parsed["checkout_id"] == "ws_CO_1" and parsed["result_code"] == 0 and parsed["amount"] == 1500 and parsed["receipt"] == "QJK123"


def test_a_cancelled_callback_has_no_metadata_and_a_garbage_body_is_none():
    cancelled = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_2", "ResultCode": 1032, "ResultDesc": "cancelled"}}}
    parsed = du.parse_stk_callback(cancelled)
    assert parsed["result_code"] == 1032 and parsed["amount"] is None
    assert du.parse_stk_callback({"nope": 1}) is None
    assert du.parse_stk_callback(None) is None


def test_status_query_answers():
    assert du.interpret_query_response({"ResultCode": "0"})[0] == "successful"
    assert du.interpret_query_response({"ResultCode": "1032"})[0] == "failed"
    # still being processed: an error-style body with no ResultCode = no final answer yet
    assert du.interpret_query_response({"errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"})[0] is None
    assert du.interpret_query_response({})[0] is None
