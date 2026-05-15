import re

file_path = r'c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\migrations\versions\c120a4afa653_sync_upload_provenance_columns.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to insert add_column and create_foreign_key before create_index in upgrade()
# Only for tables that don't have it (bus_post_mapping already has add_column)

def replacer(match):
    table_name = match.group(1)
    if table_name == 'bus_post_mapping':
        return match.group(0) # unchanged
    
    # We want to add column and foreign key
    injection = f"        batch_op.add_column(sa.Column('upload_id', sa.Integer(), nullable=True))\n        batch_op.create_foreign_key(None, 'upload_history', ['upload_id'], ['id'])\n"
    
    # return the original match up to the create_index line, injecting before create_index
    # Actually, the match is just the batch_alter_table line.
    return match.group(0) + "\n" + injection

# We will match: with op.batch_alter_table('table_name', schema=None) as batch_op:
content = re.sub(r"(    with op\.batch_alter_table\('([^']+)', schema=None\) as batch_op:)", replacer, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('File patched with add_column successfully.')
