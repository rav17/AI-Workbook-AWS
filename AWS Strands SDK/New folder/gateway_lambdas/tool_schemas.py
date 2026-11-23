"""Tool schema definitions for FPL StormForce AgentCore Gateway — 5 Lambdas, 13 tools."""

LAMBDA_CONFIGS = {
    "fpl_stormforce_data": {
        "handler": "data_lambda.lambda_handler",
        "description": "StormForce data: teams, work orders, ETA updates, team page notes, SMS consent",
        "source_files": ["data_lambda.py", "shared.py"],
        "tools": [
            {"name": "query_stormforce_teams", "description": "Query teams from StormForce by event ID.",
             "inputSchema": {"type": "object", "properties": {"event_id": {"type": "string", "description": "Storm event ID"}}, "required": ["event_id"]}},
            {"name": "query_stormforce_work_order", "description": "Get work order details by ID.",
             "inputSchema": {"type": "object", "properties": {"work_order_id": {"type": "string"}}, "required": ["work_order_id"]}},
            {"name": "update_stormforce_eta", "description": "Update team ETA and travel details.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "departure_time": {"type": "string"}, "departure_location": {"type": "string"}, "expected_arrival_time": {"type": "string"}, "update_source": {"type": "string"}}, "required": ["team_id"]}},
            {"name": "create_team_page_note", "description": "Create a note on the Team Page in StormForce.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "note_type": {"type": "string"}, "note_content": {"type": "string"}}, "required": ["team_id", "note_content"]}},
            {"name": "update_sms_consent", "description": "Record SMS consent (OPTED_IN or OPTED_OUT).",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "phone_number": {"type": "string"}, "consent_status": {"type": "string", "description": "OPTED_IN or OPTED_OUT"}, "timestamp": {"type": "string"}, "work_order_id": {"type": "string"}}, "required": ["team_id", "consent_status"]}},
        ],
    },
    "fpl_stormforce_notification": {
        "handler": "notification_lambda.lambda_handler",
        "description": "SMS notifications to team leads",
        "source_files": ["notification_lambda.py", "shared.py"],
        "tools": [
            {"name": "send_sms", "description": "Send SMS to a team lead. One SMS per agent turn. US phone format +1XXXXXXXXXX.",
             "inputSchema": {"type": "object", "properties": {"phone_number": {"type": "string"}, "message": {"type": "string"}, "team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "include_opt_out": {"type": "boolean"}}, "required": ["phone_number", "message", "team_id", "work_order_id"]}},
        ],
    },
    "fpl_stormforce_escalation": {
        "handler": "escalation_lambda.lambda_handler",
        "description": "Escalation management",
        "source_files": ["escalation_lambda.py", "shared.py"],
        "tools": [
            {"name": "create_escalation", "description": "Create escalation record. Types: Non-Response, Not Team Lead, Team Not Traveling Together, Implausible ETA, Delay Exception, Missing Information.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "escalation_type": {"type": "string"}, "trigger_reason": {"type": "string"}, "interaction_context": {"type": "string"}, "message_history": {"type": "string"}}, "required": ["team_id", "escalation_type", "trigger_reason"]}},
        ],
    },
    "fpl_stormforce_eta": {
        "handler": "eta_lambda.lambda_handler",
        "description": "ETA calculation and plausibility validation",
        "source_files": ["eta_lambda.py", "shared.py"],
        "tools": [
            {"name": "calculate_eta_plausibility", "description": "Validate provided ETA against expected travel pace of 31.25 mph.",
             "inputSchema": {"type": "object", "properties": {"departure_location": {"type": "string"}, "processing_site_address": {"type": "string"}, "departure_time": {"type": "string"}, "provided_eta": {"type": "string"}}, "required": ["departure_location", "processing_site_address", "departure_time", "provided_eta"]}},
            {"name": "calculate_eta_from_location", "description": "Calculate ETA from last known location using 31.25 mph pace.",
             "inputSchema": {"type": "object", "properties": {"last_known_location": {"type": "string"}, "processing_site_address": {"type": "string"}}, "required": ["last_known_location", "processing_site_address"]}},
        ],
    },
    "fpl_stormforce_state": {
        "handler": "state_lambda.lambda_handler",
        "description": "Workflow state management, check-in timers, audit logging",
        "source_files": ["state_lambda.py", "shared.py"],
        "tools": [
            {"name": "get_workflow_state", "description": "Retrieve workflow state from DynamoDB.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}}, "required": ["team_id", "work_order_id"]}},
            {"name": "update_workflow_state", "description": "Update workflow state. Valid: SMS_CONSENT, TEAM_LEAD_CONFIRM, TEAM_DETAILS, TRAVEL_TIMING, ETA_VALIDATION, ETA_CLARIFICATION, MONITORING, ESCALATED, COMPLETED.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "new_state": {"type": "string"}}, "required": ["team_id", "work_order_id", "new_state"]}},
            {"name": "schedule_checkin_timer", "description": "Schedule check-in timer via EventBridge.",
             "inputSchema": {"type": "object", "properties": {"team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "delay_minutes": {"type": "integer"}, "check_in_sequence_number": {"type": "integer"}}, "required": ["team_id"]}},
            {"name": "log_audit_event", "description": "Log structured audit event to CloudWatch.",
             "inputSchema": {"type": "object", "properties": {"event_type": {"type": "string"}, "team_id": {"type": "string"}, "work_order_id": {"type": "string"}, "details": {"type": "string"}}, "required": ["event_type"]}},
        ],
    },
}
