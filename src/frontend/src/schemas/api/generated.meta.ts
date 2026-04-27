// AUTO-GENERATED. Edit strict flags per-domain as migrations finish.
// Total registered schema ids: 210.
import { registerSchema } from "@/lib/schema-registry";

export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [
  [
    "api.assistant.get_conversation_api_v1_assistant_flows__flow_id__conversation_get",
    "permissive",
  ],
  [
    "api.assistant.delete_conversation_api_v1_assistant_flows__flow_id__conversation_delete",
    "permissive",
  ],
  [
    "api.assistant.send_message_api_v1_assistant_flows__flow_id__messages_post",
    "permissive",
  ],
  ["api.assistant.get_settings_api_v1_assistant_settings_get", "permissive"],
  ["api.assistant.update_settings_api_v1_assistant_settings_put", "permissive"],
  [
    "api.assistant.greet_conversation_api_v1_assistant_flows__flow_id__greet_post",
    "permissive",
  ],
  [
    "api.assistant.component_assist_messages_api_v1_assistant_components_messages_post",
    "permissive",
  ],
  ["api.chat.build_flow_api_v1_build__flow_id__flow_post", "permissive"],
  ["api.chat.get_build_events_api_v1_build__job_id__events_get", "permissive"],
  ["api.chat.cancel_build_api_v1_build__job_id__cancel_post", "permissive"],
  [
    "api.chat.build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post",
    "permissive",
  ],
  [
    "api.chat.get_build_events_public_api_v1_build_public_tmp__job_id__events_get",
    "permissive",
  ],
  [
    "api.chat.cancel_build_public_api_v1_build_public_tmp__job_id__cancel_post",
    "permissive",
  ],
  ["api.base.get_all_api_v1_all_get", "permissive"],
  [
    "api.base.simplified_run_flow_api_v1_run__flow_id_or_name__post",
    "permissive",
  ],
  [
    "api.base.webhook_run_flow_api_v1_webhook__flow_id_or_name__post",
    "permissive",
  ],
  [
    "api.base.experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post",
    "permissive",
  ],
  ["api.base.get_version_api_v1_version_get", "permissive"],
  ["api.base.get_config_api_v1_config_get", "permissive"],
  [
    "api.validate.validate_mapping_config_api_v1_validate_validate_mapping_config_post",
    "permissive",
  ],
  [
    "api.validate.jsonschema_to_fields_api_v1_validate_jsonschema_to_fields_post",
    "permissive",
  ],
  ["api.flows.create_flow_api_v1_flows__post", "permissive"],
  ["api.flows.read_flows_api_v1_flows__get", "permissive"],
  ["api.flows.delete_multiple_flows_api_v1_flows__delete", "permissive"],
  ["api.flows.read_flow_api_v1_flows__flow_id__get", "permissive"],
  ["api.flows.update_flow_api_v1_flows__flow_id__patch", "permissive"],
  ["api.flows.delete_flow_api_v1_flows__flow_id__delete", "permissive"],
  [
    "api.flows.read_public_flow_api_v1_flows_public_flow__flow_id__get",
    "permissive",
  ],
  [
    "api.flows.generate_or_reset_webhook_api_key_api_v1_flows__flow_id__webhook_api_key_post",
    "permissive",
  ],
  ["api.flows.assign_flow_tags_api_v1_flows__flow_id__tags_put", "permissive"],
  ["api.flows.create_flows_api_v1_flows_batch__post", "permissive"],
  ["api.flows.upload_file_api_v1_flows_upload__post", "permissive"],
  [
    "api.flows.download_multiple_file_api_v1_flows_download__post",
    "permissive",
  ],
  [
    "api.flows.read_basic_examples_api_v1_flows_basic_examples__get",
    "permissive",
  ],
  [
    "api.flows.list_flow_audit_logs_api_v1_flows__flow_id__audit_logs_get",
    "permissive",
  ],
  [
    "api.flow_versions.list_flow_versions_api_v1_flows__flow_id__versions__get",
    "permissive",
  ],
  [
    "api.flow_versions.create_snapshot_api_v1_flows__flow_id__versions__post",
    "permissive",
  ],
  [
    "api.flow_versions.get_single_flow_version_api_v1_flows__flow_id__versions__version_id__get",
    "permissive",
  ],
  [
    "api.flow_versions.delete_version_entry_api_v1_flows__flow_id__versions__version_id__delete",
    "permissive",
  ],
  [
    "api.flow_versions.activate_version_api_v1_flows__flow_id__versions__version_id__activate_post",
    "permissive",
  ],
  ["api.users.add_user_api_v1_users__post", "permissive"],
  ["api.users.read_all_users_api_v1_users__get", "permissive"],
  ["api.users.read_current_user_api_v1_users_whoami_get", "permissive"],
  ["api.users.patch_user_api_v1_users__user_id__patch", "permissive"],
  ["api.users.delete_user_api_v1_users__user_id__delete", "permissive"],
  [
    "api.users.reset_password_api_v1_users__user_id__reset_password_patch",
    "permissive",
  ],
  ["api.files.upload_file_api_v1_files_upload__flow_id__post", "permissive"],
  [
    "api.files.download_file_api_v1_files_download__flow_id___file_name__get",
    "permissive",
  ],
  [
    "api.files.download_image_api_v1_files_images__flow_id___file_name__get",
    "permissive",
  ],
  [
    "api.files.download_profile_picture_api_v1_files_profile_pictures__folder_name___file_name__get",
    "permissive",
  ],
  [
    "api.files.list_profile_pictures_api_v1_files_profile_pictures_list_get",
    "permissive",
  ],
  ["api.files.list_files_api_v1_files_list__flow_id__get", "permissive"],
  [
    "api.files.delete_file_api_v1_files_delete__flow_id___file_name__delete",
    "permissive",
  ],
  ["api.monitor.get_vertex_builds_api_v1_monitor_builds_get", "permissive"],
  [
    "api.monitor.delete_vertex_builds_api_v1_monitor_builds_delete",
    "permissive",
  ],
  [
    "api.monitor.get_message_sessions_api_v1_monitor_messages_sessions_get",
    "permissive",
  ],
  ["api.monitor.get_messages_api_v1_monitor_messages_get", "permissive"],
  ["api.monitor.delete_messages_api_v1_monitor_messages_delete", "permissive"],
  [
    "api.monitor.update_message_api_v1_monitor_messages__message_id__put",
    "permissive",
  ],
  [
    "api.monitor.update_session_id_api_v1_monitor_messages_session__old_session_id__patch",
    "permissive",
  ],
  [
    "api.monitor.delete_messages_session_api_v1_monitor_messages_session__session_id__delete",
    "permissive",
  ],
  [
    "api.monitor.get_transactions_api_v1_monitor_transactions_get",
    "permissive",
  ],
  ["api.traces.get_traces_api_v1_monitor_traces_get", "permissive"],
  [
    "api.traces.delete_traces_by_flow_api_v1_monitor_traces_delete",
    "permissive",
  ],
  ["api.traces.get_trace_api_v1_monitor_traces__trace_id__get", "permissive"],
  [
    "api.traces.delete_trace_api_v1_monitor_traces__trace_id__delete",
    "permissive",
  ],
  ["api.projects.create_project_api_v1_projects__post", "permissive"],
  ["api.projects.read_projects_api_v1_projects__get", "permissive"],
  ["api.projects.read_project_api_v1_projects__project_id__get", "permissive"],
  [
    "api.projects.update_project_api_v1_projects__project_id__patch",
    "permissive",
  ],
  [
    "api.projects.delete_project_api_v1_projects__project_id__delete",
    "permissive",
  ],
  [
    "api.projects.download_file_api_v1_projects_download__project_id__get",
    "permissive",
  ],
  ["api.projects.upload_file_api_v1_projects_upload__post", "permissive"],
  ["api.admin.list_organizations_api_v1_admin_organizations_get", "permissive"],
  [
    "api.admin.create_organization_api_v1_admin_organizations_post",
    "permissive",
  ],
  [
    "api.admin.get_organization_api_v1_admin_organizations__org_id__get",
    "permissive",
  ],
  [
    "api.admin.delete_organization_api_v1_admin_organizations__org_id__delete",
    "permissive",
  ],
  [
    "api.admin.list_members_api_v1_admin_organizations__org_id__members_get",
    "permissive",
  ],
  [
    "api.admin.add_member_api_v1_admin_organizations__org_id__members_post",
    "permissive",
  ],
  [
    "api.admin.remove_member_api_v1_admin_organizations__org_id__members__user_id__delete",
    "permissive",
  ],
  [
    "api.admin.patch_member_role_api_v1_admin_organizations__org_id__members__user_id__patch",
    "permissive",
  ],
  ["api.admin.search_users_api_v1_admin_users_get", "permissive"],
  [
    "api.admin.list_component_metadata_api_v1_admin_metadata_components_get",
    "permissive",
  ],
  [
    "api.admin.get_component_metadata_api_v1_admin_metadata_components__component_name__get",
    "permissive",
  ],
  [
    "api.admin.upsert_component_metadata_api_v1_admin_metadata_components__component_name__put",
    "permissive",
  ],
  [
    "api.admin.delete_component_metadata_api_v1_admin_metadata_components__component_name__delete",
    "permissive",
  ],
  ["api.admin.get_user_detail_api_v1_admin_users__user_id__get", "permissive"],
  [
    "api.admin.set_user_platform_admin_api_v1_admin_users__user_id__platform_admin_patch",
    "permissive",
  ],
  ["api.admin.list_audit_logs_api_v1_admin_audit_logs_get", "permissive"],
  [
    "api.admin.get_audit_log_api_v1_admin_audit_logs__audit_id__get",
    "permissive",
  ],
  ["api.admin.list_notifications_api_v1_admin_notifications_get", "permissive"],
  [
    "api.admin.unread_count_api_v1_admin_notifications_unread_count_get",
    "permissive",
  ],
  [
    "api.admin.mark_read_api_v1_admin_notifications__notification_id__read_post",
    "permissive",
  ],
  [
    "api.admin.mark_all_read_api_v1_admin_notifications_mark_all_read_post",
    "permissive",
  ],
  [
    "api.admin.list_thresholds_api_v1_admin_orgs__org_id__usage_thresholds_get",
    "permissive",
  ],
  [
    "api.admin.create_threshold_api_v1_admin_orgs__org_id__usage_thresholds_post",
    "permissive",
  ],
  [
    "api.admin.patch_threshold_api_v1_admin_usage_thresholds__threshold_id__patch",
    "permissive",
  ],
  [
    "api.admin.delete_threshold_api_v1_admin_usage_thresholds__threshold_id__delete",
    "permissive",
  ],
  [
    "api.admin.list_rules_api_v1_admin_orgs__org_id__alert_rules_get",
    "permissive",
  ],
  [
    "api.admin.create_rule_api_v1_admin_orgs__org_id__alert_rules_post",
    "permissive",
  ],
  [
    "api.admin.patch_rule_api_v1_admin_alert_rules__rule_id__patch",
    "permissive",
  ],
  [
    "api.admin.delete_rule_api_v1_admin_alert_rules__rule_id__delete",
    "permissive",
  ],
  ["api.admin.list_tags_api_v1_admin_tags_get", "permissive"],
  ["api.admin.create_tag_api_v1_admin_tags_post", "permissive"],
  ["api.admin.get_tag_api_v1_admin_tags__tag_id__get", "permissive"],
  ["api.admin.update_tag_api_v1_admin_tags__tag_id__put", "permissive"],
  ["api.admin.delete_tag_api_v1_admin_tags__tag_id__delete", "permissive"],
  ["api.flows.get_starter_projects_api_v1_starter_projects__get", "permissive"],
  ["api.categories.list_categories_api_v1_categories_get", "permissive"],
  ["api.categories.create_category_api_v1_categories_post", "permissive"],
  [
    "api.categories.get_category_api_v1_categories__category_id__get",
    "permissive",
  ],
  [
    "api.categories.patch_category_api_v1_categories__category_id__patch",
    "permissive",
  ],
  [
    "api.categories.delete_category_api_v1_categories__category_id__delete",
    "permissive",
  ],
  [
    "api.memberships.list_my_memberships_api_v1_memberships_me_get",
    "permissive",
  ],
  ["api.tags.list_tags_api_v1_tags_get", "permissive"],
  ["api.templates.list_templates_api_v1_templates_get", "permissive"],
  ["api.templates.create_template_api_v1_templates_post", "permissive"],
  [
    "api.templates.get_template_api_v1_templates__template_id__get",
    "permissive",
  ],
  [
    "api.templates.update_template_api_v1_templates__template_id__put",
    "permissive",
  ],
  [
    "api.templates.patch_template_api_v1_templates__template_id__patch",
    "permissive",
  ],
  [
    "api.templates.delete_template_api_v1_templates__template_id__delete",
    "permissive",
  ],
  [
    "api.templates.assign_template_tags_api_v1_templates__template_id__tags_put",
    "permissive",
  ],
  [
    "api.templates.archive_template_api_v1_templates__template_id__archive_post",
    "permissive",
  ],
  [
    "api.templates.unarchive_template_api_v1_templates__template_id__unarchive_post",
    "permissive",
  ],
  ["api.mcp.handle_sse_api_v1_mcp_sse_get", "permissive"],
  ["api.mcp.handle_messages_api_v1_mcp__post", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable_get", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable_get", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable_get", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable__get", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable__get", "permissive"],
  ["api.mcp.handle_streamable_http_api_v1_mcp_streamable__get", "permissive"],
  [
    "api.mcp_projects.list_project_tools_api_v1_mcp_project__project_id__get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_messages_api_v1_mcp_project__project_id__post",
    "permissive",
  ],
  [
    "api.mcp_projects.update_project_mcp_settings_api_v1_mcp_project__project_id__patch",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_sse_api_v1_mcp_project__project_id__sse_get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_messages_api_v1_mcp_project__project_id___post",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable__get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable__get",
    "permissive",
  ],
  [
    "api.mcp_projects.handle_project_streamable_http_api_v1_mcp_project__project_id__streamable__get",
    "permissive",
  ],
  [
    "api.mcp_projects.install_mcp_config_api_v1_mcp_project__project_id__install_post",
    "permissive",
  ],
  [
    "api.mcp_projects.get_project_composer_url_api_v1_mcp_project__project_id__composer_url_get",
    "permissive",
  ],
  [
    "api.mcp_projects.check_installed_mcp_servers_api_v1_mcp_project__project_id__installed_get",
    "permissive",
  ],
  [
    "api.openai_responses_api.create_response_api_v1_responses_post",
    "permissive",
  ],
  [
    "api.deployments.create_provider_account_api_v1_deployments_providers_post",
    "permissive",
  ],
  [
    "api.deployments.list_provider_accounts_api_v1_deployments_providers_get",
    "permissive",
  ],
  [
    "api.deployments.get_provider_account_api_v1_deployments_providers__provider_id__get",
    "permissive",
  ],
  [
    "api.deployments.delete_provider_account_api_v1_deployments_providers__provider_id__delete",
    "permissive",
  ],
  [
    "api.deployments.update_provider_account_api_v1_deployments_providers__provider_id__patch",
    "permissive",
  ],
  ["api.deployments.create_deployment_api_v1_deployments_post", "permissive"],
  ["api.deployments.list_deployments_api_v1_deployments_get", "permissive"],
  [
    "api.deployments.list_deployment_types_api_v1_deployments_types_get",
    "permissive",
  ],
  [
    "api.deployments.create_deployment_execution_api_v1_deployments_executions_post",
    "permissive",
  ],
  [
    "api.deployments.get_deployment_execution_api_v1_deployments_executions__execution_id__get",
    "permissive",
  ],
  [
    "api.deployments.list_deployment_configs_api_v1_deployments_configs_get",
    "permissive",
  ],
  [
    "api.deployments.get_deployment_api_v1_deployments__deployment_id__get",
    "permissive",
  ],
  [
    "api.deployments.update_deployment_api_v1_deployments__deployment_id__patch",
    "permissive",
  ],
  [
    "api.deployments.delete_deployment_api_v1_deployments__deployment_id__delete",
    "permissive",
  ],
  [
    "api.deployments.get_deployment_status_api_v1_deployments__deployment_id__status_get",
    "permissive",
  ],
  [
    "api.deployments.redeploy_deployment_api_v1_deployments__deployment_id__redeploy_post",
    "permissive",
  ],
  [
    "api.deployments.duplicate_deployment_api_v1_deployments__deployment_id__duplicate_post",
    "permissive",
  ],
  [
    "api.flows_cost.estimate_cost_api_v1_flows__flow_id__estimate_cost_post",
    "permissive",
  ],
  [
    "api.flows_cost.flow_cost_summary_api_v1_flows__flow_id__cost_summary_get",
    "permissive",
  ],
  ["api.orgs_usage.org_usage_kpi_api_v1_orgs__org_id__usage_get", "permissive"],
  [
    "api.orgs_usage.org_usage_chart_api_v1_orgs__org_id__usage_charts_get",
    "permissive",
  ],
  [
    "api.orgs_usage.org_usage_per_flow_api_v1_orgs__org_id__usage_flows_get",
    "permissive",
  ],
  [
    "api.auditlogs.list_org_audit_logs_api_v1_orgs__org_id__audit_logs_get",
    "permissive",
  ],
  [
    "api.agentic.execute_named_flow_api_v1_agentic_execute__flow_name__post",
    "permissive",
  ],
  [
    "api.agentic.check_assistant_config_api_v1_agentic_check_config_get",
    "permissive",
  ],
  ["api.agentic.assist_api_v1_agentic_assist_post", "permissive"],
  ["api.agentic.assist_stream_api_v1_agentic_assist_stream_post", "permissive"],
  ["api.files.upload_user_file_api_v2_files__post", "permissive"],
  ["api.files.list_files_api_v2_files__get", "permissive"],
  ["api.files.delete_all_files_api_v2_files__delete", "permissive"],
  ["api.files.upload_user_file_api_v2_files_post", "permissive"],
  ["api.files.list_files_api_v2_files_get", "permissive"],
  ["api.files.delete_all_files_api_v2_files_delete", "permissive"],
  ["api.files.download_files_batch_api_v2_files_batch__post", "permissive"],
  ["api.files.delete_files_batch_api_v2_files_batch__delete", "permissive"],
  ["api.files.download_file_api_v2_files__file_id__get", "permissive"],
  ["api.files.edit_file_name_api_v2_files__file_id__put", "permissive"],
  ["api.files.delete_file_api_v2_files__file_id__delete", "permissive"],
  ["api.mcp.get_servers_api_v2_mcp_servers_get", "permissive"],
  [
    "api.mcp.get_server_endpoint_api_v2_mcp_servers__server_name__get",
    "permissive",
  ],
  ["api.mcp.add_server_api_v2_mcp_servers__server_name__post", "permissive"],
  [
    "api.mcp.update_server_endpoint_api_v2_mcp_servers__server_name__patch",
    "permissive",
  ],
  [
    "api.mcp.delete_server_api_v2_mcp_servers__server_name__delete",
    "permissive",
  ],
  ["api.runs.enqueue_run_api_v2_runs_post", "permissive"],
  ["api.runs.list_runs_api_v2_runs_get", "permissive"],
  ["api.runs.get_run_api_v2_runs__run_id__get", "permissive"],
  ["api.runs.cancel_run_api_v2_runs__run_id__cancel_post", "permissive"],
  ["api.runs.get_run_logs_api_v2_runs__run_id__logs_get", "permissive"],
  ["api.workflow.execute_workflow_api_v2_workflows_post", "permissive"],
  ["api.workflow.get_workflow_status_api_v2_workflows_get", "permissive"],
  ["api.workflow.stop_workflow_api_v2_workflows_stop_post", "permissive"],
  ["api.mcp.handle_sse_api_mcp_sse_get", "permissive"],
  ["api.mcp.handle_messages_api_mcp__post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable_post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable_post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable_post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable__post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable__post", "permissive"],
  ["api.mcp.handle_streamable_http_api_mcp_streamable__post", "permissive"],
  ["api.health_check.health_health_get", "permissive"],
  ["api.health_check.health_check_health_check_get", "permissive"],
  ["api.log.stream_logs_logs_stream_get", "permissive"],
  ["api.log.logs_logs_get", "permissive"],
];

SCHEMA_MODES.forEach(([id, mode]) => registerSchema(id, mode));
