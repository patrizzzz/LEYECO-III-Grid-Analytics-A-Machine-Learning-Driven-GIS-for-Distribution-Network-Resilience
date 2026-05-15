import re

file_path = r'c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\migrations\versions\c120a4afa653_sync_upload_provenance_columns.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# In the upgrade() function, we want to comment out drop_index for idx_*_upload_id
content = re.sub(r"(batch_op\.drop_index\(batch_op\.f\('idx_[a-zA-Z0-9_]+_upload_id'\)\))", r'# \1', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('File patched successfully.')
