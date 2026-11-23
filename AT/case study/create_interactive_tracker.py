"""
Generate a fully interactive Excel tracker with:
1. Dropdowns for Issue Type, Priority, Story Points, and Status.
2. Dynamic cell color formatting triggered on every dropdown value selection.
3. Summary Dashboard that auto-mirrors the colors, values, and rollup metrics.
"""
import xlsxwriter

def build_interactive_tracker():
    wb = xlsxwriter.Workbook("Team_Work_Tracker_Interactive.xlsx")

    # --- FORMAT DEFINITIONS ---
    hdr_main = wb.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'bg_color': '#1F4E79', 'font_color': '#FFFFFF',
        'align': 'left', 'valign': 'vcenter', 'border': 1
    })
    hdr_sub = wb.add_format({
        'italic': True, 'font_size': 10, 'font_name': 'Segoe UI',
        'bg_color': '#D9E1F2', 'font_color': '#1F4E79',
        'align': 'left', 'valign': 'vcenter', 'border': 1
    })
    hdr_col = wb.add_format({
        'bold': True, 'font_size': 11, 'font_name': 'Segoe UI',
        'bg_color': '#203764', 'font_color': '#FFFFFF',
        'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        'border': 1
    })
    hdr_section = wb.add_format({
        'bold': True, 'font_size': 11, 'font_name': 'Segoe UI',
        'bg_color': '#8EA9DB', 'font_color': '#002060',
        'align': 'left', 'valign': 'vcenter', 'border': 1
    })
    hdr_alert_section = wb.add_format({
        'bold': True, 'font_size': 11, 'font_name': 'Segoe UI',
        'bg_color': '#FFC7CE', 'font_color': '#9C0006',
        'align': 'left', 'valign': 'vcenter', 'border': 1
    })

    # Standard Data cell formats
    cell_left = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'left',
        'valign': 'vcenter', 'text_wrap': True, 'border': 1
    })
    cell_center = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center',
        'valign': 'vcenter', 'border': 1
    })
    cell_bold_center = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'center', 'valign': 'vcenter', 'border': 1
    })
    cell_jira = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'font_color': '#0052CC'
    })
    cell_pct = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'num_format': '0.0%'
    })
    cell_num_center = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center',
        'valign': 'vcenter', 'border': 1, 'bold': True
    })

    # Totals Row format
    total_fmt_label = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'right', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#D9E1F2', 'font_color': '#002060'
    })
    total_fmt_num = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#D9E1F2', 'font_color': '#002060'
    })
    total_fmt_pct = wb.add_format({
        'bold': True, 'font_name': 'Segoe UI', 'font_size': 10,
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#D9E1F2', 'font_color': '#002060',
        'num_format': '0.0%'
    })

    # Metric Card formats
    metric_num = wb.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#F2F2F2', 'font_color': '#1F4E79'
    })
    metric_blocked_num = wb.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#FFC7CE', 'font_color': '#9C0006'
    })
    metric_lbl = wb.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#D9E1F2', 'font_color': '#203764'
    })
    metric_blocked_lbl = wb.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#F8CBAD', 'font_color': '#9C0006'
    })

    # --- CONDITIONAL FORMATTING COLOR STYLES ---
    # 1. Status Colors
    cf_stat_blocked = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'bold': True})
    cf_stat_waiting = wb.add_format({'bg_color': '#FCE4D6', 'font_color': '#C65911', 'bold': True})
    cf_stat_in_prog = wb.add_format({'bg_color': '#FFF2CC', 'font_color': '#B25900', 'bold': True})
    cf_stat_in_review = wb.add_format({'bg_color': '#DDEBF7', 'font_color': '#1F4E79', 'bold': True})
    cf_stat_completed = wb.add_format({'bg_color': '#E2EFDA', 'font_color': '#375623', 'bold': True})
    cf_stat_todo = wb.add_format({'bg_color': '#F2F2F2', 'font_color': '#595959', 'bold': True})

    # 2. Priority Colors
    cf_prio_highest = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'bold': True})
    cf_prio_high = wb.add_format({'bg_color': '#F8CBAD', 'font_color': '#C00000', 'bold': True})
    cf_prio_med = wb.add_format({'bg_color': '#FFF2CC', 'font_color': '#806000', 'bold': True})
    cf_prio_low = wb.add_format({'bg_color': '#E2EFDA', 'font_color': '#375623', 'bold': True})

    # 3. Issue Type Colors
    cf_type_bug = wb.add_format({'bg_color': '#FFD8D8', 'font_color': '#A80000', 'bold': True})
    cf_type_story = wb.add_format({'bg_color': '#E2EFDA', 'font_color': '#276A3C', 'bold': True})
    cf_type_spike = wb.add_format({'bg_color': '#E8DDF7', 'font_color': '#5B2C6F', 'bold': True})
    cf_type_task = wb.add_format({'bg_color': '#D9E1F2', 'font_color': '#1F4E79', 'bold': True})
    cf_type_testing = wb.add_format({'bg_color': '#FFF2CC', 'font_color': '#7F6000', 'bold': True})

    # Team Members metadata
    members = [
        {
            "name": "Oindrilla",
            "role": "QA & Test Lead",
            "tab": "Oindrilla",
            "color": "#4BACC6",
            "raw_update": "Planning to complete testing in test env and merge the changes in QA by tomorrow.",
            "tickets": [
                {
                    "key": "ARIA-101", "type": "Testing", "summary": "Complete CL Workflow & Onboarding E2E testing in Test Env",
                    "desc": "Execute automated and manual test suites in test environment. Verify regression, sign off, and merge changes into QA branch by tomorrow.",
                    "prio": "High", "status": "In Progress", "story_pts": 5, "due": "2025-03-02",
                    "pr_link": "PR #142 (QA Merge)", "blocker": "None (Testing on track)"
                },
                {
                    "key": "ARIA-98", "type": "Bug", "summary": "Validate bugfix for CL Escalation trigger",
                    "desc": "Re-test escalation handler once Kalpesh deploys bugfix to test environment.",
                    "prio": "High", "status": "Waiting", "story_pts": 2, "due": "2025-03-03",
                    "pr_link": "PR #145", "blocker": "⏳ Waiting for Kalpesh deployment"
                },
                {
                    "key": "ARIA-95", "type": "Task", "summary": "KT Session with Rohit Kumar on Onboarding Flow",
                    "desc": "Completed knowledge transfer on test scenarios, payload fixtures and mock services.",
                    "prio": "Medium", "status": "Completed", "story_pts": 1, "due": "2025-02-28",
                    "pr_link": "Confluence / KT Notes", "blocker": "None"
                }
            ]
        },
        {
            "name": "Karnam Kalpesh",
            "role": "Backend / Workflow Dev",
            "tab": "Karnam Kalpesh",
            "color": "#8064A2",
            "raw_update": "Fixing the bug that Oindrilla raised for CL workflow getting escalated.",
            "tickets": [
                {
                    "key": "ARIA-102", "type": "Bug", "summary": "Fix CL workflow incorrect escalation condition",
                    "desc": "Investigate state machine transitions and escalation guardrails in CL workflow. Fix edge-case causing unwarranted escalation.",
                    "prio": "Highest", "status": "In Progress", "story_pts": 5, "due": "2025-03-02",
                    "pr_link": "PR #145", "blocker": "None"
                },
                {
                    "key": "ARIA-89", "type": "Story", "summary": "Escalation Policy & SLA Management in Agent Engine",
                    "desc": "Define configurable SLA thresholds before auto-escalating cases to human relationship managers.",
                    "prio": "High", "status": "Blocked", "story_pts": 8, "due": "2025-03-06",
                    "pr_link": "PR #138", "blocker": "🛑 Blocked by ARIA-102 bug resolution"
                }
            ]
        },
        {
            "name": "Rohit Kumar",
            "role": "Workflow Engineer",
            "tab": "Rohit Kumar",
            "color": "#9BBB59",
            "raw_update": "Given KT to Oindrilla on how to test the onboarding workflow and currently he is working on CL onboarding",
            "tickets": [
                {
                    "key": "ARIA-103", "type": "Story", "summary": "Implement CL (Credit Line) Onboarding Workflow",
                    "desc": "Build automated client data extraction, credit verification steps, and DynamoDB workflow state machine.",
                    "prio": "High", "status": "In Progress", "story_pts": 8, "due": "2025-03-05",
                    "pr_link": "PR #140", "blocker": "None"
                },
                {
                    "key": "ARIA-100", "type": "Task", "summary": "Conduct Testing KT for Onboarding Workflow to QA",
                    "desc": "Guided Oindrilla through onboarding edge cases, test environment setup, and verification criteria.",
                    "prio": "Medium", "status": "Completed", "story_pts": 2, "due": "2025-02-28",
                    "pr_link": "Wiki / Architecture Docs", "blocker": "None"
                }
            ]
        },
        {
            "name": "Rohit Reddy",
            "role": "AI Architect / Senior ML",
            "tab": "Rohit Reddy",
            "color": "#F79646",
            "raw_update": "Working on evaluating GPT 6 Sol for our codebase.",
            "tickets": [
                {
                    "key": "ARIA-104", "type": "Spike", "summary": "Evaluate Next-Gen LLM / GPT-6 Architecture for Agent Core",
                    "desc": "Benchmark latency, context window utilization, function calling accuracy, and cost model against existing Bedrock Claude models.",
                    "prio": "Medium", "status": "Waiting", "story_pts": 5, "due": "2025-03-07",
                    "pr_link": "Evaluation RFC / Notebook", "blocker": "⏳ Waiting for quota limit approval"
                },
                {
                    "key": "ARIA-92", "type": "Task", "summary": "Prompt & Guardrail Optimization for Model Migration",
                    "desc": "Test system prompts across updated LLM versions to ensure zero regressions in customer banking policies.",
                    "prio": "Medium", "status": "In Review", "story_pts": 3, "due": "2025-03-08",
                    "pr_link": "PR #132", "blocker": "None"
                }
            ]
        },
        {
            "name": "Ravindra",
            "role": "Tech Lead / DevSecOps",
            "tab": "Ravindra",
            "color": "#1F4E79",
            "raw_update": "Updated the pre-requisite with status in prod readiness checklist and working on JWT + Cedar policy ticket and fixing SonarQube issue at cdk layer",
            "tickets": [
                {
                    "key": "ARIA-105", "type": "Task", "summary": "Update prerequisites & status in Production Readiness Checklist",
                    "desc": "Reviewed AWS accounts, IAM roles, alarms, KMS keys and updated the production readiness signoff document.",
                    "prio": "High", "status": "Completed", "story_pts": 3, "due": "2025-02-28",
                    "pr_link": "Prod Readiness Sheet v2.1", "blocker": "None"
                },
                {
                    "key": "ARIA-106", "type": "Story", "summary": "Implement Auth & Cedar Policy Fine-Grained Authorization with JWT",
                    "desc": "Integrate JWT token validation with AWS Verified Permissions / Cedar policies for role-based action authorization.",
                    "prio": "Highest", "status": "In Progress", "story_pts": 8, "due": "2025-03-04",
                    "pr_link": "PR #146", "blocker": "None"
                },
                {
                    "key": "ARIA-107", "type": "Bug", "summary": "Fix SonarQube Security & Quality Violations in CDK Layer",
                    "desc": "Remediate open findings in AWS CDK infrastructure code: enforce S3 bucket encryption, IAM least privilege, and VPC flow logs.",
                    "prio": "High", "status": "In Progress", "story_pts": 5, "due": "2025-03-03",
                    "pr_link": "PR #148", "blocker": "None"
                }
            ]
        }
    ]

    # Helper function to apply complete conditional formatting to any range
    def apply_color_formatting_rules(ws, type_col_range, prio_col_range, status_col_range, blocker_col_range=None, status_col_letter='G'):
        # 1. Status Colors
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Blocked"', 'format': cf_stat_blocked})
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Waiting"', 'format': cf_stat_waiting})
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"In Progress"', 'format': cf_stat_in_prog})
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"In Review"', 'format': cf_stat_in_review})
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Completed"', 'format': cf_stat_completed})
        ws.conditional_format(status_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"To Do"', 'format': cf_stat_todo})

        # 2. Priority Colors
        ws.conditional_format(prio_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Highest"', 'format': cf_prio_highest})
        ws.conditional_format(prio_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"High"', 'format': cf_prio_high})
        ws.conditional_format(prio_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Medium"', 'format': cf_prio_med})
        ws.conditional_format(prio_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Low"', 'format': cf_prio_low})

        # 3. Issue Type Colors
        ws.conditional_format(type_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Bug"', 'format': cf_type_bug})
        ws.conditional_format(type_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Story"', 'format': cf_type_story})
        ws.conditional_format(type_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Spike"', 'format': cf_type_spike})
        ws.conditional_format(type_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Task"', 'format': cf_type_task})
        ws.conditional_format(type_col_range, {'type': 'cell', 'criteria': 'equal to', 'value': '"Testing"', 'format': cf_type_testing})

        # 4. Optional Cross-Column Blocker Highlighting
        if blocker_col_range:
            ws.conditional_format(blocker_col_range, {'type': 'formula', 'criteria': f'=${status_col_letter}8="Blocked"', 'format': cf_stat_blocked})
            ws.conditional_format(blocker_col_range, {'type': 'formula', 'criteria': f'=${status_col_letter}8="Waiting"', 'format': cf_stat_waiting})

    # ==========================================
    # 1. SUMMARY DASHBOARD SHEET
    # ==========================================
    ws_dash = wb.add_worksheet("Summary Dashboard")
    ws_dash.set_tab_color('#C00000')

    ws_dash.set_column('A:A', 3)
    ws_dash.set_column('B:B', 16)  # Team Member
    ws_dash.set_column('C:C', 18)  # Role
    ws_dash.set_column('D:D', 34)  # Live Standup / Update
    ws_dash.set_column('E:E', 12)  # Total Tickets
    ws_dash.set_column('F:F', 12)  # Story Points
    ws_dash.set_column('G:G', 12)  # In Progress
    ws_dash.set_column('H:H', 12)  # Blocked / Waiting
    ws_dash.set_column('I:I', 12)  # In Review / QA
    ws_dash.set_column('J:J', 12)  # Completed
    ws_dash.set_column('K:K', 14)  # % Completion

    # Title Header
    ws_dash.merge_range('B2:K2', '🚀 DYNAMIC SPRINT TRACKER & BLOCKER ALERT DASHBOARD', hdr_main)
    ws_dash.merge_range('B3:K3', 'Live cross-sheet tracking with Interactive Dropdowns and Auto-Color highlights across all tabs', hdr_sub)
    ws_dash.set_row(1, 28)
    ws_dash.set_row(2, 20)

    # Dynamic KPI Cards using Excel Formulas
    ws_dash.write('B5', 'TEAM MEMBERS', metric_lbl)
    ws_dash.write_formula('B6', '=COUNTA(B10:B14)', metric_num)

    ws_dash.write('C5', 'TOTAL JIRA ITEMS', metric_lbl)
    ws_dash.write_formula('C6', '=SUM(E10:E14)', metric_num)

    ws_dash.write('D5', 'TOTAL STORY POINTS', metric_lbl)
    ws_dash.write_formula('D6', '=SUM(F10:F14)', metric_num)

    ws_dash.write('E5', 'IN PROGRESS', metric_lbl)
    ws_dash.write_formula('E6', '=SUM(G10:G14)', metric_num)

    ws_dash.write('F5', '🛑 BLOCKED ITEMS', metric_blocked_lbl)
    ws_dash.write_formula('F6', '=SUM(H10:H14)', metric_blocked_num)

    ws_dash.write('G5', 'IN REVIEW / QA', metric_lbl)
    ws_dash.write_formula('G6', '=SUM(I10:I14)', metric_num)

    ws_dash.write('H5', 'COMPLETED', metric_lbl)
    ws_dash.write_formula('H6', '=SUM(J10:J14)', metric_num)

    ws_dash.merge_range('I5:K5', 'SPRINT HEALTH ALERT', metric_lbl)
    ws_dash.merge_range('I6:K6', '=IF(F6>0, "🔴 ATTENTION: " & F6 & " Blocker(s) Need Action!", "🟢 ON TRACK - No Blockers")', metric_blocked_num)

    ws_dash.set_row(4, 18)
    ws_dash.set_row(5, 28)

    # Dynamic Blocker Alert Box (Row 8)
    ws_dash.merge_range('B8:K8', '⚠️ INTERACTIVE DROPDOWN SYSTEM: Change any Status, Priority, or Issue Type in member tabs — colors update automatically here!', hdr_alert_section)
    ws_dash.set_row(7, 22)

    # Table 1: Team Member Rollup Summary (Auto-Populated via Formulas)
    headers_summary_table = [
        'Team Member', 'Role / Focus', 'Live Standup Update (Linked to Tab)',
        'Total Tickets', 'Total Points', 'In Progress', '🛑 Blocked / Waiting', 'In Review', 'Completed', '% Completion'
    ]
    for col_idx, h_text in enumerate(headers_summary_table, start=1):
        ws_dash.write(8, col_idx, h_text, hdr_col)
    ws_dash.set_row(8, 26)

    # Populate Team Summary Rows with Cross-Sheet Formulas
    for i, mem in enumerate(members):
        row = 9 + i
        tab = mem["tab"]
        ws_dash.write(row, 1, mem["name"], cell_bold_center)
        ws_dash.write(row, 2, mem["role"], cell_center)
        ws_dash.write_formula(row, 3, f"='{tab}'!A5", cell_left)
        ws_dash.write_formula(row, 4, f"=COUNTIF('{tab}'!A8:A25, \"ARIA-*\")", cell_num_center)
        ws_dash.write_formula(row, 5, f"=SUM('{tab}'!F8:F25)", cell_num_center)
        ws_dash.write_formula(row, 6, f"=COUNTIF('{tab}'!G8:G25, \"In Progress\")", cell_num_center)
        ws_dash.write_formula(row, 7, f"=COUNTIF('{tab}'!G8:G25, \"Blocked\") + COUNTIF('{tab}'!G8:G25, \"Waiting\")", cell_num_center)
        ws_dash.write_formula(row, 8, f"=COUNTIF('{tab}'!G8:G25, \"In Review\")", cell_num_center)
        ws_dash.write_formula(row, 9, f"=COUNTIF('{tab}'!G8:G25, \"Completed\")", cell_num_center)
        ws_dash.write_formula(row, 10, f"=IFERROR(J{row+1}/E{row+1}, 0)", cell_pct)
        ws_dash.set_row(row, 28)

    # Conditional Formatting on Blocked Column in Summary Table (H10:H14)
    ws_dash.conditional_format('H10:H14', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': cf_stat_blocked})

    # Summary Totals Row
    total_row = 9 + len(members)
    ws_dash.merge_range(total_row, 1, total_row, 3, 'TOTAL SPRINT AGGREGATE', total_fmt_label)
    ws_dash.write_formula(total_row, 4, f"=SUM(E10:E{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 5, f"=SUM(F10:F{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 6, f"=SUM(G10:G{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 7, f"=SUM(H10:H{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 8, f"=SUM(I10:I{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 9, f"=SUM(J10:J{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 10, f"=IFERROR(J{total_row+1}/E{total_row+1}, 0)", total_fmt_pct)
    ws_dash.set_row(total_row, 24)

    # Table 2: Detailed JIRA Work Item Feed (Cell-Linked directly to member tabs)
    ws_dash.merge_range(total_row + 2, 1, total_row + 2, 10, '📋 Live JIRA Work Items Matrix (Direct Cell References with Auto-Color Sync)', hdr_section)
    ws_dash.set_row(total_row + 2, 22)

    headers_feed = ['Assignee', 'JIRA Key', 'Issue Type', 'Summary / Work Description', 'Priority', 'Story Pts', 'Status', 'Due Date', 'Blocker Reason / Dependency', 'Action Required']
    feed_hdr_row = total_row + 3
    for col_idx, h_text in enumerate(headers_feed, start=1):
        ws_dash.write(feed_hdr_row, col_idx, h_text, hdr_col)
    ws_dash.set_row(feed_hdr_row, 26)

    # Populate Live Feed rows with dynamic cell references
    curr_feed_row = feed_hdr_row + 1
    start_feed_row = curr_feed_row
    for mem in members:
        tab = mem["tab"]
        for t_idx, ticket in enumerate(mem["tickets"]):
            source_row = 8 + t_idx  # Row 8 is first ticket on member tab (A8:J8)
            ws_dash.write(curr_feed_row, 1, mem["name"], cell_bold_center)
            ws_dash.write_formula(curr_feed_row, 2, f"='{tab}'!A{source_row}", cell_jira)
            ws_dash.write_formula(curr_feed_row, 3, f"='{tab}'!B{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 4, f"='{tab}'!C{source_row}", cell_left)
            ws_dash.write_formula(curr_feed_row, 5, f"='{tab}'!E{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 6, f"='{tab}'!F{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 7, f"='{tab}'!G{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 8, f"='{tab}'!H{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 9, f"='{tab}'!J{source_row}", cell_left)
            
            # Action Required formula
            ws_dash.write_formula(curr_feed_row, 10, f"=IF(H{curr_feed_row+1}=\"Blocked\", \"🚨 ESCALATE / UNBLOCK\", IF(H{curr_feed_row+1}=\"Waiting\", \"⏳ FOLLOW UP\", \"-\"))", cell_center)
            
            ws_dash.set_row(curr_feed_row, 28)
            curr_feed_row += 1

    end_feed_row = curr_feed_row - 1

    # Apply Auto-Color Formatting Rules on Summary Dashboard Feed
    feed_type_range = f'D{start_feed_row+1}:D{end_feed_row+1}'
    feed_prio_range = f'F{start_feed_row+1}:F{end_feed_row+1}'
    feed_stat_range = f'H{start_feed_row+1}:H{end_feed_row+1}'
    apply_color_formatting_rules(ws_dash, feed_type_range, feed_prio_range, feed_stat_range)

    # Conditional formatting for Dashboard Action column
    ws_dash.conditional_format(f'K{start_feed_row+1}:K{end_feed_row+1}', {'type': 'cell', 'criteria': 'equal to', 'value': '"🚨 ESCALATE / UNBLOCK"', 'format': cf_stat_blocked})
    ws_dash.conditional_format(f'K{start_feed_row+1}:K{end_feed_row+1}', {'type': 'cell', 'criteria': 'equal to', 'value': '"⏳ FOLLOW UP"', 'format': cf_stat_waiting})

    # ==========================================
    # 2. INDIVIDUAL MEMBER TABS
    # ==========================================
    headers_member = [
        'JIRA Key', 'Issue Type (Dropdown)', 'Summary / Work Item', 'Detailed Description / Acceptance Criteria',
        'Priority (Dropdown)', 'Story Pts (Dropdown)', 'Status (Dropdown)', 'Due Date', 'PR / Artifact Link', 'Blockers & Dependencies'
    ]

    for mem in members:
        ws = wb.add_worksheet(mem["name"])
        ws.set_tab_color(mem["color"])

        # Column widths
        ws.set_column('A:A', 13)  # JIRA Key
        ws.set_column('B:B', 15)  # Issue Type (Dropdown)
        ws.set_column('C:C', 32)  # Summary
        ws.set_column('D:D', 40)  # Description
        ws.set_column('E:E', 14)  # Priority (Dropdown)
        ws.set_column('F:F', 12)  # Story Pts (Dropdown)
        ws.set_column('G:G', 16)  # Status (Dropdown)
        ws.set_column('H:H', 13)  # Due Date
        ws.set_column('I:I', 22)  # PR Link
        ws.set_column('J:J', 34)  # Blockers & Dependencies

        # Member Header Banner
        ws.merge_range('A1:J1', f"👤 TEAM MEMBER WORK TRACKER: {mem['name'].upper()}", hdr_main)
        ws.merge_range('A2:J2', f"Role: {mem['role']} | Sprint: Active | All dropdown changes dynamically update cell colors and Dashboard", hdr_sub)
        ws.set_row(0, 26)
        ws.set_row(1, 18)

        # Daily Standup Update Callout Box
        ws.merge_range('A4:J4', '📌 LATEST STANDUP / DAILY UPDATE (Auto-synced to Summary Dashboard)', hdr_section)
        ws.merge_range('A5:J5', f'{mem["raw_update"]}', cell_left)
        ws.set_row(3, 20)
        ws.set_row(4, 28)

        # Table Header
        for col_idx, h_text in enumerate(headers_member):
            ws.write(6, col_idx, h_text, hdr_col)
        ws.set_row(6, 26)

        # Ticket Data Rows
        current_row = 7
        for t in mem["tickets"]:
            ws.write(current_row, 0, t["key"], cell_jira)
            ws.write(current_row, 1, t["type"], cell_center)
            ws.write(current_row, 2, t["summary"], cell_left)
            ws.write(current_row, 3, t["desc"], cell_left)
            ws.write(current_row, 4, t["prio"], cell_center)
            ws.write(current_row, 5, t["story_pts"], cell_center)
            ws.write(current_row, 6, t["status"], cell_center)
            ws.write(current_row, 7, t["due"], cell_center)
            ws.write(current_row, 8, t["pr_link"], cell_left)
            ws.write(current_row, 9, t["blocker"], cell_left)
            ws.set_row(current_row, 36)
            current_row += 1

        # Empty placeholder rows for upcoming tasks
        for i in range(3):
            ws.write(current_row, 0, f"ARIA-1{mem['tickets'][0]['key'][-2:]}{i+1}", cell_center)
            ws.write(current_row, 1, "Task", cell_center)
            ws.write(current_row, 2, "[Upcoming Task / Backlog Item]", cell_left)
            ws.write(current_row, 3, "Add details and acceptance criteria here...", cell_left)
            ws.write(current_row, 4, "Medium", cell_center)
            ws.write(current_row, 5, 3, cell_center)
            ws.write(current_row, 6, "To Do", cell_center)
            ws.write(current_row, 7, "2025-03-10", cell_center)
            ws.write(current_row, 8, "-", cell_center)
            ws.write(current_row, 9, "None", cell_left)
            ws.set_row(current_row, 24)
            current_row += 1

        # -------------------------------------------------------------
        # 1. DATA VALIDATION DROPDOWNS (Rows 8 to 25)
        # -------------------------------------------------------------
        # Dropdown 1: Issue Type (Column B)
        ws.data_validation('B8:B25', {
            'validate': 'list',
            'source': ['Story', 'Bug', 'Task', 'Spike', 'Testing'],
            'input_title': 'Issue Type',
            'input_message': 'Select: Story, Bug, Task, Spike, Testing',
            'error_title': 'Invalid Type',
            'error_message': 'Please choose a valid Issue Type from the dropdown.'
        })

        # Dropdown 2: Priority (Column E)
        ws.data_validation('E8:E25', {
            'validate': 'list',
            'source': ['Highest', 'High', 'Medium', 'Low'],
            'input_title': 'Priority',
            'input_message': 'Select: Highest, High, Medium, Low',
            'error_title': 'Invalid Priority',
            'error_message': 'Please choose a valid Priority from the dropdown.'
        })

        # Dropdown 3: Story Points (Column F)
        ws.data_validation('F8:F25', {
            'validate': 'list',
            'source': [1, 2, 3, 5, 8, 13, 21],
            'input_title': 'Story Points',
            'input_message': 'Select estimation points (Fibonacci)',
            'error_title': 'Invalid Points',
            'error_message': 'Please choose standard Fibonacci points.'
        })

        # Dropdown 4: Status (Column G)
        ws.data_validation('G8:G25', {
            'validate': 'list',
            'source': ['To Do', 'In Progress', 'In Review', 'Waiting', 'Blocked', 'Completed'],
            'input_title': 'Status',
            'input_message': 'Select: To Do, In Progress, In Review, Waiting, Blocked, Completed',
            'error_title': 'Invalid Status',
            'error_message': 'Please pick a status from the dropdown list.'
        })

        # -------------------------------------------------------------
        # 2. DYNAMIC CONDITIONAL FORMATTING (Auto-Color on Change)
        # -------------------------------------------------------------
        apply_color_formatting_rules(
            ws=ws,
            type_col_range='B8:B25',
            prio_col_range='E8:E25',
            status_col_range='G8:G25',
            blocker_col_range='J8:J25',
            status_col_letter='G'
        )

    wb.close()
    print("Interactive Tracker with Dynamic Dropdowns and Color Rules created successfully!")

if __name__ == "__main__":
    build_interactive_tracker()
