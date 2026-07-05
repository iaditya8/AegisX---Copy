import re
import os

test_dir = "/app/tests/integration"
files_to_fix = [
    "test_cyber_risk_quantification.py",
    "test_governance_risk_compliance.py",
    "test_security_knowledge.py"
]

replacements = [
    ("CyberRiskQuantificationService", "transition_status"),
    ("CyberRiskQuantificationService", "get_all_risks"),
    ("CyberRiskQuantificationService", "get_risk"),
    ("CyberRiskQuantificationService", "get_risk_by_fingerprint"),
    ("CyberRiskQuantificationService", "sync_risks"),
    
    ("GovernanceRiskComplianceService", "transition_status"),
    ("GovernanceRiskComplianceService", "get_all_assessments"),
    ("GovernanceRiskComplianceService", "get_assessment"),
    ("GovernanceRiskComplianceService", "get_assessment_by_fingerprint"),
    ("GovernanceRiskComplianceService", "recalculate_assessments"),
    ("GovernanceRiskComplianceService", "sync_assessments"),
    
    ("SecurityKnowledgeService", "transition_status"),
    ("SecurityKnowledgeService", "get_all_knowledge"),
    ("SecurityKnowledgeService", "get_knowledge"),
    ("SecurityKnowledgeService", "get_knowledge_by_fingerprint"),
    ("SecurityKnowledgeService", "recalculate_knowledge"),
    ("SecurityKnowledgeService", "add_tag"),
    ("SecurityKnowledgeService", "sync_knowledge"),
    
    ("KnowledgeRelationshipService", "add_relationship"),
    ("KnowledgeRelationshipService", "get_relationships"),
]

def add_await(content, class_name, method_name):
    # Matches class_name.method_name but NOT preceded by 'await ' or 'await\s+'
    pattern = r'(?<!await\s)(?<!await\s\s)' + re.escape(class_name) + r'\.' + re.escape(method_name)
    replacement = 'await ' + class_name + '.' + method_name
    return re.sub(pattern, replacement, content)

for filename in files_to_fix:
    filepath = os.path.join(test_dir, filename)
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    original = content
    for class_name, method_name in replacements:
        content = add_await(content, class_name, method_name)
        
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed await calls in {filename}")
    else:
        print(f"No changes needed for {filename}")
