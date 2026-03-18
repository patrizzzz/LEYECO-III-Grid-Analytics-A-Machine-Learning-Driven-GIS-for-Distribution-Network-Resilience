import os
import subprocess
import json
import fnmatch

with open('git_files.json', 'r') as f:
    data = json.load(f)

tracked_files = data['tracked']

patterns = [
    "debug_*.py",
    "test_*.py",
    "verify_*.py",
    "check_*.py",
    "inspect_*.py",
    "tmp_*.py",
    "*_debug.py",
    "analyze_*.py",
    
    "*.csv",
    "*.xlsx",
    "*.log",
    "*out.txt",
    "*output.txt",
    "*log.txt",
    "out*.json",
    "trace_debug.json",
    "data_inspection*.txt",
    "geometry_report.txt",
    "excel_inspection.txt",
    "dir_xl.txt",
    "all_posts_db.txt",
    "nodes_sample.txt",
    "gen_conn_sample.txt",
    "sl_prefixes.txt",
    "modified_list.txt",
    "modified_files.txt",
    "git_status.txt",
    "git_files.json",
    "list_files.py",
    "cleanup_git.py"
]

to_remove = set()
for f in tracked_files:
    # Exclude requirements.txt from wildcard accidental matches just in case
    if f == "requirements.txt":
        continue
    for p in patterns:
        if fnmatch.fnmatch(os.path.basename(f), p) or fnmatch.fnmatch(f, p):
            to_remove.add(f)
            break

# Also include staged files that are not tracked yet
staged_files = data.get('staged', [])
for f in staged_files:
    if f == "requirements.txt":
        continue
    for p in patterns:
        if fnmatch.fnmatch(os.path.basename(f), p) or fnmatch.fnmatch(f, p):
            to_remove.add(f)
            break

print(f"Found {len(to_remove)} files to remove from git tracking.")

# Remove from git cache
if to_remove:
    # chunk into 50 files at a time to avoid command line length limits
    files_list = list(to_remove)
    for i in range(0, len(files_list), 50):
        chunk = files_list[i:i+50]
        cmd = ["git", "rm", "--cached", "-q"] + chunk
        subprocess.run(cmd)

# Add patterns to .gitignore
existing_ignore = ""
if os.path.exists(".gitignore"):
    with open(".gitignore", "r") as f:
        existing_ignore = f.read()

new_patterns = []
for p in patterns:
    # check if pattern is already in .gitignore
    if p not in existing_ignore:
        new_patterns.append(p)

if new_patterns:
    with open(".gitignore", "a") as f:
        f.write("\n\n# Auto-added patterns for test/debug/data files\n")
        for p in new_patterns:
            f.write(p + "\n")
            
print("Successfully applied git rm --cached and updated .gitignore!")
