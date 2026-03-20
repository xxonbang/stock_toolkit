from unittest.mock import patch, MagicMock
from core.kis_client import KISClient


def test_get_asking_price_parses_response():
    """KIS 호가 API 응답을 올바르게 파싱하는지 검증"""
    mock_response = {
        "rt_cd": "0",
        "output1": {
            "askp1": "184000", "askp2": "184500", "askp3": "185000",
            "askp4": "185500", "askp5": "186000",
            "bidp1": "183500", "bidp2": "183000", "bidp3": "182500",
            "bidp4": "182000", "bidp5": "181500",
            "askp_rsqn1": "1000", "askp_rsqn2": "2000", "askp_rsqn3": "1500",
            "askp_rsqn4": "800", "askp_rsqn5": "600",
            "bidp_rsqn1": "1200", "bidp_rsqn2": "1800", "bidp_rsqn3": "900",
            "bidp_rsqn4": "700", "bidp_rsqn5": "500",
            "total_askp_rsqn": "5900",
            "total_bidp_rsqn": "5100",
        },
    }
    client = KISClient()
    client.access_token = "fake_token"
    client._token_expires_at = None

    with patch.object(client, "ensure_token", return_value=True), \
         patch("core.kis_client.requests.get") as mock_get:
        mock_get.return_value = MagicMock(json=lambda: mock_response)
        result = client.get_asking_price("005930")

    assert result is not None
    assert len(result["ask_levels"]) == 5
    assert len(result["bid_levels"]) == 5
    assert result["ask_levels"][0]["price"] == 184000
    assert result["ask_levels"][0]["qty"] == 1000
    assert result["bid_levels"][0]["price"] == 183500
    assert result["total_ask_qty"] == 5900
    assert result["total_bid_qty"] == 5100


def test_get_asking_price_returns_none_on_failure():
    """API 실패 시 None 반환"""
    client = KISClient()
    with patch.object(client, "ensure_token", return_value=False):
        assert client.get_asking_price("005930") is None


def test_get_investor_parses_response():
    """KIS 투자자동향 API 응답을 올바르게 파싱하는지 검증"""
    mock_response = {
        "rt_cd": "0",
        "output": [
            {
                "stck_bsop_date": "20260320",
                "prsn_ntby_qty": "-5000",
                "frgn_ntby_qty": "3000",
                "orgn_ntby_qty": "2000",
                "prsn_ntby_tr_pbmn": "-915000000",
                "frgn_ntby_tr_pbmn": "549000000",
                "orgn_ntby_tr_pbmn": "366000000",
            }
        ],
    }
    client = KISClient()
    client.access_token = "fake_token"
    client._token_expires_at = None

    with patch.object(client, "ensure_token", return_value=True), \
         patch("core.kis_client.requests.get") as mock_get:
        mock_get.return_value = MagicMock(json=lambda: mock_response)
        result = client.get_investor("005930")

    assert result is not None
    assert len(result) >= 1
    assert result[0]["date"] == "20260320"
    assert result[0]["individual_net_qty"] == -5000
    assert result[0]["foreign_net_qty"] == 3000
    assert result[0]["institution_net_qty"] == 2000


def test_get_investor_returns_none_on_failure():
    """API 실패 시 None 반환"""
    client = KISClient()
    with patch.object(client, "ensure_token", return_value=False):
        assert client.get_investor("005930") is None
