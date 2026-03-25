import subprocess
import json

try:
    staged = subprocess.check_output('git diff --name-only --cached', shell=True).decode('utf-8').splitlines()
except:
    staged = []
    
try:
    tracked = subprocess.check_output('git ls-files', shell=True).decode('utf-8').splitlines()
except:
    tracked = []
    
try:
    untracked = subprocess.check_output('git ls-files --others --exclude-standard', shell=True).decode('utf-8').splitlines()
except:
    untracked = []

with open('git_files.json', 'w') as f:
    json.dump({'staged': staged, 'tracked': tracked, 'untracked': untracked}, f, indent=2)
