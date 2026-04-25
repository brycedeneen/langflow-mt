def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
        ADPToolsComponent,
        ADPTriggerComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPToolsComponent.name == "ADPTools"
    assert ADPTriggerComponent.name == "ADPTrigger"
    assert ADPMCPComponent.name == "ADPMCP"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"


def test_bundle_all_lists_only_kept_components():
    from lfx.components.adp import __all__ as exports

    assert set(exports) == {
        "ADPAPIRequestComponent",
        "ADPAuthComponent",
        "ADPMCPComponent",
        "ADPToolsComponent",
        "ADPTriggerComponent",
    }
