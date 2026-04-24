def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPApplicantOnboardingToolsComponent,
        ADPAuthComponent,
        ADPJobApplicantsToolsComponent,
        ADPJobRequisitionsToolsComponent,
        ADPMCPComponent,
        ADPPayDataInputToolsComponent,
        ADPPayDistributionsToolsComponent,
        ADPTeamTimeCardsToolsComponent,
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
        ADPWorkerPayrollInstructionsToolsComponent,
        ADPWorkerPersonalCommunicationToolsComponent,
        ADPWorkerToolsComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPJobApplicantsToolsComponent.name == "ADPJobApplicantsTools"
    assert ADPJobRequisitionsToolsComponent.name == "ADPJobRequisitionsTools"
    assert ADPTeamTimeCardsToolsComponent.name == "ADPTeamTimeCardsTools"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"
    assert ADPApplicantOnboardingToolsComponent.name == "ADPApplicantOnboardingTools"
    assert ADPMCPComponent.name == "ADPMCP"
    assert ADPPayDataInputToolsComponent.name == "ADPPayDataInputTools"
    assert ADPPayDistributionsToolsComponent.name == "ADPPayDistributionsTools"
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
    assert ADPWorkerPayrollInstructionsToolsComponent.name == "ADPWorkerPayrollInstructionsTools"
    assert ADPWorkerAssignmentV3ToolsComponent.name == "ADPWorkerAssignmentV3Tools"
