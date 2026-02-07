import json
import sys

def find_control_chars(obj, path=""):
    """Find any control characters in the data"""
    issues = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            issues.extend(find_control_chars(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            issues.extend(find_control_chars(item, f"{path}[{i}]"))
    elif isinstance(obj, str):
        # Check for problematic characters
        for i, char in enumerate(obj):
            if ord(char) < 32 and char not in ['\n', '\t', '\r']:
                issues.append({
                    "path": path,
                    "position": i,
                    "char": repr(char),
                    "text_sample": obj[max(0,i-20):i+20]
                })
    
    return issues

# Load your hackathon file
filename = sys.argv[1] if len(sys.argv) > 1 else 'hackathon_data.json'

print(f"🔍 Checking {filename}...\n")

try:
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("✅ JSON is valid and parseable!")
    
    # Check for control characters
    issues = find_control_chars(data)
    
    if issues:
        print(f"\n⚠️  Found {len(issues)} control character issues:\n")
        for issue in issues[:10]:  # Show first 10
            print(f"  Path: {issue['path']}")
            print(f"  Character: {issue['char']} at position {issue['position']}")
            print(f"  Context: ...{issue['text_sample']}...")
            print()
    else:
        print("✅ No control character issues found!")
    
    # Show structure
    print("\n📊 Data Structure:")
    print(f"  - _id: {data.get('_id')}")
    print(f"  - name: {data.get('name')}")
    print(f"  - themes: {len(data.get('themes', []))} themes")
    print(f"  - phases: {len(data.get('phases', []))} phases")
    print(f"  - faq: {len(data.get('faq', []))} FAQs")
    print(f"  - mentors: {len(data.get('mentors', []))} mentors")
    
    # Validate FAQ specifically
    if data.get('faq'):
        print("\n✅ FAQ looks good:")
        for i, faq in enumerate(data['faq'], 1):
            print(f"  Q{i}: {faq.get('question', 'N/A')}")
    
except json.JSONDecodeError as e:
    print(f"❌ JSON Syntax Error!")
    print(f"   Line {e.lineno}, Column {e.colno}")
    print(f"   Error: {e.msg}")
    
    # Show context
    lines = e.doc.split('\n')
    if e.lineno <= len(lines):
        print(f"\n   Line {e.lineno}: {lines[e.lineno-1]}")
        print(f"   {' ' * (e.colno + 9)}^")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()