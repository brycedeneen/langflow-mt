def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPApplicantOnboardingToolsComponent,
        ADPAuthComponent,
        ADPBenefitsToolsComponent,
        ADPDataCollectionEntriesToolsComponent,
        ADPDeductionConfigurationsToolsComponent,
        ADPJobApplicantsToolsComponent,
        ADPJobRequisitionsToolsComponent,
        ADPMCPComponent,
        ADPPayDataInputToolsComponent,
        ADPPayDistributionsToolsComponent,
        ADPPayStatementsToolsComponent,
        ADPTalentToolsComponent,
        ADPTeamTimeCardsToolsComponent,
        ADPTimeCardsToolsComponent,
        ADPTimeOffToolsComponent,
        ADPTriggerComponent,
        ADPUSTaxProfilesToolsComponent,
        ADPWorkSchedulesToolsComponent,
        ADPWorkerBusinessCommunicationToolsComponent,
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
    assert ADPTalentToolsComponent.name == "ADPTalentTools"
    assert ADPPayStatementsToolsComponent.name == "ADPPayStatementsTools"
    assert ADPBenefitsToolsComponent.name == "ADPBenefitsTools"
    assert ADPDataCollectionEntriesToolsComponent.name == "ADPDataCollectionEntriesTools"
    assert ADPDeductionConfigurationsToolsComponent.name == "ADPDeductionConfigurationsTools"
    assert ADPTimeCardsToolsComponent.name == "ADPTimeCardsTools"
    assert ADPTimeOffToolsComponent.name == "ADPTimeOffTools"
    assert ADPUSTaxProfilesToolsComponent.name == "ADPUSTaxProfilesTools"
    assert ADPWorkerBusinessCommunicationToolsComponent.name == "ADPWorkerBusinessCommunicationTools"
    assert ADPWorkSchedulesToolsComponent.name == "ADPWorkSchedulesTools"
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
