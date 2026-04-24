def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
        ADPTriggerComponent,
        ADPWorkerAssignmentToolsComponent,
        ADPWorkerAssignmentV3ToolsComponent,
        ADPWorkerBiologicalToolsComponent,
        ADPWorkerCompensationToolsComponent,
        ADPWorkerDemographicToolsComponent,
        ADPWorkerDeploymentToolsComponent,
        ADPWorkerHrProfilesToolsComponent,
        ADPWorkerIdentificationToolsComponent,
        ADPWorkerLeavesToolsComponent,
        ADPWorkerLifecycleToolsComponent,
        ADPWorkerPersonalCommunicationToolsComponent,
        ADPWorkerToolsComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"
    assert ADPMCPComponent.name == "ADPMCP"
    assert ADPWorkerToolsComponent.name == "ADPWorkerTools"
    assert ADPTriggerComponent.name == "ADPTrigger"
    assert ADPWorkerCompensationToolsComponent.name == "ADPWorkerCompensationTools"
    assert ADPWorkerPersonalCommunicationToolsComponent.name == "ADPWorkerPersonalCommunicationTools"
    assert ADPWorkerDeploymentToolsComponent.name == "ADPWorkerDeploymentTools"
    assert ADPWorkerIdentificationToolsComponent.name == "ADPWorkerIdentificationTools"
    assert ADPWorkerAssignmentToolsComponent.name == "ADPWorkerAssignmentTools"
    assert ADPWorkerDemographicToolsComponent.name == "ADPWorkerDemographicTools"
    assert ADPWorkerBiologicalToolsComponent.name == "ADPWorkerBiologicalTools"
    assert ADPWorkerHrProfilesToolsComponent.name == "ADPWorkerHrProfilesTools"
    assert ADPWorkerLeavesToolsComponent.name == "ADPWorkerLeavesTools"
    assert ADPWorkerLifecycleToolsComponent.name == "ADPWorkerLifecycleTools"
    assert ADPWorkerAssignmentV3ToolsComponent.name == "ADPWorkerAssignmentV3Tools"
