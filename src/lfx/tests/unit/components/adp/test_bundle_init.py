def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"
    assert ADPMCPComponent.name == "ADPMCP"
