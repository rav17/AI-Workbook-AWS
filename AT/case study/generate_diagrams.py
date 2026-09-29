import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np
import os

out_dir = r'c:\Users\RavindraYadav\Documents\AT\case study\diagrams'
os.makedirs(out_dir, exist_ok=True)

# ============================================================
# EXERCISE 1: System Context Diagram
# ============================================================
def draw_system_context():
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('Exercise 1: System Context Diagram\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Central system
    ecs = FancyBboxPatch((5.5, 4), 3, 2, boxstyle="round,pad=0.2",
                         facecolor='#4472C4', edgecolor='black', linewidth=2)
    ax.add_patch(ecs)
    ax.text(7, 5, 'ECS\n(Electronic\nCensus System)', ha='center', va='center',
            fontsize=11, fontweight='bold', color='white')

    # Human actors (stick figures represented as circles with labels)
    actors = [
        (1.5, 8.5, 'Respondent\n(Desktop/Mobile)'),
        (1.5, 5, 'Census\nCollector'),
        (1.5, 1.5, 'DoS\nAdministrator'),
        (12.5, 8.5, 'Help Desk\nOperator'),
        (12.5, 5, 'Developer/\nTester'),
        (12.5, 1.5, 'Support\nStaff'),
    ]

    for x, y, label in actors:
        circle = plt.Circle((x, y), 0.4, color='#70AD47', ec='black', linewidth=1.5)
        ax.add_patch(circle)
        ax.text(x, y-0.8, label, ha='center', va='top', fontsize=8, fontweight='bold')

    # System actors (rectangles)
    sys_actors = [
        (7, 8.5, 'DoS Electronic\nCensus Processing'),
        (7, 1.2, 'SMS Gateway\n(Mobile Network)'),
    ]

    for x, y, label in sys_actors:
        rect = FancyBboxPatch((x-1.2, y-0.4), 2.4, 0.8, boxstyle="round,pad=0.1",
                              facecolor='#FFC000', edgecolor='black', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, fontweight='bold')

    # Arrows from actors to ECS
    arrow_style = dict(arrowstyle='->', color='#333333', lw=1.5,
                       connectionstyle='arc3,rad=0.1')
    # Left actors
    ax.annotate('', xy=(5.5, 5.5), xytext=(2, 8.5), arrowprops=arrow_style)
    ax.annotate('', xy=(5.5, 5), xytext=(2, 5), arrowprops=arrow_style)
    ax.annotate('', xy=(5.5, 4.5), xytext=(2, 1.5), arrowprops=arrow_style)
    # Right actors
    ax.annotate('', xy=(8.5, 5.5), xytext=(12, 8.5), arrowprops=arrow_style)
    ax.annotate('', xy=(8.5, 5), xytext=(12, 5), arrowprops=arrow_style)
    ax.annotate('', xy=(8.5, 4.5), xytext=(12, 1.5), arrowprops=arrow_style)
    # System actors
    ax.annotate('', xy=(7, 6), xytext=(7, 8.1), arrowprops=arrow_style)
    ax.annotate('', xy=(7, 4), xytext=(7, 1.6), arrowprops=arrow_style)

    # Labels on arrows
    ax.text(3.5, 7.5, 'HTTPS', fontsize=7, fontstyle='italic', color='#555')
    ax.text(3.5, 5.2, 'SMS', fontsize=7, fontstyle='italic', color='#555')
    ax.text(7.2, 7.2, 'Data\nTransfer', fontsize=7, fontstyle='italic', color='#555')
    ax.text(7.2, 2.8, 'SMS\nNotification', fontsize=7, fontstyle='italic', color='#555')

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor='#70AD47', edgecolor='black', label='Human Actor'),
        mpatches.Patch(facecolor='#FFC000', edgecolor='black', label='System Actor'),
        mpatches.Patch(facecolor='#4472C4', edgecolor='black', label='System Under Design'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '01_System_Context_Diagram.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 01_System_Context_Diagram.png")

draw_system_context()

# ============================================================
# EXERCISE 1: Use Case Diagram
# ============================================================
def draw_use_case():
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('Exercise 1: High-Level Use Case Model\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # System boundary
    rect = FancyBboxPatch((3, 0.5), 8, 9, boxstyle="round,pad=0.3",
                          facecolor='#E8F0FE', edgecolor='#4472C4', linewidth=2, linestyle='--')
    ax.add_patch(rect)
    ax.text(7, 9.2, 'ECS System Boundary', ha='center', fontsize=10, fontstyle='italic', color='#4472C4')

    # Use cases (ellipses)
    use_cases = [
        (7, 8.5, 'UC_01: Logon'),
        (7, 7.5, 'UC_02: Navigate Form'),
        (7, 6.5, 'UC_03: Complete Sections'),
        (7, 5.5, 'UC_07: Save Progress'),
        (7, 4.5, 'UC_08: Resume Form'),
        (7, 3.5, 'UC_09: Submit Form'),
        (7, 2.5, 'UC_10: View Receipt'),
        (7, 1.5, 'UC_11: Logoff'),
        (10, 7, 'UC_20: Monitor Stats'),
        (10, 5.5, 'UC_21: Generate Reports'),
        (10, 4, 'UC_22: Transfer Data'),
        (10, 2.5, 'UC_23: Send SMS Notif.'),
    ]

    for x, y, label in use_cases:
        ellipse = mpatches.Ellipse((x, y), 2.8, 0.7, facecolor='white', 
                                    edgecolor='#4472C4', linewidth=1.5)
        ax.add_patch(ellipse)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5)

    # Actors
    ax.text(1.5, 6, 'Respondent', ha='center', fontsize=9, fontweight='bold', color='#70AD47')
    circle = plt.Circle((1.5, 6.5), 0.3, color='#70AD47', ec='black')
    ax.add_patch(circle)

    ax.text(12.5, 5, 'DoS Admin', ha='center', fontsize=9, fontweight='bold', color='#70AD47')
    circle2 = plt.Circle((12.5, 5.5), 0.3, color='#70AD47', ec='black')
    ax.add_patch(circle2)

    # Lines from actors to use cases
    for y_uc in [8.5, 7.5, 6.5, 5.5, 4.5, 3.5, 2.5, 1.5]:
        ax.plot([1.8, 5.6], [6.5, y_uc], 'k-', lw=0.5, alpha=0.4)
    for y_uc in [7, 5.5, 4, 2.5]:
        ax.plot([12.2, 11.4], [5.5, y_uc], 'k-', lw=0.5, alpha=0.4)

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '01_Use_Case_Diagram.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 01_Use_Case_Diagram.png")

draw_use_case()

# ============================================================
# EXERCISE 2: Architecture Overview Diagram
# ============================================================
def draw_aod():
    fig, ax = plt.subplots(1, 1, figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis('off')
    ax.set_title('Exercise 2: Architecture Overview Diagram\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Cloud boundary
    cloud = FancyBboxPatch((3.5, 1), 9, 7.5, boxstyle="round,pad=0.4",
                           facecolor='#F0F8FF', edgecolor='#2F5496', linewidth=2.5)
    ax.add_patch(cloud)
    ax.text(8, 8.2, 'Cloud Hosting Environment', ha='center', fontsize=11, 
            fontweight='bold', color='#2F5496')

    # Users at top
    users = [(2, 10, 'Desktop\nBrowser', '#70AD47'), (5, 10, 'Mobile\nDevice', '#70AD47'),
             (14, 10, 'Census\nCollector', '#70AD47')]
    for x, y, label, color in users:
        circle = plt.Circle((x, y), 0.35, color=color, ec='black')
        ax.add_patch(circle)
        ax.text(x, y-0.7, label, ha='center', va='top', fontsize=8, fontweight='bold')

    # Internet cloud
    ax.text(3.5, 9, 'Internet', ha='center', fontsize=9, fontstyle='italic',
            bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='orange'))

    # Tiers inside cloud
    tiers = [
        (8, 7, 3.5, 0.8, 'CDN / WAF / Load Balancer', '#BDD7EE'),
        (8, 5.8, 3.5, 0.8, 'Web + Application Tier\n(Presentation & Business Logic)', '#D9E2F3'),
        (8, 4.5, 3.5, 0.8, 'Data Tier\n(Census DB + Session Cache)', '#E2EFDA'),
        (8, 3.2, 3.5, 0.8, 'Integration Tier\n(Data Transfer + Notifications)', '#FFF2CC'),
        (8, 1.8, 3.5, 0.8, 'Monitoring & Support', '#F2F2F2'),
    ]
    for x, y, w, h, label, color in tiers:
        rect = FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='black', linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8)

    # External systems
    ext_sys = [
        (14, 4, 'DoS Electronic\nCensus Processing', '#FFC000'),
        (14, 2, 'SMS\nGateway', '#FFC000'),
    ]
    for x, y, label, color in ext_sys:
        rect = FancyBboxPatch((x-1.2, y-0.4), 2.4, 0.8, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='black', linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, fontweight='bold')

    # Arrows
    ax.annotate('', xy=(3.5, 8.5), xytext=(2, 9.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(5, 8.5), xytext=(5, 9.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(8, 7.4), xytext=(4, 8.5),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='blue'))
    ax.text(5, 8.7, 'HTTPS', fontsize=7, color='blue')
    
    # Tier connections
    for y_from, y_to in [(6.6, 6.2), (5.4, 4.9), (4.1, 3.6)]:
        ax.annotate('', xy=(8, y_to), xytext=(8, y_from),
                    arrowprops=dict(arrowstyle='->', lw=1.2, color='#555'))

    # Integration to external
    ax.annotate('', xy=(12.8, 4), xytext=(9.75, 3.2),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='red'))
    ax.annotate('', xy=(12.8, 2), xytext=(9.75, 3),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='orange'))
    ax.annotate('', xy=(14, 9.5), xytext=(14, 2.4),
                arrowprops=dict(arrowstyle='->', lw=1, color='orange', linestyle='dashed'))
    ax.text(14.2, 6, 'SMS', fontsize=7, color='orange')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '02_Architecture_Overview.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 02_Architecture_Overview.png")

draw_aod()

# ============================================================
# EXERCISE 3: Component Relationship Diagram
# ============================================================
def draw_component():
    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('Exercise 3: Logical Component Relationship Diagram\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Components as boxes
    components = {
        'Presentation\nManager': (3, 8, '#BDD7EE'),
        'Authentication\nManager': (7, 8, '#D9E2F3'),
        'Session\nManager': (11, 8, '#D9E2F3'),
        'Form\nManager': (5, 5.5, '#E2EFDA'),
        'Validation\nEngine': (9, 5.5, '#E2EFDA'),
        'Data Access\nManager': (5, 3, '#FFF2CC'),
        'Integration\nManager': (9, 3, '#FFF2CC'),
        'Security\nManager': (13, 5.5, '#F4B183'),
        'Notification\nService': (13, 3, '#F4B183'),
        'Reporting\nService': (1.5, 3, '#F2F2F2'),
    }

    comp_positions = {}
    for label, (x, y, color) in components.items():
        rect = FancyBboxPatch((x-1.1, y-0.5), 2.2, 1, boxstyle="round,pad=0.08",
                              facecolor=color, edgecolor='black', linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5, fontweight='bold')
        comp_positions[label] = (x, y)

    # Actor
    circle = plt.Circle((0.8, 8), 0.3, color='#70AD47', ec='black')
    ax.add_patch(circle)
    ax.text(0.8, 7.4, 'Respondent', ha='center', fontsize=8, fontweight='bold')

    # External systems
    ext = [('Census\nDatabase', 5, 1, '#FFC000'), 
           ('DoS\nProcessing', 9, 1, '#FFC000'),
           ('SMS\nGateway', 13, 1, '#FFC000')]
    for label, x, y, color in ext:
        rect = FancyBboxPatch((x-1, y-0.4), 2, 0.8, boxstyle="round,pad=0.08",
                              facecolor=color, edgecolor='black', linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5)

    # Arrows (connections)
    connections = [
        ((1.1, 8), (1.9, 8)),           # Respondent -> Presentation
        ((4.1, 8), (5.9, 8)),           # Presentation -> Auth
        ((4.1, 7.5), (11, 7.5)),        # Presentation -> Session (via)
        ((3, 7.5), (5, 6)),             # Presentation -> Form
        ((6.1, 5.5), (7.9, 5.5)),       # Form -> Validation
        ((5, 5), (5, 3.5)),             # Form -> DataAccess
        ((6.1, 5), (9, 3.5)),           # Form -> Integration
        ((5, 2.5), (5, 1.4)),           # DataAccess -> DB
        ((9, 2.5), (9, 1.4)),           # Integration -> DoS
        ((10.1, 3), (11.9, 3)),         # Integration -> Notification
        ((13, 2.5), (13, 1.4)),         # Notification -> SMS
    ]
    for start, end in connections:
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='->', lw=1.2, color='#333'))

    # Security connects to all (dashed)
    ax.plot([13, 13], [5, 9.5], 'r--', lw=0.8, alpha=0.5)
    ax.text(14, 7, '(cross-cutting)', fontsize=6, color='red', fontstyle='italic')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '03_Component_Diagram.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 03_Component_Diagram.png")

draw_component()

# ============================================================
# EXERCISE 4: Location Model
# ============================================================
def draw_location():
    fig, ax = plt.subplots(1, 1, figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis('off')
    ax.set_title('Exercise 4: Location Model\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Locations as large rounded boxes
    locations = [
        (2, 7, 3, 1.5, 'Respondent Location\n(Homes/Offices\nacross Bolumbia)', '#E2EFDA'),
        (7, 7, 3, 1.5, 'Cloud Hosting\nEnvironment\n(Cloud Provider DC)', '#BDD7EE'),
        (12, 7, 3, 1.5, 'DoS Data Center\n(Government\nPremises)', '#FFF2CC'),
        (2, 3, 3, 1.5, 'Census Collector\n(Field - Mobile\nacross Bolumbia)', '#E2EFDA'),
        (7, 3, 3, 1.5, 'DoS Internal\nNetwork\n(Admin/Help Desk)', '#FFF2CC'),
        (12, 3, 3, 1.5, 'DR Region\n(Cloud Provider\nBackup DC)', '#BDD7EE'),
    ]

    for x, y, w, h, label, color in locations:
        rect = FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle="round,pad=0.15",
                              facecolor=color, edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8.5, fontweight='bold')

    # Connections
    conns = [
        ((3.5, 7), (5.5, 7), 'Internet\n(HTTPS)'),
        ((8.5, 7), (10.5, 7), 'Secure Link\n(VPN)'),
        ((3.5, 3), (5.5, 3), 'Mobile\nNetwork'),
        ((7, 5.75), (7, 4.5), 'Internal\nNetwork'),
        ((8.5, 3.5), (10.5, 6.5), 'Secure\nReplication'),
        ((7, 6.25), (2, 3.75), ''),
    ]
    for start, end, label in conns:
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='<->', lw=1.5, color='#2F5496'))
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        if label:
            ax.text(mid_x, mid_y + 0.3, label, ha='center', va='bottom', 
                    fontsize=7, fontstyle='italic', color='#2F5496')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '04_Location_Model.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 04_Location_Model.png")

draw_location()

# ============================================================
# EXERCISE 5: Logical Operational Model
# ============================================================
def draw_lom():
    fig, ax = plt.subplots(1, 1, figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis('off')
    ax.set_title('Exercise 5: Logical Operational Model (LOM)\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Cloud hosting boundary
    cloud = FancyBboxPatch((3, 1.5), 10, 8, boxstyle="round,pad=0.3",
                           facecolor='#F0F8FF', edgecolor='#2F5496', linewidth=2.5)
    ax.add_patch(cloud)
    ax.text(8, 9.2, 'Cloud Hosting Environment', ha='center', fontsize=10, 
            fontweight='bold', color='#2F5496')

    # Zones inside cloud
    zones = [
        (5, 7.5, 4, 1.5, 'DMZ / Internet Zone', '#FFDDDD'),
        (9, 5.5, 4, 1.5, 'Application Zone', '#DDFFDD'),
        (5, 3.5, 4, 1.5, 'Data Zone', '#FFFFDD'),
        (9, 3.5, 4, 1.5, 'Integration Zone', '#DDE8FF'),
    ]
    for x, y, w, h, label, color in zones:
        rect = FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='gray', linewidth=1.2, linestyle='--')
        ax.add_patch(rect)
        ax.text(x, y+h/2-0.2, label, ha='center', va='top', fontsize=7, 
                fontstyle='italic', color='gray')

    # Nodes inside zones
    nodes = [
        (5, 7.5, 'LN: Web Server\n[DU_Web]\nLoad Balancer + WAF', '#BDD7EE'),
        (9, 5.5, 'LN: App Server\n[DU_App]\nBusiness Logic', '#C6EFCE'),
        (5, 3.5, 'LN: Database Server\n[DU_Data]\nCensus DB + Cache', '#FFF2CC'),
        (9, 3.5, 'LN: Integration Server\n[DU_Integration]\nData Transfer', '#BDD7EE'),
    ]
    for x, y, label, color in nodes:
        rect = FancyBboxPatch((x-1.5, y-0.5), 3, 1, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='black', linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7)

    # External
    # Respondent
    circle = plt.Circle((1, 8), 0.3, color='#70AD47', ec='black')
    ax.add_patch(circle)
    ax.text(1, 7.4, 'Respondent', ha='center', fontsize=8, fontweight='bold')

    # DoS Processing
    rect = FancyBboxPatch((14, 3), 2, 1, boxstyle="round,pad=0.1",
                          facecolor='#FFC000', edgecolor='black', linewidth=1.3)
    ax.add_patch(rect)
    ax.text(15, 3.5, 'DoS\nProcessing', ha='center', va='center', fontsize=8)

    # Arrows
    ax.annotate('', xy=(3.5, 7.5), xytext=(1.3, 8),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='green'))
    ax.text(2.2, 8, 'HTTPS', fontsize=7, color='green')

    ax.annotate('', xy=(9, 6.25), xytext=(6.5, 7),
                arrowprops=dict(arrowstyle='->', lw=1.2))
    ax.annotate('', xy=(5, 4), xytext=(9, 5),
                arrowprops=dict(arrowstyle='->', lw=1.2))
    ax.annotate('', xy=(9, 4), xytext=(9, 5),
                arrowprops=dict(arrowstyle='->', lw=1.2))
    ax.annotate('', xy=(14, 3.5), xytext=(11, 3.5),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='red'))
    ax.text(12, 3.8, 'Secure\nTransfer', fontsize=7, color='red')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '05_LOM.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 05_LOM.png")

draw_lom()

# ============================================================
# EXERCISE 5: Physical Operational Model
# ============================================================
def draw_pom():
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('Exercise 5: Physical Operational Model (POM)\nElectronic Census System (ECS)', 
                 fontsize=14, fontweight='bold', pad=20)

    # Primary region
    primary = FancyBboxPatch((0.5, 3), 11, 8.5, boxstyle="round,pad=0.3",
                             facecolor='#F0F8FF', edgecolor='#2F5496', linewidth=2.5)
    ax.add_patch(primary)
    ax.text(6, 11.2, 'PRIMARY REGION (Cloud)', ha='center', fontsize=11, 
            fontweight='bold', color='#2F5496')

    # DR region
    dr = FancyBboxPatch((12, 3), 3.5, 4, boxstyle="round,pad=0.2",
                        facecolor='#FFF0F0', edgecolor='#C00000', linewidth=2)
    ax.add_patch(dr)
    ax.text(13.75, 6.8, 'DR REGION', ha='center', fontsize=9, fontweight='bold', color='#C00000')

    # Physical nodes in primary
    pnodes = [
        (3, 10, 'CDN Edge Nodes (Global)'),
        (8, 10, 'WAF + DDoS Protection'),
        (5.5, 8.8, 'Load Balancer x2\n(Active-Active)'),
        (5.5, 7.5, 'Web Servers x4+\n(Auto-scaling)'),
        (5.5, 6.2, 'App Servers x8+\n(Auto-scaling)'),
        (3, 6.2, 'Session Cache\nCluster x3 (Redis)'),
        (5.5, 4.8, 'Primary DB\n(HA Active/Standby)'),
        (3, 4.8, 'Read Replicas x2'),
        (8.5, 4.8, 'Integration\nServers x2'),
        (8.5, 6.2, 'Message Queue'),
        (10, 8.5, 'Monitoring Server'),
        (10, 7.3, 'Log Aggregation'),
        (10, 6.1, 'Bastion Host'),
    ]

    colors = ['#BDD7EE', '#BDD7EE', '#BDD7EE', '#C6EFCE', '#C6EFCE', 
              '#E2EFDA', '#FFF2CC', '#FFF2CC', '#DDE8FF', '#DDE8FF',
              '#F2F2F2', '#F2F2F2', '#F2F2F2']

    for (x, y, label), color in zip(pnodes, colors):
        rect = FancyBboxPatch((x-1.2, y-0.4), 2.4, 0.8, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='black', linewidth=1)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=6.5)

    # DR nodes
    dr_nodes = [
        (13.75, 6, 'Web/App\n(scaled down)'),
        (13.75, 4.8, 'DB Replica\n(async)'),
        (13.75, 3.6, 'Integration\n(standby)'),
    ]
    for x, y, label in dr_nodes:
        rect = FancyBboxPatch((x-1.1, y-0.35), 2.2, 0.7, boxstyle="round,pad=0.05",
                              facecolor='#FFE0E0', edgecolor='#C00000', linewidth=0.8)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=6.5)

    # Replication arrow
    ax.annotate('', xy=(12.2, 4.8), xytext=(7, 4.8),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#C00000', linestyle='dashed'))
    ax.text(9.5, 5.1, 'Async Replication', fontsize=7, color='#C00000')

    # Vertical flow arrows
    flow = [(5.5, 9.6), (5.5, 9.2), (5.5, 8.4), (5.5, 7.9), (5.5, 7.1), (5.5, 6.6), (5.5, 5.2)]
    for i in range(len(flow)-1):
        ax.annotate('', xy=flow[i+1], xytext=flow[i],
                    arrowprops=dict(arrowstyle='->', lw=0.8, color='#555'))

    # Users
    ax.text(3, 11.5, '🖥️ Desktop Users', fontsize=9)
    ax.text(7, 11.5, '📱 Mobile Users', fontsize=9)
    ax.annotate('', xy=(5.5, 10.4), xytext=(5, 11.3),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='green'))

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '05_POM.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 05_POM.png")

draw_pom()

# ============================================================
# EXERCISE 7: Architecture on a Page
# ============================================================
def draw_arch_on_page():
    fig, ax = plt.subplots(1, 1, figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis('off')
    ax.set_title('Exercise 7: Architecture-on-a-Page\nElectronic Census System (ECS) - Republic of Bolumbia', 
                 fontsize=13, fontweight='bold', pad=15)

    # Title banner
    banner = FancyBboxPatch((0.2, 10), 15.6, 0.7, boxstyle="round,pad=0.1",
                            facecolor='#2F5496', edgecolor='black', linewidth=1.5)
    ax.add_patch(banner)
    ax.text(8, 10.35, 'ECS: Online Census for 23M population | Cloud-hosted | 3-year delivery | Peak: Census Night',
            ha='center', va='center', fontsize=9, color='white', fontweight='bold')

    # Users section
    users_box = FancyBboxPatch((0.3, 8), 3, 1.8, boxstyle="round,pad=0.1",
                               facecolor='#E2EFDA', edgecolor='#548235', linewidth=1.5)
    ax.add_patch(users_box)
    ax.text(1.8, 9.5, 'USERS', ha='center', fontweight='bold', fontsize=9, color='#548235')
    ax.text(1.8, 9, '• Respondents (9.5M)\n• Collectors (27K)\n• DoS Admin\n• Support Staff',
            ha='center', va='top', fontsize=7)

    # Channels section
    chan_box = FancyBboxPatch((3.5, 8), 3, 1.8, boxstyle="round,pad=0.1",
                              facecolor='#BDD7EE', edgecolor='#2F5496', linewidth=1.5)
    ax.add_patch(chan_box)
    ax.text(5, 9.5, 'CHANNELS', ha='center', fontweight='bold', fontsize=9, color='#2F5496')
    ax.text(5, 9, '• Desktop Browser\n• Mobile Browser\n• SMS (Collectors)',
            ha='center', va='top', fontsize=7)

    # Solution architecture (main box)
    sol = FancyBboxPatch((0.3, 2.5), 10.5, 5.3, boxstyle="round,pad=0.2",
                         facecolor='#F0F8FF', edgecolor='#2F5496', linewidth=2)
    ax.add_patch(sol)
    ax.text(5.5, 7.5, 'SOLUTION ARCHITECTURE (Cloud-Native)', ha='center', 
            fontweight='bold', fontsize=9, color='#2F5496')

    # Layers inside solution
    layers = [
        (5.5, 6.8, 'CDN + WAF + Load Balancer', '#FFDDDD'),
        (5.5, 5.9, 'Web Tier (Responsive UI - HTML5/CSS3/JS)', '#E2EFDA'),
        (5.5, 5.0, 'App Tier (Auth, Form Mgmt, Validation)', '#D9E2F3'),
        (5.5, 4.1, 'Cache (Redis) + Database (PostgreSQL)', '#FFF2CC'),
        (5.5, 3.2, 'Integration (REST APIs + MQ → DoS Systems)', '#DDE8FF'),
    ]
    for x, y, label, color in layers:
        rect = FancyBboxPatch((x-4.5, y-0.35), 9, 0.7, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='gray', linewidth=0.8)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5)

    # Integrations
    int_box = FancyBboxPatch((6.8, 8), 3, 1.8, boxstyle="round,pad=0.1",
                              facecolor='#FFF2CC', edgecolor='#BF8F00', linewidth=1.5)
    ax.add_patch(int_box)
    ax.text(8.3, 9.5, 'INTEGRATIONS', ha='center', fontweight='bold', fontsize=9, color='#BF8F00')
    ax.text(8.3, 9, '• DoS Census Processing\n• SMS Gateway\n• Help Desk',
            ha='center', va='top', fontsize=7)

    # Key Decisions
    dec_box = FancyBboxPatch((11, 5.5), 4.7, 4.3, boxstyle="round,pad=0.1",
                             facecolor='#FBE5D6', edgecolor='#C55A11', linewidth=1.5)
    ax.add_patch(dec_box)
    ax.text(13.3, 9.5, 'KEY DECISIONS & RISKS', ha='center', fontweight='bold', 
            fontsize=9, color='#C55A11')
    decisions = ('DECISIONS:\n'
                 '1. Cloud-native (elastic scale)\n'
                 '2. Responsive web (no app install)\n'
                 '3. Stateless + session cache\n'
                 '4. CFN+ECN auth (no registration)\n'
                 '5. Async data transfer to DoS\n\n'
                 'RISKS:\n'
                 '• Census Night peak load\n'
                 '• Data privacy breach\n'
                 '• Browser compatibility\n'
                 '• Single point of failure')
    ax.text(13.3, 9, decisions, ha='center', va='top', fontsize=6.5)

    # NFRs bottom
    nfr_box = FancyBboxPatch((0.3, 0.3), 15.4, 2, boxstyle="round,pad=0.1",
                              facecolor='#F2F2F2', edgecolor='#333', linewidth=1.5)
    ax.add_patch(nfr_box)
    ax.text(8, 2.1, 'KEY NON-FUNCTIONAL REQUIREMENTS', ha='center', 
            fontweight='bold', fontsize=9)
    nfrs = ('Performance: <3s response  |  Scalability: Auto-scale to millions  |  '
            'Availability: 99.99%  |  Security: TLS + AES-256 + WAF\n'
            'Privacy: Statistics Act compliance  |  Capacity: 9.5M forms  |  '
            'Accessibility: WCAG  |  DR: Multi-region warm standby')
    ax.text(8, 1.3, nfrs, ha='center', va='center', fontsize=7)

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, '07_Architecture_On_A_Page.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Created: 07_Architecture_On_A_Page.png")

draw_arch_on_page()
print("\nAll diagrams generated in:", out_dir)
