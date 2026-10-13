from app.core.location import get_location_coords


def test_get_location_coords_crajubar():
    # Teste Barbalha
    loc_barbalha = get_location_coords("barbalha")
    assert loc_barbalha["name"] == "Barbalha"
    assert loc_barbalha["latitude"] == -7.3108

    # Teste Juazeiro do Norte (com e sem acento / parcial)
    loc_juazeiro = get_location_coords("Juazeiro do Norte")
    assert loc_juazeiro["name"] == "Juazeiro do Norte"

    loc_juazeiro_parcial = get_location_coords("juazeiro")
    assert loc_juazeiro_parcial["name"] == "Juazeiro do Norte"

    # Teste Crato
    loc_crato = get_location_coords("Crato")
    assert loc_crato["name"] == "Crato"


def test_get_location_coords_fallback():
    # Cidade fora do Crajubar ou None -> Retorna Barbalha
    loc_desconhecida = get_location_coords("Fortaleza")
    assert loc_desconhecida["name"] == "Barbalha"

    loc_none = get_location_coords(None)
    assert loc_none["name"] == "Barbalha"