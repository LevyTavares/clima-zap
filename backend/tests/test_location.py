from app.core.location import get_location_coords


def test_location_disambiguation():
    loc_jn = get_location_coords("Juazeiro do Norte")
    assert loc_jn["name"] == "Juazeiro do Norte"
    assert loc_jn["state"] == "CE"

    loc_ba = get_location_coords("Juazeiro BA")
    assert loc_ba["name"] == "Juazeiro"
    assert loc_ba["state"] == "BA"

    loc_crato = get_location_coords("crato")
    assert loc_crato["name"] == "Crato"
