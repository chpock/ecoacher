from ecoacher.config.constants import app_id_for_profile, spell_server_name_for_profile


def test_app_id_for_profile_values() -> None:
    assert app_id_for_profile("normal") == "ecoacher"
    assert app_id_for_profile("dev") == "ecoacher-dev"


def test_spell_server_name_for_profile_values() -> None:
    assert spell_server_name_for_profile("normal") == "ecoacher-spell"
    assert spell_server_name_for_profile("dev") == "ecoacher-spell-dev"
