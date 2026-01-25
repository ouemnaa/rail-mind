import os
p = r'C:\\vectors-in-orbit\\detection'
print('path:', p)
print('exists:', os.path.exists(p))
if os.path.exists(p):
    try:
        print('isdir:', os.path.isdir(p))
        print('entries:', sorted(os.listdir(p))[:50])
    except Exception as e:
        print('list error:', e)
else:
    # also try searching upward
    for root, dirs, files in os.walk(r'C:\\vectors-in-orbit'):
        if 'detection' in dirs:
            print('found detection at', os.path.join(root,'detection'))
            break
print('sys.path sample not shown')
