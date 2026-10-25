from app.core.location import get_location_coords, parse_coordinates


def test_parse_coordinates_accepts_lat_lon_pairs():
    pair = parse_coordinates("-7.2342, -39.4086")
    assert pair["latitude"] == -7.2342
    assert pair["longitude"] == -39.4086
    assert pair["name"] == "-7.2342, -39.4086"

    spaced = parse_coordinates("-7.2342 -39.4086")
    assert spaced["latitude"] == -7.2342
    assert spaced["longitude"] == -39.4086


def test_parse_coordinates_rejects_invalid_input():
    assert parse_coordinates("Crato") is None
    assert parse_coordinates("") is None
    assert parse_coordinates("-99.0, 0.0") is None  # latitude fora de faixa
    assert parse_coordinates("0.0, 200.0") is None  # longitude fora de faixa
    assert parse_coordinates("7,2 -39,3") is None  # vírgula decimal ambígua


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