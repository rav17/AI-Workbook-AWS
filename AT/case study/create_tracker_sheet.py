"""
Generate an Excel workbook with dynamic cross-sheet formulas in the Summary Dashboard.
"""
import xlsxwriter

def build_excel_tracker_with_formulas():
    wb = xlsxwriter.Workbook("Team_Work_Tracker_Dynamic.xlsx")

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

    # Data cell formats
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

    # Status & Priority formats
    status_in_progress = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#FFF2CC', 'font_color': '#B25900', 'bold': True
    })
    status_completed = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#E2EFDA', 'font_color': '#375623', 'bold': True
    })
    status_in_review = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#DDEBF7', 'font_color': '#1F4E79', 'bold': True
    })
    status_todo = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#F2F2F2', 'font_color': '#595959', 'bold': True
    })
    
    prio_crit = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#FCE4D6', 'font_color': '#C00000', 'bold': True
    })
    prio_high = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#F8CBAD', 'font_color': '#C00000', 'bold': True
    })
    prio_med = wb.add_format({
        'font_name': 'Segoe UI', 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#FFF2CC', 'font_color': '#806000'
    })

    # Metric Card formats
    metric_num = wb.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#F2F2F2', 'font_color': '#1F4E79'
    })
    metric_pct = wb.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#F2F2F2', 'font_color': '#2E75B6',
        'num_format': '0.0%'
    })
    metric_lbl = wb.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#D9E1F2', 'font_color': '#203764'
    })

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
                    "prio": "High", "prio_fmt": prio_high, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 5, "due": "2025-03-02", "pr_link": "PR #142 (QA Merge)", "blocker": "None (Testing on track)"
                },
                {
                    "key": "ARIA-98", "type": "Bug", "summary": "Validate bugfix for CL Escalation trigger",
                    "desc": "Re-test escalation handler once Kalpesh deploys bugfix to test environment.",
                    "prio": "High", "prio_fmt": prio_high, "status": "In Review", "stat_fmt": status_in_review,
                    "story_pts": 2, "due": "2025-03-03", "pr_link": "PR #145", "blocker": "Waiting for Kalpesh deployment"
                },
                {
                    "key": "ARIA-95", "type": "Task", "summary": "KT Session with Rohit Kumar on Onboarding Flow",
                    "desc": "Completed knowledge transfer on test scenarios, payload fixtures and mock services.",
                    "prio": "Medium", "prio_fmt": prio_med, "status": "Completed", "stat_fmt": status_completed,
                    "story_pts": 1, "due": "2025-02-28", "pr_link": "Confluence / KT Notes", "blocker": "None"
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
                    "prio": "Highest", "prio_fmt": prio_crit, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 5, "due": "2025-03-02", "pr_link": "PR #145", "blocker": "None"
                },
                {
                    "key": "ARIA-89", "type": "Story", "summary": "Escalation Policy & SLA Management in Agent Engine",
                    "desc": "Define configurable SLA thresholds before auto-escalating cases to human relationship managers.",
                    "prio": "High", "prio_fmt": prio_high, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 8, "due": "2025-03-06", "pr_link": "PR #138", "blocker": "Pending ARIA-102 bug resolution"
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
                    "prio": "High", "prio_fmt": prio_high, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 8, "due": "2025-03-05", "pr_link": "PR #140", "blocker": "None"
                },
                {
                    "key": "ARIA-100", "type": "Task", "summary": "Conduct Testing KT for Onboarding Workflow to QA",
                    "desc": "Guided Oindrilla through onboarding edge cases, test environment setup, and verification criteria.",
                    "prio": "Medium", "prio_fmt": prio_med, "status": "Completed", "stat_fmt": status_completed,
                    "story_pts": 2, "due": "2025-02-28", "pr_link": "Wiki / Architecture Docs", "blocker": "None"
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
                    "prio": "Medium", "prio_fmt": prio_med, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 5, "due": "2025-03-07", "pr_link": "Evaluation RFC / Notebook", "blocker": "Awaiting quota limit confirmation"
                },
                {
                    "key": "ARIA-92", "type": "Task", "summary": "Prompt & Guardrail Optimization for Model Migration",
                    "desc": "Test system prompts across updated LLM versions to ensure zero regressions in customer banking policies.",
                    "prio": "Medium", "prio_fmt": prio_med, "status": "In Review", "stat_fmt": status_in_review,
                    "story_pts": 3, "due": "2025-03-08", "pr_link": "PR #132", "blocker": "Dependent on ARIA-104 benchmarking"
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
                    "prio": "High", "prio_fmt": prio_high, "status": "Completed", "stat_fmt": status_completed,
                    "story_pts": 3, "due": "2025-02-28", "pr_link": "Prod Readiness Sheet v2.1", "blocker": "None"
                },
                {
                    "key": "ARIA-106", "type": "Story", "summary": "Implement Auth & Cedar Policy Fine-Grained Authorization with JWT",
                    "desc": "Integrate JWT token validation with AWS Verified Permissions / Cedar policies for role-based action authorization.",
                    "prio": "Highest", "prio_fmt": prio_crit, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 8, "due": "2025-03-04", "pr_link": "PR #146", "blocker": "None"
                },
                {
                    "key": "ARIA-107", "type": "Bug", "summary": "Fix SonarQube Security & Quality Violations in CDK Layer",
                    "desc": "Remediate open findings in AWS CDK infrastructure code: enforce S3 bucket encryption, IAM least privilege, and VPC flow logs.",
                    "prio": "High", "prio_fmt": prio_high, "status": "In Progress", "stat_fmt": status_in_progress,
                    "story_pts": 5, "due": "2025-03-03", "pr_link": "PR #148", "blocker": "None"
                }
            ]
        }
    ]

    # ==========================================
    # 1. SUMMARY DASHBOARD SHEET (WITH FORMULAS)
    # ==========================================
    ws_dash = wb.add_worksheet("Summary Dashboard")
    ws_dash.set_tab_color('#1F4E79')

    ws_dash.set_column('A:A', 3)
    ws_dash.set_column('B:B', 16)  # Team Member
    ws_dash.set_column('C:C', 18)  # Role
    ws_dash.set_column('D:D', 34)  # Live Standup / Update (Formula Linked)
    ws_dash.set_column('E:E', 12)  # Total Tickets (Formula)
    ws_dash.set_column('F:F', 12)  # Story Points (Formula)
    ws_dash.set_column('G:G', 12)  # In Progress (Formula)
    ws_dash.set_column('H:H', 12)  # In Review / QA (Formula)
    ws_dash.set_column('I:I', 12)  # Completed (Formula)
    ws_dash.set_column('J:J', 14)  # % Completion (Formula)

    # Title Header
    ws_dash.merge_range('B2:J2', '🚀 DYNAMIC SPRINT WORK TRACKER & EXECUTIVE DASHBOARD', hdr_main)
    ws_dash.merge_range('B3:J3', 'Auto-populated in real-time via Excel formulas linked to individual team member tabs', hdr_sub)
    ws_dash.set_row(1, 28)
    ws_dash.set_row(2, 20)

    # Dynamic KPI Cards using Excel Formulas
    ws_dash.write('B5', 'TEAM MEMBERS', metric_lbl)
    ws_dash.write_formula('B6', '=COUNTA(B9:B13)', metric_num)

    ws_dash.write('C5', 'TOTAL ACTIVE JIRA', metric_lbl)
    ws_dash.write_formula('C6', '=SUM(E9:E13)', metric_num)

    ws_dash.merge_range('D5:E5', 'TOTAL STORY POINTS', metric_lbl)
    ws_dash.merge_range('D6:E6', '=SUM(F9:F13)', metric_num)

    ws_dash.write('F5', 'IN PROGRESS', metric_lbl)
    ws_dash.write_formula('F6', '=SUM(G9:G13)', metric_num)

    ws_dash.write('G5', 'IN REVIEW / QA', metric_lbl)
    ws_dash.write_formula('G6', '=SUM(H9:H13)', metric_num)

    ws_dash.write('H5', 'COMPLETED', metric_lbl)
    ws_dash.write_formula('H6', '=SUM(I9:I13)', metric_num)

    ws_dash.merge_range('I5:J5', 'SPRINT COMPLETION %', metric_lbl)
    ws_dash.merge_range('I6:J6', '=IFERROR(SUM(I9:I13)/SUM(E9:E13), 0)', metric_pct)

    ws_dash.set_row(4, 18)
    ws_dash.set_row(5, 28)

    # Table 1: Team Member Rollup Summary (Auto-Populated via Formulas)
    ws_dash.merge_range('B8:J8', '📊 Team Member Sprint Rollup (Formulas Link to Individual Tabs)', hdr_section)
    ws_dash.set_row(7, 22)

    headers_summary_table = [
        'Team Member', 'Role / Focus', 'Live Standup Update (Linked to Tab)',
        'Total Tickets', 'Total Points', 'In Progress', 'In Review', 'Completed', '% Completion'
    ]
    for col_idx, h_text in enumerate(headers_summary_table, start=1):
        ws_dash.write(8, col_idx, h_text, hdr_col)
    ws_dash.set_row(8, 26)

    # Populate Team Summary Rows with Cross-Sheet Formulas
    # Team tabs data range: A8:J20
    # Status column is G, Story Points is F, JIRA Key is A, Latest Update is A5
    for i, mem in enumerate(members):
        row = 9 + i
        tab = mem["tab"]
        ws_dash.write(row, 1, mem["name"], cell_bold_center)
        ws_dash.write(row, 2, mem["role"], cell_center)
        
        # Link directly to the standup update cell on member's sheet
        ws_dash.write_formula(row, 3, f"='{tab}'!A5", cell_left)
        
        # Formula: Count valid ARIA tickets on their sheet
        ws_dash.write_formula(row, 4, f"=COUNTIF('{tab}'!A8:A25, \"ARIA-*\")", cell_num_center)
        
        # Formula: Sum story points on their sheet
        ws_dash.write_formula(row, 5, f"=SUM('{tab}'!F8:F25)", cell_num_center)
        
        # Formula: Count In Progress
        ws_dash.write_formula(row, 6, f"=COUNTIF('{tab}'!G8:G25, \"In Progress\")", cell_num_center)
        
        # Formula: Count In Review / Testing
        ws_dash.write_formula(row, 7, f"=COUNTIF('{tab}'!G8:G25, \"In Review\")", cell_num_center)
        
        # Formula: Count Completed
        ws_dash.write_formula(row, 8, f"=COUNTIF('{tab}'!G8:G25, \"Completed\")", cell_num_center)
        
        # Formula: % Completion rate for this member
        ws_dash.write_formula(row, 9, f"=IFERROR(I{row+1}/E{row+1}, 0)", cell_pct)
        
        ws_dash.set_row(row, 28)

    # Summary Totals Row
    total_row = 9 + len(members)
    ws_dash.merge_range(total_row, 1, total_row, 3, 'TOTAL SPRINT AGGREGATE', total_fmt_label)
    ws_dash.write_formula(total_row, 4, f"=SUM(E9:E{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 5, f"=SUM(F9:F{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 6, f"=SUM(G9:G{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 7, f"=SUM(H9:H{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 8, f"=SUM(I9:I{total_row})", total_fmt_num)
    ws_dash.write_formula(total_row, 9, f"=IFERROR(I{total_row+1}/E{total_row+1}, 0)", total_fmt_pct)
    ws_dash.set_row(total_row, 24)

    # Table 2: Detailed JIRA Work Item Feed (Cell-Linked directly to member tabs)
    ws_dash.merge_range(total_row + 2, 1, total_row + 2, 9, '📋 Live JIRA Work Items Matrix (Direct Cell References to Each Member Tab)', hdr_section)
    ws_dash.set_row(total_row + 2, 22)

    headers_feed = ['Assignee', 'JIRA Key', 'Issue Type', 'Summary / Work Description', 'Priority', 'Story Pts', 'Status', 'Due Date', 'Blockers & Notes']
    feed_hdr_row = total_row + 3
    for col_idx, h_text in enumerate(headers_feed, start=1):
        ws_dash.write(feed_hdr_row, col_idx, h_text, hdr_col)
    ws_dash.set_row(feed_hdr_row, 26)

    # Populate Live Feed rows with dynamic cell references
    curr_feed_row = feed_hdr_row + 1
    for mem in members:
        tab = mem["tab"]
        for t_idx, ticket in enumerate(mem["tickets"]):
            source_row = 8 + t_idx  # Row 8 is first ticket on member tab (A8:J8)
            ws_dash.write(curr_feed_row, 1, mem["name"], cell_bold_center)
            ws_dash.write_formula(curr_feed_row, 2, f"='{tab}'!A{source_row}", cell_jira)
            ws_dash.write_formula(curr_feed_row, 3, f"='{tab}'!B{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 4, f"='{tab}'!C{source_row}", cell_left)
            ws_dash.write_formula(curr_feed_row, 5, f"='{tab}'!E{source_row}", ticket["prio_fmt"])
            ws_dash.write_formula(curr_feed_row, 6, f"='{tab}'!F{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 7, f"='{tab}'!G{source_row}", ticket["stat_fmt"])
            ws_dash.write_formula(curr_feed_row, 8, f"='{tab}'!H{source_row}", cell_center)
            ws_dash.write_formula(curr_feed_row, 9, f"='{tab}'!J{source_row}", cell_left)
            ws_dash.set_row(curr_feed_row, 28)
            curr_feed_row += 1

    # ==========================================
    # 2. INDIVIDUAL MEMBER TABS
    # ==========================================
    headers_member = [
        'JIRA Key', 'Issue Type', 'Summary / Work Item', 'Detailed Description / Acceptance Criteria',
        'Priority', 'Story Pts', 'Status', 'Due Date', 'PR / Artifact Link', 'Blockers & Dependencies'
    ]

    for mem in members:
        ws = wb.add_worksheet(mem["name"])
        ws.set_tab_color(mem["color"])

        # Column widths
        ws.set_column('A:A', 13)  # JIRA Key
        ws.set_column('B:B', 13)  # Issue Type
        ws.set_column('C:C', 32)  # Summary
        ws.set_column('D:D', 40)  # Description
        ws.set_column('E:E', 12)  # Priority
        ws.set_column('F:F', 10)  # Story Pts
        ws.set_column('G:G', 14)  # Status
        ws.set_column('H:H', 13)  # Due Date
        ws.set_column('I:I', 22)  # PR Link
        ws.set_column('J:J', 28)  # Blockers

        # Member Header Banner
        ws.merge_range('A1:J1', f"👤 TEAM MEMBER WORK TRACKER: {mem['name'].upper()}", hdr_main)
        ws.merge_range('A2:J2', f"Role: {mem['role']} | Sprint: Current Active Sprint | Changes here auto-reflect in Summary Dashboard", hdr_sub)
        ws.set_row(0, 26)
        ws.set_row(1, 18)

        # Daily Standup Update Callout Box (Referenced by Summary Dashboard cell D9:D13)
        ws.merge_range('A4:J4', '📌 LATEST STANDUP / DAILY UPDATE (Updates typed here automatically show in Summary Dashboard)', hdr_section)
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
            ws.write(current_row, 4, t["prio"], t["prio_fmt"])
            ws.write(current_row, 5, t["story_pts"], cell_center)
            ws.write(current_row, 6, t["status"], t["stat_fmt"])
            ws.write(current_row, 7, t["due"], cell_center)
            ws.write(current_row, 8, t["pr_link"], cell_left)
            ws.write(current_row, 9, t["blocker"], cell_left)
            ws.set_row(current_row, 36)
            current_row += 1

        # Empty placeholder rows for upcoming tasks
        for i in range(2):
            ws.write(current_row, 0, f"ARIA-1{mem['tickets'][0]['key'][-2:]}{i+1}", cell_center)
            ws.write(current_row, 1, "Task", cell_center)
            ws.write(current_row, 2, "[Upcoming Task / Backlog Item]", cell_left)
            ws.write(current_row, 3, "Add details and acceptance criteria here...", cell_left)
            ws.write(current_row, 4, "Medium", prio_med)
            ws.write(current_row, 5, 3, cell_center)
            ws.write(current_row, 6, "To Do", status_todo)
            ws.write(current_row, 7, "2025-03-10", cell_center)
            ws.write(current_row, 8, "-", cell_center)
            ws.write(current_row, 9, "None", cell_left)
            ws.set_row(current_row, 24)
            current_row += 1

    wb.close()
    print("Workbook with dynamic formulas created successfully!")

if __name__ == "__main__":
    build_excel_tracker_with_formulas()
