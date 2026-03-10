import os

target_dir = r"c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\routes"
for root, dirs, files in os.walk(target_dir):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f), 'r', encoding='utf-8') as file:
                for i, line in enumerate(file):
                    if 'service-drops' in line or 'SecondaryServiceDrop' in line:
                        print(f"{f}:{i+1}: {line.strip()}")
